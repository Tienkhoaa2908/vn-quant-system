"""Deterministic operational dry-runs and source registry for V38."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

OPS_KEYS = (
    "data_freshness_fail_closed",
    "idempotent_daily_run_verified",
    "kill_switch_tested",
    "manual_order_confirmation_required",
    "account_sync_verified",
    "position_reconciliation_verified",
    "stale_signal_rejected",
    "duplicate_order_prevention_tested",
    "no_automatic_live_orders",
)


@dataclass
class OperationalGuard:
    max_signal_age_days: int = 1
    seen_run_ids: set[str] = field(default_factory=set)
    seen_order_fingerprints: set[str] = field(default_factory=set)
    kill_switch: bool = False

    def begin_run(self, run_id: str) -> None:
        if not run_id or run_id in self.seen_run_ids:
            raise ValueError("DUPLICATE_RUN")
        self.seen_run_ids.add(run_id)

    def validate_signal(self, signal_day: date, as_of: date) -> None:
        age = (as_of - signal_day).days
        if age < 0 or age > self.max_signal_age_days:
            raise ValueError("STALE_SIGNAL")

    def authorize_order(self, *, fingerprint: str, manually_confirmed: bool, signal_day: date, as_of: date) -> None:
        if self.kill_switch:
            raise ValueError("KILL_SWITCH_ACTIVE")
        self.validate_signal(signal_day, as_of)
        if not manually_confirmed:
            raise ValueError("MANUAL_CONFIRMATION_REQUIRED")
        if not fingerprint or fingerprint in self.seen_order_fingerprints:
            raise ValueError("DUPLICATE_ORDER")
        self.seen_order_fingerprints.add(fingerprint)


def raises(expected: str, fn) -> bool:
    try:
        fn()
    except ValueError as exc:
        return str(exc) == expected
    return False


def run_operational_dry_run() -> dict[str, object]:
    today = date(2026, 8, 3)
    guard = OperationalGuard(max_signal_age_days=1)
    guard.begin_run("daily-20260803")
    idempotent = raises("DUPLICATE_RUN", lambda: guard.begin_run("daily-20260803"))

    fresh = OperationalGuard(max_signal_age_days=1)
    fresh.validate_signal(today, today)
    stale = raises("STALE_SIGNAL", lambda: fresh.validate_signal(today - timedelta(days=2), today))

    manual = OperationalGuard()
    manual_required = raises("MANUAL_CONFIRMATION_REQUIRED", lambda: manual.authorize_order(
        fingerprint="AAA-BUY-100", manually_confirmed=False, signal_day=today, as_of=today,
    ))

    duplicate = OperationalGuard()
    duplicate.authorize_order(
        fingerprint="AAA-BUY-100", manually_confirmed=True, signal_day=today, as_of=today,
    )
    duplicate_rejected = raises("DUPLICATE_ORDER", lambda: duplicate.authorize_order(
        fingerprint="AAA-BUY-100", manually_confirmed=True, signal_day=today, as_of=today,
    ))

    kill = OperationalGuard(kill_switch=True)
    kill_tested = raises("KILL_SWITCH_ACTIVE", lambda: kill.authorize_order(
        fingerprint="BBB-BUY-100", manually_confirmed=True, signal_day=today, as_of=today,
    ))

    checklist = {
        "data_freshness_fail_closed": stale,
        "idempotent_daily_run_verified": idempotent,
        "kill_switch_tested": kill_tested,
        "manual_order_confirmation_required": manual_required,
        "account_sync_verified": False,
        "position_reconciliation_verified": False,
        "stale_signal_rejected": stale,
        "duplicate_order_prevention_tested": duplicate_rejected,
        "no_automatic_live_orders": True,
    }
    return {
        "status": "SUCCESS",
        "checklist": checklist,
        "passed_count": sum(value is True for value in checklist.values()),
        "total_count": len(checklist),
        "remaining_workstation_controls": [
            key for key in ("account_sync_verified", "position_reconciliation_verified")
            if checklist[key] is not True
        ],
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def authoritative_source_registry() -> dict[str, object]:
    return {
        "status": "SOURCE_REGISTRY_ONLY_NOT_COMPLETENESS_PROOF",
        "price_basis": [
            {"authority": "HOSE", "url": "https://www1.hsx.vn/vi/du-lieu-giao-dich/quy-mo-giao-dich/bo-chi-so", "evidence": "Official market-statistics price unit is thousand VND."},
            {"authority": "DNSE", "url": "https://docs.dnse.com.vn/", "evidence": "Confirm candle semantics and adjusted/unadjusted basis."},
        ],
        "sector_point_in_time": [
            {"authority": "HOSE", "url": "https://www.hsx.vn/vi/quan-ly-niem-yet/co-phieu", "evidence": "Official listing and sector classification source."},
            {"authority": "HNX", "url": "https://www.hnx.vn/vi-vn/co-phieu-etfs/chung-khoan-ny-quy-mo-theo-nganh.html", "evidence": "Official industry classification source."},
        ],
        "corporate_actions": [
            {"authority": "VSDC", "url": "https://www.vsd.vn/en/news", "evidence": "Official record-date and rights notices."},
            {"authority": "HNX", "url": "https://www.hnx.vn/vi-vn/m-niem-yet/tin-tuc.html", "evidence": "Official exchange notices and listed-share changes."},
            {"authority": "HOSE", "url": "https://www.hsx.vn/vi/su-kien", "evidence": "Official issuer events and disclosures."},
        ],
        "governance": {
            "source_registry_is_not_assurance": True,
            "sector_inference_from_ticker_forbidden": True,
            "corporate_action_empty_file_is_not_completeness": True,
            "live_capital_approved": False,
        },
    }
