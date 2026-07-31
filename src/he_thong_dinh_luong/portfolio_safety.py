"""Safety rules shared by live DNSE portfolio analysis and the local terminal.

This module deliberately contains no broker writes.  Its outputs are advisory and
are designed to fail closed when the cash payload is ambiguous.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CashSemantics:
    broker_buying_power_vnd: float
    total_cash_vnd: float
    withdrawable_cash_vnd: float
    planner_cash_vnd: float
    status: str
    warnings: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value["warnings"] = list(self.warnings)
        return value


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def find_number(payload: object, names: Sequence[str], default: float = 0.0) -> float:
    wanted = {name.lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in wanted:
                result = _number(value, float("nan"))
                if isfinite(result):
                    return max(0.0, result)
        for value in payload.values():
            result = find_number(value, names, float("nan"))
            if isfinite(result):
                return max(0.0, result)
    return default


def derive_cash_semantics(balance_payload: object) -> CashSemantics:
    """Separate broker buying power from cash that may safely enter the planner.

    ``availableCash`` can include intraday or broker-specific purchasing capacity.
    The local target-gap planner must not treat it as uncommitted settled cash.  We
    therefore use the lower of total cash and withdrawable cash when both exist,
    otherwise total cash.  Missing total cash is fail-closed and produces zero
    planner cash rather than silently falling back to buying power.
    """
    buying_power = find_number(
        balance_payload,
        ("availableCash", "available_cash", "buyingPower", "buying_power"),
    )
    total_cash = find_number(balance_payload, ("totalCash", "total_cash"))
    withdrawable = find_number(
        balance_payload,
        ("withdrawableCash", "withdrawable_cash", "cashWithdrawable"),
    )
    warnings: list[str] = []
    if total_cash <= 0:
        planner_cash = 0.0
        status = "BLOCKED_TOTAL_CASH_MISSING"
        warnings.append("PLANNER_CASH_BLOCKED_TOTAL_CASH_MISSING")
    else:
        planner_cash = min(total_cash, withdrawable) if withdrawable > 0 else total_cash
        status = "PASS_SETTLED_CASH"
    if buying_power > planner_cash + 1.0:
        warnings.append("BROKER_BUYING_POWER_EXCEEDS_SETTLED_PLANNER_CASH")
    if withdrawable <= 0:
        warnings.append("WITHDRAWABLE_CASH_NOT_AVAILABLE_USING_TOTAL_CASH")
    return CashSemantics(
        broker_buying_power_vnd=buying_power,
        total_cash_vnd=total_cash,
        withdrawable_cash_vnd=withdrawable,
        planner_cash_vnd=max(0.0, planner_cash),
        status=status,
        warnings=tuple(warnings),
    )


def resolve_position_action(
    *,
    target_weight_pct: float,
    current_weight_pct: float,
    above_ma250: bool,
    trend_score: float,
) -> str:
    """Return one stable action using an explicit priority order."""
    if target_weight_pct <= 0 and not above_ma250:
        return "REVIEW_REDUCE_OUTSIDE_TARGET"
    if target_weight_pct <= 0:
        return "NO_ADD_OUTSIDE_TARGET"
    if current_weight_pct > target_weight_pct + 2.0:
        return "NO_ADD_OVERWEIGHT"
    if above_ma250 and trend_score >= 0.60:
        return "TARGET_ELIGIBLE"
    return "WAIT_TREND_CONFIRMATION"


def foreign_trading_params(now: datetime, *, lookback_days: int = 10) -> dict[str, object]:
    if now.tzinfo is None:
        raise ValueError("FOREIGN_CONTEXT_TIMEZONE_REQUIRED")
    if lookback_days <= 0:
        raise ValueError("FOREIGN_CONTEXT_LOOKBACK_INVALID")
    start = now - timedelta(days=lookback_days)
    return {
        "type": "STOCK",
        "from": int(start.timestamp()),
        "to": int(now.timestamp()),
    }


ACTION_LABELS: dict[str, str] = {
    "TARGET_ELIGIBLE": "Có thể cân nhắc theo target",
    "WAIT_TREND_CONFIRMATION": "Chờ xu hướng xác nhận",
    "NO_ADD_OUTSIDE_TARGET": "Không mua thêm ngoài target",
    "REVIEW_REDUCE_OUTSIDE_TARGET": "Xem xét giảm, ngoài target và dưới MA250",
    "NO_ADD_OVERWEIGHT": "Không mua thêm, tỷ trọng đang cao",
    "HOLD_MONITOR": "Giữ và theo dõi",
}


def action_label(value: object) -> str:
    key = str(value or "HOLD_MONITOR")
    return ACTION_LABELS.get(key, key.replace("_", " ").title())
