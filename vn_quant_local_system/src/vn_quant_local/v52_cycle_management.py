"""V52 auditable capital-cycle discard and restore.

A cycle can be removed from the operational performance view only when it has
no effective actual fill.  The source plan is never physically deleted: V52
appends a DISCARD/RESTORE action, excludes discarded intents from reconciliation,
and rebuilds shadow trades from active cycles only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping, Sequence
from uuid import uuid4

from . import performance
from . import v51_integrity as v51
from .core import state_db, utc_now

V52_VERSION = "V52_AUDITABLE_CYCLE_DISCARD"
VALID_ACTIONS = {"DISCARD", "RESTORE"}

_ORIGINAL_REBUILD_SHADOW = None
_ORIGINAL_PERFORMANCE_STATUS = None
_ORIGINAL_LOAD_RECONCILIATION_INPUTS = None
_ORIGINAL_ADD_ACTUAL_FILL = None


def _ensure_schema(db) -> None:
    performance._ensure_schema(db)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS performance_cycle_actions_v52(
            action_id TEXT PRIMARY KEY,
            action_time TEXT NOT NULL,
            action_type TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            week_key TEXT,
            cycle_id TEXT,
            reason TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cycle_actions_v52_plan_time
        ON performance_cycle_actions_v52(plan_id,action_time,action_id);
        """
    )


def _decode_details(raw: object) -> dict[str, object]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _action_rows() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            """
            SELECT * FROM performance_cycle_actions_v52
            ORDER BY action_time,action_id
            """
        ).fetchall()
    result: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        row["details"] = _decode_details(row.pop("details_json", None))
        result.append(row)
    return result


def latest_cycle_action_index(
    rows: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw in rows if rows is not None else _action_rows():
        row = dict(raw)
        plan_id = str(row.get("plan_id") or "")
        action = str(row.get("action_type") or "").upper()
        if plan_id and action in VALID_ACTIONS:
            result[plan_id] = row
    return result


def discarded_plan_ids() -> set[str]:
    return {
        plan_id
        for plan_id, row in latest_cycle_action_index().items()
        if str(row.get("action_type") or "").upper() == "DISCARD"
    }


def _plan_row(plan_id: str) -> dict[str, object]:
    target = str(plan_id or "").strip()
    if not target:
        raise ValueError("PERFORMANCE_CYCLE_PLAN_ID_REQUIRED")
    with state_db() as db:
        _ensure_schema(db)
        row = db.execute(
            "SELECT * FROM performance_shadow_plans WHERE plan_id=?",
            (target,),
        ).fetchone()
    if row is None:
        raise ValueError("PERFORMANCE_CYCLE_NOT_FOUND")
    return dict(row)


def _append_cycle_action(
    *,
    action_type: str,
    plan: Mapping[str, object],
    reason: str,
) -> dict[str, object]:
    action = str(action_type or "").upper()
    if action not in VALID_ACTIONS:
        raise ValueError("PERFORMANCE_CYCLE_ACTION_INVALID")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("PERFORMANCE_CYCLE_REASON_REQUIRED")
    details = _decode_details(plan.get("details_json"))
    cycle_id = str(details.get("cycle_id") or "") or (
        str(plan.get("week_key") or "").removeprefix("CYCLE:") or None
    )
    action_time = utc_now()
    digest = sha256(
        json.dumps(
            {
                "nonce": uuid4().hex,
                "action_time": action_time,
                "action_type": action,
                "plan_id": str(plan["plan_id"]),
                "reason": normalized_reason,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    action_id = "cycle-action-" + digest[:20]
    payload = {
        "version": V52_VERSION,
        "source_plan_status": plan.get("status"),
        "source_execution_day": plan.get("execution_day"),
        "source_created_at": plan.get("created_at"),
        "physical_plan_deleted": False,
        "derived_shadow_trades_rebuilt": True,
        "audit_append_only": True,
    }
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            """
            INSERT INTO performance_cycle_actions_v52(
                action_id,action_time,action_type,plan_id,week_key,
                cycle_id,reason,details_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                action_id,
                action_time,
                action,
                str(plan["plan_id"]),
                plan.get("week_key"),
                cycle_id,
                normalized_reason,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    return {
        "status": "SUCCESS",
        "version": V52_VERSION,
        "action_id": action_id,
        "action_time": action_time,
        "action_type": action,
        "plan_id": str(plan["plan_id"]),
        "week_key": plan.get("week_key"),
        "cycle_id": cycle_id,
        "reason": normalized_reason,
        "physical_plan_deleted": False,
    }


def _load_reconciliation_inputs_v52() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    str | None,
]:
    assert _ORIGINAL_LOAD_RECONCILIATION_INPUTS is not None
    plans, shadow, actual, latest_day = _ORIGINAL_LOAD_RECONCILIATION_INPUTS()
    discarded = discarded_plan_ids()
    active_plans = [
        dict(row)
        for row in plans
        if str(row.get("plan_id") or "") not in discarded
    ]
    active_ids = {str(row.get("plan_id") or "") for row in active_plans}
    active_shadow = [
        dict(row)
        for row in shadow
        if str(row.get("plan_id") or "") in active_ids
    ]
    return active_plans, active_shadow, [dict(row) for row in actual], latest_day


def reconciliation_v52() -> list[dict[str, object]]:
    plans, shadow, actual, latest_day = _load_reconciliation_inputs_v52()
    return v51.reconcile_intents(
        plans=plans,
        shadow_trades=shadow,
        actual_fills=actual,
        latest_market_day=latest_day,
    )


def _actual_quantity_for_plan(plan_id: str) -> int:
    target = str(plan_id or "")
    return sum(
        int(row.get("actual_quantity") or 0)
        for row in reconciliation_v52()
        if str(row.get("plan_id") or "") == target
    )


def discard_cycle(*, plan_id: str, reason: str) -> dict[str, object]:
    plan = _plan_row(plan_id)
    latest = latest_cycle_action_index().get(str(plan["plan_id"]))
    if latest and str(latest.get("action_type") or "").upper() == "DISCARD":
        return {
            "status": "ALREADY_DISCARDED",
            "version": V52_VERSION,
            "plan_id": str(plan["plan_id"]),
            "action_id": latest.get("action_id"),
            "reason": latest.get("reason"),
        }
    actual_quantity = _actual_quantity_for_plan(str(plan["plan_id"]))
    if actual_quantity > 0:
        raise ValueError(
            "PERFORMANCE_CYCLE_HAS_ACTUAL_FILL:"
            f"{plan['plan_id']}:{actual_quantity}"
        )
    result = _append_cycle_action(
        action_type="DISCARD",
        plan=plan,
        reason=reason,
    )
    performance.refresh_performance()
    result["message"] = (
        "Đã bỏ cycle khỏi đối soát và rebuild toàn bộ shadow đang hoạt động."
    )
    return result


def restore_cycle(*, plan_id: str, reason: str) -> dict[str, object]:
    plan = _plan_row(plan_id)
    latest = latest_cycle_action_index().get(str(plan["plan_id"]))
    if not latest or str(latest.get("action_type") or "").upper() != "DISCARD":
        return {
            "status": "ALREADY_ACTIVE",
            "version": V52_VERSION,
            "plan_id": str(plan["plan_id"]),
        }
    result = _append_cycle_action(
        action_type="RESTORE",
        plan=plan,
        reason=reason,
    )
    performance.refresh_performance()
    result["message"] = "Đã khôi phục cycle và rebuild shadow từ đầu."
    return result


def _active_shadow_plans() -> tuple[list[dict[str, object]], set[str]]:
    discarded = discarded_plan_ids()
    with state_db() as db:
        _ensure_schema(db)
        all_plans = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_plans
                ORDER BY created_at,week_key
                """
            ).fetchall()
        ]
    active = [
        row
        for row in all_plans
        if str(row.get("plan_id") or "") not in discarded
    ]
    return active, discarded


def rebuild_shadow_v52(config: Mapping[str, object]) -> None:
    """Rebuild derived shadow state using active cycles only."""

    latest_day = performance._latest_market_day()
    cost_rate = float(config["shadow_cost_bps"]) / 10_000.0
    tax_rate = float(config["sell_tax_bps"]) / 10_000.0
    cash = float(config["opening_model_cash_vnd"])
    positions = performance._adopted_opening_positions()
    plans, discarded = _active_shadow_plans()
    trades: list[dict[str, object]] = []

    for plan in plans:
        execution_day = plan.get("execution_day") or performance._next_session(
            str(plan["created_at"])[:10]
        )
        if not execution_day or str(execution_day) > latest_day:
            continue
        details = _decode_details(plan.get("details_json"))
        cash += float(plan["planned_contribution_vnd"])
        for raw in details.get("exit_candidates", []):
            if not isinstance(raw, Mapping):
                continue
            symbol = str(raw.get("symbol") or "").upper()
            held = positions.get(symbol, 0)
            requested = int(
                raw.get("sellable_quantity")
                or raw.get("quantity")
                or held
            )
            quantity = min(held, requested)
            price = performance._price_exact(
                symbol, str(execution_day), "open"
            )
            if quantity <= 0 or price is None:
                continue
            gross = quantity * price
            fees = gross * cost_rate
            taxes = gross * tax_rate
            cash += gross - fees - taxes
            positions[symbol] = held - quantity
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-SELL-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "SELL",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": quantity,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": taxes,
                    "details": {
                        "execution_rule": "T_PLUS_1_EXACT_OPEN_SELL_FIRST",
                        "cycle_filter": "V52_ACTIVE_ONLY",
                    },
                }
            )
        for raw in details.get("buy_orders", []):
            if not isinstance(raw, Mapping):
                continue
            symbol = str(raw.get("symbol") or "").upper()
            requested = int(raw.get("quantity") or 0)
            price = performance._price_exact(
                symbol, str(execution_day), "open"
            )
            if requested <= 0 or price is None:
                continue
            unit_cost = price * (1.0 + cost_rate)
            quantity = min(requested, int(max(cash, 0.0) // unit_cost))
            if quantity <= 0:
                continue
            gross = quantity * price
            fees = gross * cost_rate
            cash -= gross + fees
            positions[symbol] = positions.get(symbol, 0) + quantity
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-BUY-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "BUY",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": quantity,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": 0.0,
                    "details": {
                        "execution_rule": "T_PLUS_1_EXACT_OPEN",
                        "limited_by_cash": quantity < requested,
                        "cycle_filter": "V52_ACTIVE_ONLY",
                    },
                }
            )

    with state_db() as db:
        _ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("DELETE FROM performance_shadow_trades")
            db.executemany(
                """
                INSERT INTO performance_shadow_trades(
                    trade_id,plan_id,execution_day,side,symbol,
                    requested_quantity,filled_quantity,price_vnd,gross_vnd,
                    fees_vnd,taxes_vnd,details_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        row["trade_id"],
                        row["plan_id"],
                        row["execution_day"],
                        row["side"],
                        row["symbol"],
                        row["requested_quantity"],
                        row["filled_quantity"],
                        row["price_vnd"],
                        row["gross_vnd"],
                        row["fees_vnd"],
                        row["taxes_vnd"],
                        json.dumps(
                            row["details"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                    for row in trades
                ],
            )
            all_plans = db.execute(
                "SELECT week_key,plan_id,created_at,execution_day FROM performance_shadow_plans"
            ).fetchall()
            for row in all_plans:
                plan_id = str(row["plan_id"])
                if plan_id in discarded:
                    db.execute(
                        """
                        UPDATE performance_shadow_plans
                        SET status='DISCARDED' WHERE week_key=?
                        """,
                        (row["week_key"],),
                    )
                    continue
                execution_day = row["execution_day"] or performance._next_session(
                    str(row["created_at"])[:10]
                )
                status = (
                    "EXECUTED"
                    if execution_day and str(execution_day) <= latest_day
                    else "PENDING_MARKET_DATA"
                )
                db.execute(
                    """
                    UPDATE performance_shadow_plans
                    SET execution_day=?,status=? WHERE week_key=?
                    """,
                    (execution_day, status, row["week_key"]),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise


def _discarded_cycle_catalog() -> list[dict[str, object]]:
    action_index = latest_cycle_action_index()
    discarded = {
        plan_id: row
        for plan_id, row in action_index.items()
        if str(row.get("action_type") or "").upper() == "DISCARD"
    }
    if not discarded:
        return []
    with state_db() as db:
        _ensure_schema(db)
        plans = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_shadow_plans ORDER BY created_at DESC"
            ).fetchall()
        ]
    intents = v51.extract_plan_intents(plans)
    intents_by_plan: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in intents:
        intents_by_plan[str(row.get("plan_id") or "")].append(dict(row))
    result: list[dict[str, object]] = []
    for plan in plans:
        plan_id = str(plan.get("plan_id") or "")
        action = discarded.get(plan_id)
        if action is None:
            continue
        details = _decode_details(plan.get("details_json"))
        rows = intents_by_plan.get(plan_id, [])
        result.append(
            {
                "plan_id": plan_id,
                "week_key": plan.get("week_key"),
                "cycle_id": details.get("cycle_id")
                or str(plan.get("week_key") or "").removeprefix("CYCLE:"),
                "created_at": plan.get("created_at"),
                "created_at_vn": v51._display_time_vn(plan.get("created_at")),
                "discarded_at": action.get("action_time"),
                "discarded_at_vn": v51._display_time_vn(action.get("action_time")),
                "reason": action.get("reason"),
                "symbols": [str(row.get("symbol") or "") for row in rows],
                "planned_quantity": sum(
                    int(row.get("planned_quantity") or 0) for row in rows
                ),
                "status": "DISCARDED",
                "restorable": True,
            }
        )
    return result


def performance_status_v52() -> dict[str, object]:
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    status["v52_version"] = V52_VERSION
    if status.get("status") != "ACTIVE":
        return status
    status["discarded_cycle_catalog"] = _discarded_cycle_catalog()
    status["cycle_action_audit"] = _action_rows()
    limitations = dict(status.get("limitations") or {})
    limitations.update(
        {
            "cycle_discard_is_audited_not_physical_delete": True,
            "cycle_with_actual_fill_cannot_be_discarded": True,
            "discarded_cycle_intents_excluded_from_reconciliation": True,
            "discarded_cycle_shadow_trades_excluded_from_nav": True,
        }
    )
    status["limitations"] = limitations
    return status


def add_actual_fill_v52(**kwargs):
    assert _ORIGINAL_ADD_ACTUAL_FILL is not None
    plan_id = str(kwargs.get("plan_id") or "")
    if plan_id and plan_id in discarded_plan_ids():
        raise ValueError("PERFORMANCE_FILL_REFERENCES_DISCARDED_CYCLE")
    return _ORIGINAL_ADD_ACTUAL_FILL(**kwargs)


def apply() -> None:
    if getattr(performance, "_v52_cycle_management_applied", False):
        return
    global _ORIGINAL_REBUILD_SHADOW, _ORIGINAL_PERFORMANCE_STATUS
    global _ORIGINAL_LOAD_RECONCILIATION_INPUTS, _ORIGINAL_ADD_ACTUAL_FILL

    _ORIGINAL_REBUILD_SHADOW = performance._rebuild_shadow
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    _ORIGINAL_LOAD_RECONCILIATION_INPUTS = v51._load_reconciliation_inputs
    _ORIGINAL_ADD_ACTUAL_FILL = performance.add_actual_fill

    v51._load_reconciliation_inputs = _load_reconciliation_inputs_v52
    v51.reconciliation_v51 = reconciliation_v52
    performance._rebuild_shadow = rebuild_shadow_v52
    performance._reconciliation = reconciliation_v52
    performance.performance_status = performance_status_v52
    performance.add_actual_fill = add_actual_fill_v52
    performance.discard_cycle = discard_cycle
    performance.restore_cycle = restore_cycle
    performance.V52_VERSION = V52_VERSION
    performance._v52_cycle_management_applied = True
