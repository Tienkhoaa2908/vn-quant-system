"""V46 event-driven capital planning.

Mỗi lần người dùng có vốn hoặc muốn rà soát danh mục có thể tạo một planning
cycle ngay tại thời điểm đó. Chu kỳ không phụ thuộc tuần. Hàm này tái sử dụng
planner P1 đã kiểm định để giữ nguyên logic ranking, sizing và sell review,
nhưng ghi thêm event metadata riêng cho performance shadow và audit.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Mapping

from .core import paths, state_db
from .weekly_plan import create_weekly_plan

PLANNING_MODE = "EVENT_DRIVEN_CAPITAL_CYCLE"
VALID_TRIGGERS = {
    "NEW_CAPITAL",
    "AVAILABLE_CASH",
    "SELL_PROCEEDS_AVAILABLE",
    "PORTFOLIO_REVIEW",
}


def _ensure_schema(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS capital_plans(
            cycle_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            new_capital_vnd REAL NOT NULL,
            broker_snapshot_id TEXT,
            market_day TEXT NOT NULL,
            ranking_run_id TEXT NOT NULL,
            note TEXT,
            details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_capital_plans_created
        ON capital_plans(created_at DESC);
        """
    )


def create_capital_plan(
    *,
    new_capital_vnd: float = 0.0,
    maximum_buy_orders: int | None = None,
    trigger_type: str | None = None,
    note: str | None = None,
) -> dict[str, object]:
    amount = float(new_capital_vnd)
    if amount < 0.0:
        raise ValueError("Tiền mới cho planning cycle không được âm")
    trigger = str(
        trigger_type
        or ("NEW_CAPITAL" if amount > 0.0 else "AVAILABLE_CASH")
    ).upper()
    if trigger not in VALID_TRIGGERS:
        raise ValueError("CAPITAL_PLAN_TRIGGER_INVALID")

    base = create_weekly_plan(
        weekly_budget_vnd=amount,
        maximum_buy_orders=maximum_buy_orders,
    )
    cycle_id = "cycle-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rationale = dict(base.get("rationale") or {})
    rationale.update(
        {
            "planning_mode": PLANNING_MODE,
            "cycle_id": cycle_id,
            "trigger_type": trigger,
            "planned_new_capital_vnd": amount,
            "canonical_shadow_rule": "EVERY_CAPITAL_CYCLE_AFTER_OBSERVATORY_START",
            "not_limited_to_calendar_week": True,
            "cycle_note": note,
        }
    )
    result = dict(base)
    result.update(
        {
            "cycle_id": cycle_id,
            "planning_mode": PLANNING_MODE,
            "trigger_type": trigger,
            "planned_new_capital_vnd": amount,
            "capital_available_before_plan_vnd": float(
                base.get("dnse_available_cash_vnd") or 0.0
            ),
            "total_planning_buying_power_vnd": float(
                base.get("spendable_budget_vnd") or 0.0
            ),
            "cycle_note": note,
            "rationale": rationale,
        }
    )
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            """
            INSERT INTO capital_plans(
                cycle_id,plan_id,created_at,trigger_type,new_capital_vnd,
                broker_snapshot_id,market_day,ranking_run_id,note,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cycle_id,
                str(base["plan_id"]),
                str(base["created_at"]),
                trigger,
                amount,
                rationale.get("broker_snapshot_id"),
                str(base.get("market_day") or ""),
                str(base.get("ranking_run_id") or ""),
                note,
                json.dumps(result, ensure_ascii=False, sort_keys=True),
            ),
        )
    output = paths().outputs / f"{cycle_id}.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def latest_capital_plan() -> dict[str, object] | None:
    with state_db() as db:
        _ensure_schema(db)
        row = db.execute(
            "SELECT details_json FROM capital_plans ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    value = json.loads(str(row["details_json"]))
    return dict(value) if isinstance(value, Mapping) else None


def capital_plan_history(limit: int = 50) -> list[dict[str, object]]:
    bounded = min(max(int(limit), 1), 500)
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            """
            SELECT details_json FROM capital_plans
            ORDER BY created_at DESC LIMIT ?
            """,
            (bounded,),
        ).fetchall()
    return [json.loads(str(row["details_json"])) for row in rows]
