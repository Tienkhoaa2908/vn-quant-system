"""Backward-compatible call surface for V47 capital-cycle helpers.

V47 added ``preview_snapshot_id`` to the duplicate guard. Older tests and local
extensions may still call the helper without that keyword. The runtime wrapper
keeps the new comparison semantics while defaulting the missing preview id to
``None``.
"""
from __future__ import annotations

from . import capital_plan

_ORIGINAL_RECENT_DUPLICATE = capital_plan._recent_duplicate


def recent_duplicate_compat(
    *,
    amount: float,
    trigger: str,
    broker_snapshot_id: str | None,
    maximum_buy_orders: int | None,
    preview_snapshot_id: str | None = None,
) -> dict[str, object] | None:
    return _ORIGINAL_RECENT_DUPLICATE(
        amount=amount,
        trigger=trigger,
        broker_snapshot_id=broker_snapshot_id,
        preview_snapshot_id=preview_snapshot_id,
        maximum_buy_orders=maximum_buy_orders,
    )


def apply() -> None:
    capital_plan._recent_duplicate = recent_duplicate_compat
