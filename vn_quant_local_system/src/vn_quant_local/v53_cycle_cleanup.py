"""V53 bulk cycle cleanup and inspectable intent details.

V53 keeps the V52 append-only audit model, but improves operational cleanup:

* multiple discardable cycles can be removed in one command;
* incomplete cycles may be discarded when their actual fills were assigned only
  by automatic matching.  Those fills are not deleted and are reconciled again
  against the remaining active cycles;
* an explicitly selected ``plan_id`` remains authoritative and locks the cycle;
* completed cycles and cycles whose shadow execution is already observable are
  immutable;
* status exposes per-intent quantities and match methods for direct UI review.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Mapping, Sequence
from uuid import uuid4

from . import performance
from . import v52_cycle_management as v52
from . import v52_status_safety
from .core import state_db, utc_now

V53_VERSION = "V53_BULK_CYCLE_CLEANUP"
AUTO_MATCH_METHOD = "AUTO_NEWEST_OPEN_INTENT"
EXPLICIT_MATCH_METHOD = "EXPLICIT_PLAN_ID"

_ORIGINAL_PERFORMANCE_STATUS = None
_ORIGINAL_ADD_ACTUAL_CASHFLOW = None


def _match_methods(value: object) -> set[str]:
    return {
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    }


def _latest_market_day_safe() -> str | None:
    try:
        return performance._latest_market_day()
    except Exception:
        return None


def _cycle_policy_rows(status: Mapping[str, object]) -> list[dict[str, object]]:
    reconciliation_by_plan: dict[str, list[dict[str, object]]] = {}
    for raw in status.get("reconciliation", []) or []:
        row = dict(raw)
        plan_id = str(row.get("plan_id") or "")
        if plan_id and row.get("intent_id"):
            reconciliation_by_plan.setdefault(plan_id, []).append(row)

    shadow_by_plan = {
        str(row.get("plan_id") or ""): dict(row)
        for row in status.get("shadow_plans", []) or []
    }
    latest_market_day = (
        str(status.get("latest_market_day_for_cycle_lock") or "") or None
    ) or _latest_market_day_safe()

    result: list[dict[str, object]] = []
    for raw in status.get("cycle_catalog", []) or []:
        cycle = dict(raw)
        plan_id = str(cycle.get("plan_id") or "")
        rows = reconciliation_by_plan.get(plan_id, [])
        shadow = shadow_by_plan.get(plan_id, {})

        intent_details: list[dict[str, object]] = []
        all_methods: set[str] = set()
        planned_quantity = 0
        actual_quantity = 0
        remaining_quantity = 0
        explicit_event_count = 0
        auto_event_count = 0

        for row in rows:
            methods = _match_methods(row.get("match_method"))
            all_methods.update(methods)
            event_count = len(row.get("actual_event_ids") or [])
            if EXPLICIT_MATCH_METHOD in methods:
                explicit_event_count += event_count
            if AUTO_MATCH_METHOD in methods:
                auto_event_count += event_count
            planned = int(row.get("planned_quantity") or 0)
            actual = int(row.get("actual_quantity") or 0)
            remaining = int(row.get("remaining_quantity") or 0)
            planned_quantity += planned
            actual_quantity += actual
            remaining_quantity += remaining
            intent_details.append(
                {
                    "intent_id": row.get("intent_id"),
                    "side": row.get("side"),
                    "symbol": row.get("symbol"),
                    "planned_quantity": planned,
                    "actual_quantity": actual,
                    "remaining_quantity": remaining,
                    "status": row.get("status"),
                    "match_method": row.get("match_method"),
                    "actual_vwap_vnd": row.get("actual_vwap_vnd"),
                    "actual_event_ids": list(row.get("actual_event_ids") or []),
                    "shadow_pending": bool(row.get("shadow_pending")),
                    "shadow_execution_day": row.get("shadow_execution_day"),
                    "shadow_quantity": int(row.get("shadow_quantity") or 0),
                    "shadow_price_vnd": row.get("shadow_price_vnd"),
                }
            )

        # Fall back to catalog totals only when no reconciliation intent exists.
        if not rows:
            planned_quantity = int(cycle.get("planned_quantity") or 0)
            actual_quantity = int(cycle.get("actual_quantity") or 0)
            remaining_quantity = int(cycle.get("remaining_quantity") or 0)
            intent_details = [dict(row) for row in cycle.get("intents", []) or []]

        complete = planned_quantity > 0 and remaining_quantity <= 0
        has_actual = actual_quantity > 0
        auto_only = has_actual and all_methods and all_methods <= {AUTO_MATCH_METHOD}
        explicit_binding = EXPLICIT_MATCH_METHOD in all_methods
        unclassified_actual = has_actual and not auto_only and not explicit_binding
        pre_execution = v52_status_safety._pre_execution(
            status=shadow.get("status") or cycle.get("shadow_status"),
            execution_day=shadow.get("execution_day") or cycle.get("execution_day"),
            latest_market_day=latest_market_day,
        )

        if complete:
            discardable = False
            lock_reason = "ACTUAL_COMPLETE"
        elif explicit_binding:
            discardable = False
            lock_reason = "EXPLICIT_PLAN_BINDING"
        elif unclassified_actual:
            discardable = False
            lock_reason = "UNCLASSIFIED_ACTUAL_MATCH"
        elif not pre_execution:
            discardable = False
            lock_reason = "SHADOW_EXECUTION_ALREADY_OBSERVED"
        else:
            discardable = True
            lock_reason = None

        cycle.update(
            {
                "v53_version": V53_VERSION,
                "intents": intent_details,
                "planned_quantity": planned_quantity,
                "actual_quantity": actual_quantity,
                "remaining_quantity": remaining_quantity,
                "completion_ratio": (
                    min(actual_quantity / planned_quantity, 1.0)
                    if planned_quantity > 0
                    else 0.0
                ),
                "actual_complete": complete,
                "has_actual_fill": has_actual,
                "auto_match_only": auto_only,
                "explicit_plan_binding": explicit_binding,
                "explicit_event_count": explicit_event_count,
                "auto_event_count": auto_event_count,
                "match_methods": sorted(all_methods),
                "discardable": discardable,
                "discard_lock_reason": lock_reason,
                "discard_reassigns_auto_fills": bool(discardable and auto_only),
            }
        )
        result.append(cycle)
    return result


def performance_status_v53() -> dict[str, object]:
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    status["v53_version"] = V53_VERSION
    if status.get("status") != "ACTIVE":
        return status
    cycles = _cycle_policy_rows(status)
    status["cycle_catalog"] = cycles
    status["bulk_discardable_plan_ids"] = [
        str(row.get("plan_id") or "")
        for row in cycles
        if row.get("discardable")
    ]
    status["bulk_discardable_count"] = len(status["bulk_discardable_plan_ids"])
    limitations = dict(status.get("limitations") or {})
    limitations.update(
        {
            "bulk_cycle_discard_is_atomic": True,
            "partial_auto_matched_cycle_can_be_discarded": True,
            "auto_matched_fills_are_reconciled_again_after_discard": True,
            "explicit_plan_binding_locks_cycle": True,
            "completed_cycle_cannot_be_discarded": True,
            "observed_shadow_cannot_be_rewritten": True,
        }
    )
    status["limitations"] = limitations
    return status


def _action_row(plan: Mapping[str, object], reason: str, action_time: str) -> tuple:
    details = v52._decode_details(plan.get("details_json"))
    cycle_id = str(details.get("cycle_id") or "") or (
        str(plan.get("week_key") or "").removeprefix("CYCLE:") or None
    )
    digest = sha256(
        json.dumps(
            {
                "nonce": uuid4().hex,
                "action_time": action_time,
                "action_type": "DISCARD",
                "plan_id": str(plan["plan_id"]),
                "reason": reason,
                "version": V53_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    action_id = "cycle-action-" + digest[:20]
    payload = {
        "version": V53_VERSION,
        "source_plan_status": plan.get("status"),
        "source_execution_day": plan.get("execution_day"),
        "source_created_at": plan.get("created_at"),
        "physical_plan_deleted": False,
        "derived_shadow_trades_rebuilt": True,
        "audit_append_only": True,
        "bulk_operation": True,
        "actual_fills_deleted": False,
        "auto_matched_fills_reconciled_again": True,
    }
    return (
        action_id,
        action_time,
        "DISCARD",
        str(plan["plan_id"]),
        plan.get("week_key"),
        cycle_id,
        reason,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def discard_cycles(
    *,
    plan_ids: Sequence[str],
    reason: str,
) -> dict[str, object]:
    targets = list(dict.fromkeys(str(value or "").strip() for value in plan_ids))
    targets = [value for value in targets if value]
    if not targets:
        raise ValueError("PERFORMANCE_CYCLE_PLAN_IDS_REQUIRED")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("PERFORMANCE_CYCLE_REASON_REQUIRED")

    status = performance_status_v53()
    policies = {
        str(row.get("plan_id") or ""): row
        for row in status.get("cycle_catalog", []) or []
    }
    blocked: list[str] = []
    selected: list[dict[str, object]] = []
    for plan_id in targets:
        policy = policies.get(plan_id)
        if policy is None:
            if plan_id in v52.discarded_plan_ids():
                continue
            blocked.append(f"{plan_id}:NOT_ACTIVE_OR_NOT_FOUND")
            continue
        if not policy.get("discardable"):
            blocked.append(
                f"{plan_id}:{policy.get('discard_lock_reason') or 'LOCKED'}"
            )
            continue
        selected.append(policy)
    if blocked:
        raise ValueError("PERFORMANCE_CYCLE_BULK_DISCARD_BLOCKED:" + "|".join(blocked))
    if not selected:
        return {
            "status": "ALREADY_DISCARDED",
            "version": V53_VERSION,
            "discarded_plan_ids": [],
            "message": "Các cycle đã được bỏ trước đó.",
        }

    plans = [v52._plan_row(str(row["plan_id"])) for row in selected]
    action_time = utc_now()
    action_rows = [_action_row(plan, normalized_reason, action_time) for plan in plans]
    with state_db() as db:
        v52._ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.executemany(
                """
                INSERT INTO performance_cycle_actions_v52(
                    action_id,action_time,action_type,plan_id,week_key,
                    cycle_id,reason,details_json
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                action_rows,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    performance.refresh_performance()
    auto_reassigned = sum(
        int(row.get("actual_quantity") or 0)
        for row in selected
        if row.get("discard_reassigns_auto_fills")
    )
    return {
        "status": "SUCCESS",
        "version": V53_VERSION,
        "discarded_plan_ids": [str(row["plan_id"]) for row in selected],
        "discarded_count": len(selected),
        "auto_matched_quantity_reconciled_again": auto_reassigned,
        "physical_plan_deleted": False,
        "actual_fills_deleted": False,
        "message": (
            f"Đã bỏ {len(selected)} cycle và đối soát lại actual fill/shadow một lần."
        ),
    }


def _decode_command(note: str | None) -> Mapping[str, object]:
    try:
        value = json.loads(str(note or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("PERFORMANCE_CYCLE_COMMAND_INVALID") from exc
    if not isinstance(value, Mapping):
        raise ValueError("PERFORMANCE_CYCLE_COMMAND_INVALID")
    return value


def add_actual_cashflow_v53(
    *,
    flow_type: str,
    amount_vnd: float,
    event_day: str,
    note: str | None = None,
):
    kind = str(flow_type or "").upper()
    if kind not in {"DISCARD_CYCLE", "DISCARD_CYCLES"}:
        assert _ORIGINAL_ADD_ACTUAL_CASHFLOW is not None
        return _ORIGINAL_ADD_ACTUAL_CASHFLOW(
            flow_type=flow_type,
            amount_vnd=amount_vnd,
            event_day=event_day,
            note=note,
        )
    command = _decode_command(note)
    reason = str(command.get("reason") or "")
    if kind == "DISCARD_CYCLE":
        plan_ids = [str(command.get("plan_id") or "")]
    else:
        raw_plan_ids = command.get("plan_ids")
        if not isinstance(raw_plan_ids, Sequence) or isinstance(raw_plan_ids, (str, bytes)):
            raise ValueError("PERFORMANCE_CYCLE_PLAN_IDS_REQUIRED")
        plan_ids = [str(value or "") for value in raw_plan_ids]
    return discard_cycles(plan_ids=plan_ids, reason=reason)


def apply() -> None:
    if getattr(performance, "_v53_cycle_cleanup_applied", False):
        return
    global _ORIGINAL_PERFORMANCE_STATUS, _ORIGINAL_ADD_ACTUAL_CASHFLOW
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    _ORIGINAL_ADD_ACTUAL_CASHFLOW = performance.add_actual_cashflow
    performance.performance_status = performance_status_v53
    performance.add_actual_cashflow = add_actual_cashflow_v53
    performance.discard_cycles = discard_cycles
    performance.V53_VERSION = V53_VERSION
    performance._v53_cycle_cleanup_applied = True
