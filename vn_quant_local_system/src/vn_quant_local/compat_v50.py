"""Bind modules imported during package initialization to V50 broker functions."""
from __future__ import annotations

from . import broker_portfolio, capital_plan, performance, weekly_plan
from .buying_power_v50 import (
    create_weekly_plan_v50,
    latest_broker_portfolio_v50,
)


def apply() -> None:
    # buying_power_v50 is imported while package __init__ is still executing.
    # Rebind references captured before V49/V50 monkey patches were applied.
    weekly_plan.latest_broker_portfolio = latest_broker_portfolio_v50
    capital_plan.latest_broker_portfolio = latest_broker_portfolio_v50
    capital_plan.create_weekly_plan = create_weekly_plan_v50
    performance.latest_broker_portfolio = latest_broker_portfolio_v50
    broker_portfolio.latest_broker_portfolio = latest_broker_portfolio_v50
