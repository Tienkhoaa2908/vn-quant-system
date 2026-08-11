"""V56.1 parity fix for the V56 tail-risk research harness.

V56 intentionally values the study through analysis_end so that daily risk
signals can still be observed after the final weekly contribution day. V43.1,
however, reports its terminal value on the final weekly trading day. Comparing
those two terminal values directly made the baseline parity guard fail whenever
prices moved between the final weekly day and analysis_end.

This module changes only the parity check. It re-runs the V56 BASELINE through
the same final weekly trading day used by V43.1, then compares final value and
XIRR on that common date. The actual V56 study still runs through analysis_end.
Research only; no workstation/live-model bindings.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from . import tail_risk_overlay_v56 as v56
from . import weekly_micro_capital_v43 as base
from . import weekly_micro_capital_v43_1 as v43_1

PATCH_VERSION = "V56_1_COMMON_DATE_BASELINE_PARITY"


def baseline_parity_same_day(
    *,
    summaries: Sequence[Mapping[str, object]],
    snapshots: Sequence[base.SignalSnapshot],
    prices: base.PriceStore,
    weekly_days: Sequence[date],
    analysis_end: date,
) -> dict[str, object]:
    del summaries  # parity is recomputed independently on the common terminal date.
    parity_days = [day for day in weekly_days if day <= analysis_end]
    if not parity_days:
        raise ValueError("V56_1_NO_PARITY_WEEKLY_DAY")
    parity_day = parity_days[-1]
    baseline_spec = next(
        spec for spec in v56.OVERLAYS if spec.overlay_id == "BASELINE"
    )
    new, _, _ = v56.simulate_overlay(
        spec=baseline_spec,
        contribution=v56.PRIMARY_CONTRIBUTION,
        scenario=v56.PRIMARY_SCENARIO,
        snapshots=snapshots,
        prices=prices,
        weekly_days=weekly_days,
        analysis_end=parity_day,
    )
    old, _, _ = v43_1._simulate(
        policy_id=v56.BASE_POLICY,
        contribution=v56.PRIMARY_CONTRIBUTION,
        scenario=v56.PRIMARY_SCENARIO,
        snapshots=snapshots,
        prices=prices,
        weekly_days=parity_days,
    )
    final_diff = abs(float(new["final_value_vnd"]) - float(old["final_value_vnd"]))
    xirr_new = new.get("xirr")
    xirr_old = old.get("xirr")
    xirr_diff = (
        abs(float(xirr_new) - float(xirr_old))
        if xirr_new is not None and xirr_old is not None
        else None
    )
    passed = final_diff <= 0.01 and (xirr_diff is None or xirr_diff <= 1e-10)
    return {
        "status": "PASS" if passed else "FAIL",
        "comparison_day": parity_day.isoformat(),
        "study_analysis_end": analysis_end.isoformat(),
        "comparison_contract": "SAME_FINAL_WEEKLY_TRADING_DAY",
        "final_value_abs_diff_vnd": final_diff,
        "xirr_abs_diff": xirr_diff,
        "v56_final_value_vnd": new["final_value_vnd"],
        "v43_1_final_value_vnd": old["final_value_vnd"],
        "patch_version": PATCH_VERSION,
    }


def apply_patch() -> None:
    v56._baseline_parity = baseline_parity_same_day


def run_study(**kwargs: object) -> dict[str, object]:
    apply_patch()
    return v56.run_study(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    apply_patch()
    return v56.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
