"""V54 research-only cycle scope and sellability-aware compliance.

Operational performance must distinguish two user intentions:

* an operational capital cycle that the user intended to execute;
* a cycle created only to inspect model output.

V54 allows an incomplete cycle to be reclassified as ``RESEARCH_ONLY`` even
when its T+1 shadow has already been observed.  The source plan, actual fills,
and scope action remain append-only.  Operational reconciliation and shadow are
rebuilt without research-only cycles, while retroactive classification is
explicitly flagged as curated/hindsight-sensitive.

V54 also fixes a sell-intent defect.  A position with ``sellable_quantity=0`` is
not an executable sell order.  Such a row is retained for audit as
``WAIT_SELLABLE_AT_PLAN`` but is excluded from quantity-compliance and shadow
execution until a later plan sees sellable shares.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping, Sequence
from uuid import uuid4

from . import performance
from . import v51_integrity as v51
from . import v52_cycle_management as v52
from .core import state_db, utc_now

V54_VERSION = "V54_RESEARCH_SCOPE_SELLABILITY"
SCOPE_ACTIONS = {"MARK_RESEARCH_ONLY", "RESTORE_OPERATIONAL"}

_ORIGINAL_DISCARDED_PLAN_IDS = None
_ORIGINAL_ACTIVE_SHADOW_PLANS = None
_ORIGINAL_EXTRACT_PLAN_INTENTS = None
_ORIGINAL_PERFORMANCE_STATUS = None
_ORIGINAL_ADD_ACTUAL_CASHFLOW = None


def _ensure_schema(db) -> None:
    v52._ensure_schema(db)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS performance_cycle_scope_actions_v54(
            action_id TEXT PRIMARY KEY,
            action_time TEXT NOT NULL,
            action_type TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            retroactive INTEGER NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cycle_scope_v54_plan_time
        ON performance_cycle_scope_actions_v54(plan_id,action_time,action_id);
        """
    )


def _decode(raw: object) -> dict[str, object]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _scope_action_rows() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            """
            SELECT * FROM performance_cycle_scope_actions_v54
            ORDER BY action_time,action_id
            """
        ).fetchall()
    result: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        row["retroactive"] = bool(row.get("retroactive"))
        row["details"] = _decode(row.pop("details_json", None))
        result.append(row)
    return result


def latest_scope_action_index(
    rows: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw in rows if rows is not None else _scope_action_rows():
        row = dict(raw)
        plan_id = str(row.get("plan_id") or "")
        action = str(row.get("action_type") or "").upper()
        if plan_id and action in SCOPE_ACTIONS:
            result[plan_id] = row
    return result


def research_only_plan_ids() -> set[str]:
    return {
        plan_id
        for plan_id, row in latest_scope_action_index().items()
        if str(row.get("action_type") or "").upper() == "MARK_RESEARCH_ONLY"
    }


def operationally_excluded_plan_ids() -> set[str]:
    assert _ORIGINAL_DISCARDED_PLAN_IDS is not None
    return set(_ORIGINAL_DISCARDED_PLAN_IDS()) | research_only_plan_ids()


def _nonnegative_int(value: object) -> int:
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _sellability(
    row: Mapping[str, object],
    *,
    snapshot_sellable: int | None,
) -> tuple[int, int, str]:
    """Return requested, executable and source while preserving explicit zero."""

    requested = 0
    for key in ("quantity", "requested_quantity", "sellable_quantity"):
        if key in row and row.get(key) is not None:
            requested = _nonnegative_int(row.get(key))
            if requested > 0:
                break

    action = str(row.get("action") or "").upper()
    reason = str(row.get("reason") or "").upper()
    if action == "WAIT_SELLABLE" or "NOT_SELLABLE" in reason:
        return requested, 0, "PLAN_CLASSIFIED_WAIT_SELLABLE"

    if snapshot_sellable is not None:
        executable = min(requested, max(int(snapshot_sellable), 0))
        return requested, executable, "BROKER_SNAPSHOT_AT_PLAN"

    if "sellable_quantity" in row and row.get("sellable_quantity") is not None:
        executable = min(requested, _nonnegative_int(row.get("sellable_quantity")))
        return requested, executable, "PLAN_EXPLICIT_SELLABLE_QUANTITY"

    return requested, requested, "LEGACY_NO_SELLABILITY_FIELD"


def _snapshot_sellable_map(details: Mapping[str, object]) -> dict[str, int]:
    snapshot_id = str(details.get("broker_snapshot_id") or "")
    if not snapshot_id:
        return {}
    with state_db() as db:
        rows = db.execute(
            """
            SELECT symbol,sellable_quantity
            FROM broker_positions
            WHERE snapshot_id=?
            """,
            (snapshot_id,),
        ).fetchall()
    return {
        str(row["symbol"] or "").upper(): int(row["sellable_quantity"] or 0)
        for row in rows
        if str(row["symbol"] or "").strip()
    }


def _sell_rows_for_plan(
    plan: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    details = v52._decode_details(plan.get("details_json"))
    snapshot_sellable = _snapshot_sellable_map(details)
    plan_id = str(plan.get("plan_id") or "")
    cycle_id = str(details.get("cycle_id") or "") or (
        str(plan.get("week_key") or "").removeprefix("CYCLE:") or None
    )
    created_at = str(plan.get("created_at") or "")
    executable_rows: list[dict[str, object]] = []
    blocked_rows: list[dict[str, object]] = []

    for raw in details.get("exit_candidates", []) or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        requested, executable, source = _sellability(
            row,
            snapshot_sellable=snapshot_sellable.get(symbol),
        )
        if requested <= 0:
            continue
        common = {
            "plan_id": plan_id,
            "cycle_id": cycle_id,
            "week_key": plan.get("week_key"),
            "created_at": created_at,
            "execution_day": plan.get("execution_day"),
            "plan_status": plan.get("status"),
            "side": "SELL",
            "symbol": symbol,
            "requested_quantity": requested,
            "sellable_quantity_at_plan": executable,
            "sellability_source": source,
            "planning_price_vnd": float(row.get("price_vnd") or 0.0),
            "estimated_value_vnd": float(row.get("market_value_vnd") or 0.0),
        }
        if executable > 0:
            executable_rows.append(
                {
                    **common,
                    "intent_id": f"{plan_id}:SELL:{symbol}",
                    "planned_quantity": executable,
                    "compliance_eligible": True,
                }
            )
        blocked = max(requested - executable, 0)
        if blocked > 0:
            blocked_rows.append(
                {
                    **common,
                    "intent_id": f"{plan_id}:WAIT_SELLABLE:{symbol}",
                    "planned_quantity": blocked,
                    "actual_quantity": 0,
                    "remaining_quantity": 0,
                    "status": "WAIT_SELLABLE_AT_PLAN",
                    "match_method": None,
                    "actual_vwap_vnd": None,
                    "actual_event_ids": [],
                    "shadow_pending": False,
                    "shadow_quantity": 0,
                    "shadow_price_vnd": None,
                    "compliance_eligible": False,
                    "excluded_from_compliance": True,
                }
            )
    return executable_rows, blocked_rows


def extract_plan_intents_v54(
    plans: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Use V51 buy intents and rebuild sell intents with zero-safe semantics."""

    assert _ORIGINAL_EXTRACT_PLAN_INTENTS is not None
    result = [
        dict(row)
        for row in _ORIGINAL_EXTRACT_PLAN_INTENTS(plans)
        if str(row.get("side") or "").upper() != "SELL"
    ]
    for raw_plan in plans:
        executable, _ = _sell_rows_for_plan(dict(raw_plan))
        result.extend(executable)
    return sorted(
        result,
        key=lambda row: (
            v51._parse_datetime(row.get("created_at")),
            str(row.get("plan_id") or ""),
            str(row.get("side") or ""),
            str(row.get("symbol") or ""),
        ),
    )


def _active_shadow_plans_v54() -> tuple[list[dict[str, object]], set[str]]:
    """Sanitize plan details before the existing V52 shadow engine reads them."""

    assert _ORIGINAL_ACTIVE_SHADOW_PLANS is not None
    plans, excluded = _ORIGINAL_ACTIVE_SHADOW_PLANS()
    sanitized: list[dict[str, object]] = []
    for raw in plans:
        plan = dict(raw)
        details = v52._decode_details(plan.get("details_json"))
        executable, _ = _sell_rows_for_plan(plan)
        details["exit_candidates"] = [
            {
                "symbol": row["symbol"],
                "quantity": int(row["planned_quantity"]),
                "sellable_quantity": int(row["planned_quantity"]),
                "market_value_vnd": row.get("estimated_value_vnd"),
                "v54_sellability_source": row.get("sellability_source"),
            }
            for row in executable
        ]
        plan["details_json"] = json.dumps(
            details, ensure_ascii=False, sort_keys=True
        )
        sanitized.append(plan)
    return sanitized, excluded


def _all_plan_rows() -> list[dict[str, object]]:
    with state_db() as db:
        v52._ensure_schema(db)
        return [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_plans
                ORDER BY created_at DESC,week_key DESC
                """
            ).fetchall()
        ]


def _research_catalog() -> list[dict[str, object]]:
    action_index = latest_scope_action_index()
    research_ids = research_only_plan_ids()
    rows: list[dict[str, object]] = []
    for plan in _all_plan_rows():
        plan_id = str(plan.get("plan_id") or "")
        if plan_id not in research_ids:
            continue
        details = v52._decode_details(plan.get("details_json"))
        executable = extract_plan_intents_v54([plan])
        _, blocked = _sell_rows_for_plan(plan)
        action = action_index.get(plan_id, {})
        rows.append(
            {
                "plan_id": plan_id,
                "cycle_id": str(details.get("cycle_id") or "") or (
                    str(plan.get("week_key") or "").removeprefix("CYCLE:")
                ),
                "created_at": plan.get("created_at"),
                "created_at_vn": v51._display_time_vn(plan.get("created_at")),
                "execution_day": plan.get("execution_day"),
                "shadow_status": plan.get("status"),
                "symbols": sorted(
                    {
                        str(row.get("symbol") or "")
                        for row in executable + blocked
                        if str(row.get("symbol") or "")
                    }
                ),
                "compliance_planned_quantity": sum(
                    int(row.get("planned_quantity") or 0) for row in executable
                ),
                "wait_sellable_quantity": sum(
                    int(row.get("planned_quantity") or 0) for row in blocked
                ),
                "reason": action.get("reason"),
                "scope_action_time": action.get("action_time"),
                "scope_action_time_vn": v51._display_time_vn(
                    action.get("action_time")
                ),
                "retroactive": bool(action.get("retroactive")),
                "hindsight_sensitive": bool(action.get("retroactive")),
                "restorable": True,
            }
        )
    return rows


def _is_shadow_observed(cycle: Mapping[str, object], latest_day: str | None) -> bool:
    status = str(cycle.get("shadow_status") or "").upper()
    execution_day = str(cycle.get("execution_day") or "") or None
    return status == "EXECUTED" or bool(
        execution_day and latest_day and execution_day <= latest_day
    )


def performance_status_v54() -> dict[str, object]:
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    status["v54_version"] = V54_VERSION
    if status.get("status") != "ACTIVE":
        return status

    plans = {
        str(row.get("plan_id") or ""): row for row in _all_plan_rows()
    }
    latest_day = str(status.get("latest_market_day_for_cycle_lock") or "") or None
    active_cycles: list[dict[str, object]] = []
    for raw in status.get("cycle_catalog", []) or []:
        cycle = dict(raw)
        plan_id = str(cycle.get("plan_id") or "")
        plan = plans.get(plan_id)
        blocked: list[dict[str, object]] = []
        if plan is not None:
            _, blocked = _sell_rows_for_plan(plan)
        executable_intents = [dict(row) for row in cycle.get("intents", []) or []]
        cycle["intents"] = executable_intents + blocked
        cycle["compliance_planned_quantity"] = int(
            cycle.get("planned_quantity") or 0
        )
        cycle["wait_sellable_quantity"] = sum(
            int(row.get("planned_quantity") or 0) for row in blocked
        )
        cycle["raw_review_quantity"] = (
            cycle["compliance_planned_quantity"]
            + cycle["wait_sellable_quantity"]
        )
        cycle["symbols"] = sorted(
            {
                str(row.get("symbol") or "")
                for row in cycle["intents"]
                if str(row.get("symbol") or "")
            }
        )
        complete = bool(cycle.get("actual_complete")) or bool(
            int(cycle.get("planned_quantity") or 0) > 0
            and int(cycle.get("remaining_quantity") or 0) <= 0
        )
        observed = _is_shadow_observed(cycle, latest_day)
        cycle["research_scope_eligible"] = not complete
        cycle["research_scope_lock_reason"] = (
            "ACTUAL_COMPLETE" if complete else None
        )
        cycle["research_scope_retroactive"] = bool(observed and not complete)
        active_cycles.append(cycle)

    research_catalog = _research_catalog()
    retroactive_count = sum(1 for row in research_catalog if row["retroactive"])
    status["cycle_catalog"] = active_cycles
    status["research_only_cycle_catalog"] = research_catalog
    status["research_only_plan_ids"] = sorted(research_only_plan_ids())
    status["research_only_count"] = len(research_catalog)
    status["retroactive_research_only_count"] = retroactive_count
    status["operational_scope_curated"] = retroactive_count > 0
    status["scope_action_audit_v54"] = _scope_action_rows()
    status["sellability_policy"] = {
        "explicit_zero_is_preserved": True,
        "wait_sellable_excluded_from_compliance": True,
        "wait_sellable_excluded_from_shadow": True,
        "future_plan_rechecks_sellability": True,
    }
    limitations = dict(status.get("limitations") or {})
    limitations.update(
        {
            "research_only_reclassification_is_audited": True,
            "retroactive_scope_changes_are_hindsight_sensitive": True,
            "source_plans_and_actual_fills_are_never_deleted": True,
            "operational_metrics_exclude_research_only_cycles": True,
            "wait_sellable_is_not_a_compliance_failure": True,
        }
    )
    status["limitations"] = limitations
    return status


def _scope_action_tuple(
    *,
    plan: Mapping[str, object],
    action_type: str,
    reason: str,
    retroactive: bool,
    latest_market_day: str | None,
) -> tuple:
    action_time = utc_now()
    action_id = "scope-action-" + sha256(
        json.dumps(
            {
                "nonce": uuid4().hex,
                "action_time": action_time,
                "action_type": action_type,
                "plan_id": str(plan.get("plan_id") or ""),
                "reason": reason,
                "version": V54_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:20]
    payload = {
        "version": V54_VERSION,
        "source_plan_status": plan.get("status"),
        "source_execution_day": plan.get("execution_day"),
        "source_created_at": plan.get("created_at"),
        "latest_market_day_at_action": latest_market_day,
        "retroactive_after_shadow_observation": retroactive,
        "hindsight_sensitive": retroactive,
        "physical_plan_deleted": False,
        "actual_fills_deleted": False,
        "source_plan_immutable": True,
        "operational_shadow_rebuilt": True,
    }
    return (
        action_id,
        action_time,
        action_type,
        str(plan.get("plan_id") or ""),
        reason,
        1 if retroactive else 0,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _active_cycle_policy() -> tuple[dict[str, dict[str, object]], str | None]:
    status = performance_status_v54()
    latest_day = str(status.get("latest_market_day_for_cycle_lock") or "") or None
    return (
        {
            str(row.get("plan_id") or ""): dict(row)
            for row in status.get("cycle_catalog", []) or []
        },
        latest_day,
    )


def mark_research_only(
    *,
    plan_ids: Sequence[str],
    reason: str,
) -> dict[str, object]:
    targets = list(dict.fromkeys(str(value or "").strip() for value in plan_ids))
    targets = [value for value in targets if value]
    if not targets:
        raise ValueError("PERFORMANCE_SCOPE_PLAN_IDS_REQUIRED")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("PERFORMANCE_SCOPE_REASON_REQUIRED")

    policies, latest_day = _active_cycle_policy()
    current_research = research_only_plan_ids()
    blocked: list[str] = []
    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    for plan_id in targets:
        if plan_id in current_research:
            continue
        policy = policies.get(plan_id)
        if policy is None:
            blocked.append(f"{plan_id}:NOT_ACTIVE_OR_NOT_FOUND")
            continue
        if not policy.get("research_scope_eligible"):
            blocked.append(
                f"{plan_id}:{policy.get('research_scope_lock_reason') or 'LOCKED'}"
            )
            continue
        selected.append((policy, v52._plan_row(plan_id)))
    if blocked:
        raise ValueError("PERFORMANCE_SCOPE_BULK_BLOCKED:" + "|".join(blocked))
    if not selected:
        return {
            "status": "ALREADY_RESEARCH_ONLY",
            "version": V54_VERSION,
            "classified_plan_ids": [],
            "message": "Các cycle đã được loại khỏi đánh giá trước đó.",
        }

    rows = [
        _scope_action_tuple(
            plan=plan,
            action_type="MARK_RESEARCH_ONLY",
            reason=normalized_reason,
            retroactive=_is_shadow_observed(policy, latest_day),
            latest_market_day=latest_day,
        )
        for policy, plan in selected
    ]
    with state_db() as db:
        _ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.executemany(
                """
                INSERT INTO performance_cycle_scope_actions_v54(
                    action_id,action_time,action_type,plan_id,reason,
                    retroactive,details_json
                ) VALUES(?,?,?,?,?,?,?)
                """,
                rows,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    performance.refresh_performance()
    retroactive_count = sum(int(row[5]) for row in rows)
    return {
        "status": "SUCCESS",
        "version": V54_VERSION,
        "classified_plan_ids": [str(plan.get("plan_id")) for _, plan in selected],
        "classified_count": len(selected),
        "retroactive_count": retroactive_count,
        "physical_plan_deleted": False,
        "actual_fills_deleted": False,
        "message": (
            f"Đã loại {len(selected)} cycle khỏi đánh giá vận hành; "
            "actual fill và lịch sử gốc vẫn được giữ."
        ),
    }


def restore_operational(
    *,
    plan_ids: Sequence[str],
    reason: str,
) -> dict[str, object]:
    targets = list(dict.fromkeys(str(value or "").strip() for value in plan_ids))
    targets = [value for value in targets if value]
    if not targets:
        raise ValueError("PERFORMANCE_SCOPE_PLAN_IDS_REQUIRED")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("PERFORMANCE_SCOPE_REASON_REQUIRED")
    current = research_only_plan_ids()
    selected = [value for value in targets if value in current]
    if not selected:
        return {
            "status": "ALREADY_OPERATIONAL",
            "version": V54_VERSION,
            "restored_plan_ids": [],
        }
    latest_day = None
    try:
        latest_day = performance._latest_market_day()
    except Exception:
        pass
    rows = []
    for plan_id in selected:
        plan = v52._plan_row(plan_id)
        retroactive = bool(
            str(plan.get("status") or "").upper() == "EXECUTED"
            or (
                plan.get("execution_day")
                and latest_day
                and str(plan.get("execution_day")) <= latest_day
            )
        )
        rows.append(
            _scope_action_tuple(
                plan=plan,
                action_type="RESTORE_OPERATIONAL",
                reason=normalized_reason,
                retroactive=retroactive,
                latest_market_day=latest_day,
            )
        )
    with state_db() as db:
        _ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.executemany(
                """
                INSERT INTO performance_cycle_scope_actions_v54(
                    action_id,action_time,action_type,plan_id,reason,
                    retroactive,details_json
                ) VALUES(?,?,?,?,?,?,?)
                """,
                rows,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    performance.refresh_performance()
    return {
        "status": "SUCCESS",
        "version": V54_VERSION,
        "restored_plan_ids": selected,
        "restored_count": len(selected),
        "message": f"Đã đưa {len(selected)} cycle trở lại đánh giá vận hành.",
    }


def _decode_command(note: str | None) -> Mapping[str, object]:
    try:
        value = json.loads(str(note or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("PERFORMANCE_SCOPE_COMMAND_INVALID") from exc
    if not isinstance(value, Mapping):
        raise ValueError("PERFORMANCE_SCOPE_COMMAND_INVALID")
    return value


def add_actual_cashflow_v54(
    *,
    flow_type: str,
    amount_vnd: float,
    event_day: str,
    note: str | None = None,
):
    kind = str(flow_type or "").upper()
    if kind not in {
        "MARK_RESEARCH_ONLY",
        "MARK_RESEARCH_ONLY_BULK",
        "RESTORE_OPERATIONAL",
    }:
        assert _ORIGINAL_ADD_ACTUAL_CASHFLOW is not None
        return _ORIGINAL_ADD_ACTUAL_CASHFLOW(
            flow_type=flow_type,
            amount_vnd=amount_vnd,
            event_day=event_day,
            note=note,
        )
    command = _decode_command(note)
    reason = str(command.get("reason") or "")
    if kind == "MARK_RESEARCH_ONLY":
        return mark_research_only(
            plan_ids=[str(command.get("plan_id") or "")],
            reason=reason,
        )
    if kind == "MARK_RESEARCH_ONLY_BULK":
        raw = command.get("plan_ids")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("PERFORMANCE_SCOPE_PLAN_IDS_REQUIRED")
        return mark_research_only(
            plan_ids=[str(value or "") for value in raw],
            reason=reason,
        )
    return restore_operational(
        plan_ids=[str(command.get("plan_id") or "")],
        reason=reason,
    )


def apply() -> None:
    if getattr(performance, "_v54_research_scope_applied", False):
        return
    global _ORIGINAL_DISCARDED_PLAN_IDS, _ORIGINAL_ACTIVE_SHADOW_PLANS
    global _ORIGINAL_EXTRACT_PLAN_INTENTS, _ORIGINAL_PERFORMANCE_STATUS
    global _ORIGINAL_ADD_ACTUAL_CASHFLOW

    _ORIGINAL_DISCARDED_PLAN_IDS = v52.discarded_plan_ids
    _ORIGINAL_ACTIVE_SHADOW_PLANS = v52._active_shadow_plans
    _ORIGINAL_EXTRACT_PLAN_INTENTS = v51.extract_plan_intents
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    _ORIGINAL_ADD_ACTUAL_CASHFLOW = performance.add_actual_cashflow

    v52.discarded_plan_ids = operationally_excluded_plan_ids
    v52._active_shadow_plans = _active_shadow_plans_v54
    v51.extract_plan_intents = extract_plan_intents_v54
    performance.performance_status = performance_status_v54
    performance.add_actual_cashflow = add_actual_cashflow_v54
    performance.mark_research_only = mark_research_only
    performance.restore_operational = restore_operational
    performance.research_only_plan_ids = research_only_plan_ids
    performance.V54_VERSION = V54_VERSION
    performance._v54_research_scope_applied = True
