"""V33 fixed-turnover-cap stability audit for the frozen C3 score.

V33 consumes the canonical successful V32.1 artifact. It does not retrain or
change rankings. It compares fixed voluntary-replacement caps 0..10 against
V32.1's nested block-wise cap selector on the same 51 chronological outer-test
months and the same DNSE modeled-cost contract.

The cap grid is post-review sensitivity analysis. Cap 3 is the only
pre-registered policy candidate, inherited from V11. Historical results may
freeze it for a future paper holdout, but cannot promote research eligibility,
approve live capital, or reset the holdout clock.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
import zipfile

from . import model_lab_upgrade_v11 as v11
from . import model_lab_upgrade_v13 as v13
from . import portfolio_ablation_v30 as v30
from . import portfolio_ablation_v32 as v32

SCHEMA_VERSION = "turnover_policy_stability_v33"
REPORT_FILE = "turnover_policy_stability_v33.json"
FROZEN_MODEL = v32.FROZEN_MODEL
PRE_REGISTERED_CAP = 3
DEFAULT_CAPS = tuple(range(11))
REQUIRED_FILES = {
    v32.REPORT_FILE,
    "eligible_predictions_v32.csv",
    "outer_test_periods_v32.csv",
    "analysis_bundle_manifest_v32.json",
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def _safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"V33_UNSAFE_MEMBER:{name}")
    return path.name


def _read_csv_bytes(value: bytes) -> list[dict[str, str]]:
    with io.StringIO(value.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and fields is None:
        raise ValueError(f"V33_EMPTY_CSV:{path.name}")
    fieldnames = list(fields or ())
    if not fieldnames:
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _finite(value: object, *, name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"V33_MISSING_NUMERIC:{name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V33_NON_FINITE:{name}")
    return number


def _load_artifact(
    artifact_zip: Path,
    *,
    expected_sha256: str | None,
) -> tuple[
    dict[str, object],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, object],
]:
    source = Path(artifact_zip).resolve()
    if not source.is_file():
        raise ValueError("V33_V32_ARTIFACT_NOT_FOUND")
    artifact_sha = _sha256(source)
    if expected_sha256 and artifact_sha != expected_sha256:
        raise ValueError("V33_V32_ARTIFACT_SHA256_MISMATCH")

    members: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_basename(info.filename)
            if basename in members:
                raise ValueError(f"V33_DUPLICATE_BASENAME:{basename}")
            members[basename] = (info.filename, archive.read(info))
    missing = REQUIRED_FILES - set(members)
    if missing:
        raise ValueError(
            "V33_REQUIRED_FILES_MISSING:" + "|".join(sorted(missing))
        )

    report_bytes = members[v32.REPORT_FILE][1]
    report = json.loads(report_bytes.decode("utf-8-sig"))
    if not isinstance(report, dict):
        raise ValueError("V33_V32_REPORT_OBJECT_REQUIRED")
    if report.get("status") != "SUCCESS":
        raise ValueError("V33_V32_STATUS_NOT_SUCCESS")
    if report.get("upgrade_schema_version") != "portfolio_ablation_v32_1":
        raise ValueError("V33_V32_1_SCHEMA_REQUIRED")
    if report.get("evaluated_full_horizon_breadths") != [10]:
        raise ValueError("V33_EXPECTED_ONLY_TOP10_FULL_HORIZON")
    if bool(report.get("research_eligible")):
        raise ValueError("V33_SOURCE_RESEARCH_ELIGIBILITY_UNEXPECTED")
    if bool(report.get("live_capital_approved")):
        raise ValueError("V33_SOURCE_LIVE_CAPITAL_UNEXPECTED")

    predictions = _read_csv_bytes(
        members["eligible_predictions_v32.csv"][1]
    )
    outer = _read_csv_bytes(members["outer_test_periods_v32.csv"][1])
    metadata = {
        "artifact_zip": str(source),
        "artifact_zip_sha256": artifact_sha,
        "report_sha256": _bytes_sha256(report_bytes),
        "eligible_predictions_sha256": _bytes_sha256(
            members["eligible_predictions_v32.csv"][1]
        ),
        "outer_test_periods_sha256": _bytes_sha256(
            members["outer_test_periods_v32.csv"][1]
        ),
        "analysis_manifest_sha256": _bytes_sha256(
            members["analysis_bundle_manifest_v32.json"][1]
        ),
    }
    return report, predictions, outer, metadata


def _cost_from_report(report: Mapping[str, object]) -> v13.DnseCashCostConfig:
    contract = dict(report.get("cost_contract") or {})
    return v13.DnseCashCostConfig(
        broker_buy_fee_bps=_finite(
            contract.get("broker_buy_fee_bps"), name="broker_buy_fee_bps"
        ),
        broker_sell_fee_bps=_finite(
            contract.get("broker_sell_fee_bps"), name="broker_sell_fee_bps"
        ),
        exchange_buy_fee_bps=_finite(
            contract.get("exchange_buy_fee_bps"), name="exchange_buy_fee_bps"
        ),
        exchange_sell_fee_bps=_finite(
            contract.get("exchange_sell_fee_bps"), name="exchange_sell_fee_bps"
        ),
        sell_tax_bps=_finite(
            contract.get("sell_tax_bps"), name="sell_tax_bps"
        ),
        transfer_fee_vnd_per_share=_finite(
            contract.get("transfer_fee_vnd_per_share"),
            name="transfer_fee_vnd_per_share",
        ),
        transfer_reference_price_vnd=_finite(
            contract.get("transfer_reference_price_vnd"),
            name="transfer_reference_price_vnd",
        ),
        slippage_bps=_finite(
            contract.get("base_slippage_bps_each_side"), name="slippage_bps"
        ),
        stress_slippage_bps=_finite(
            contract.get("stress_slippage_bps_each_side"),
            name="stress_slippage_bps",
        ),
    )


def _normalize_caps(values: Sequence[int]) -> tuple[int, ...]:
    caps = tuple(sorted(set(int(value) for value in values)))
    if not caps or any(value < 0 or value > 10 for value in caps):
        raise ValueError("V33_INVALID_CAPS")
    if PRE_REGISTERED_CAP not in caps:
        raise ValueError("V33_PRE_REGISTERED_CAP_3_REQUIRED")
    return caps


def _official_nested_rows(
    outer_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    selected = [
        dict(row)
        for row in outer_rows
        if str(row.get("model") or "") == FROZEN_MODEL
        and int(float(row.get("breadth", 0) or 0)) == 10
        and str(row.get("cost_scenario") or "") == "BASE"
    ]
    selected.sort(key=lambda row: str(row.get("signal_date") or ""))
    if len(selected) != 51:
        raise ValueError(f"V33_EXPECTED_51_NESTED_PERIODS:{len(selected)}")
    dates = [str(row.get("signal_date") or "") for row in selected]
    if len(set(dates)) != len(dates):
        raise ValueError("V33_DUPLICATE_NESTED_DATE")
    return selected


def _c3_predictions(
    predictions: Sequence[Mapping[str, object]],
    dates: Sequence[str],
) -> list[dict[str, object]]:
    wanted = set(dates)
    selected = [
        dict(row)
        for row in predictions
        if str(row.get("model") or "") == FROZEN_MODEL
        and str(row.get("test_date") or "") in wanted
    ]
    by_day: dict[str, int] = {}
    for row in selected:
        day = str(row.get("test_date") or "")
        by_day[day] = by_day.get(day, 0) + 1
    if set(by_day) != wanted:
        raise ValueError("V33_C3_DATE_COVERAGE_MISMATCH")
    if min(by_day.values()) < 10:
        raise ValueError("V33_C3_TOP10_NOT_FEASIBLE")
    return selected


def _fixed_cap_rows(
    predictions: Sequence[Mapping[str, object]],
    *,
    caps: Sequence[int],
    cost: v13.DnseCashCostConfig,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    summary_rows: list[dict[str, object]] = []
    base_rows_all: list[dict[str, object]] = []
    stress_rows_all: list[dict[str, object]] = []
    for cap in caps:
        base_cache = v13._period_cache(
            predictions,
            top_k=10,
            candidate_models=(FROZEN_MODEL,),
            replacement_caps=(cap,),
            cost=cost,
            slippage_bps=cost.slippage_bps,
        )
        stress_cache = v13._period_cache(
            predictions,
            top_k=10,
            candidate_models=(FROZEN_MODEL,),
            replacement_caps=(cap,),
            cost=cost,
            slippage_bps=cost.stress_slippage_bps,
        )
        base_rows = [dict(row) for row in base_cache[(FROZEN_MODEL, cap)]]
        stress_rows = [dict(row) for row in stress_cache[(FROZEN_MODEL, cap)]]
        if len(base_rows) != 51 or len(stress_rows) != 51:
            raise ValueError(f"V33_FIXED_CAP_PERIOD_COUNT:{cap}")
        for row in base_rows:
            row["fixed_replacement_cap"] = cap
            row["cost_scenario"] = "BASE"
        for row in stress_rows:
            row["fixed_replacement_cap"] = cap
            row["cost_scenario"] = "STRESS"
        base_metrics = v11.capped_policy_metrics(base_rows)
        stress_metrics = v11.capped_policy_metrics(stress_rows)
        summary = {
            "model": FROZEN_MODEL,
            "breadth": 10,
            "fixed_replacement_cap": cap,
            "pre_registered_cap": cap == PRE_REGISTERED_CAP,
        }
        for prefix, metrics in (("base", base_metrics), ("stress", stress_metrics)):
            for key, value in metrics.items():
                summary[f"{prefix}_{key}"] = value
        summary_rows.append(summary)
        base_rows_all.extend(base_rows)
        stress_rows_all.extend(stress_rows)
    return summary_rows, base_rows_all, stress_rows_all


def _period_map(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for row in rows:
        day = str(row.get("signal_date") or "")
        if not day or day in result:
            raise ValueError(f"V33_INVALID_PERIOD_KEY:{day}")
        result[day] = row
    return result


def _paired_rows(
    fixed_base_rows: Sequence[Mapping[str, object]],
    nested_rows: Sequence[Mapping[str, object]],
    *,
    caps: Sequence[int],
    repetitions: int,
    block_months: int,
    seed: int,
) -> list[dict[str, object]]:
    nested = _period_map(nested_rows)
    output: list[dict[str, object]] = []
    for cap in caps:
        fixed = _period_map(
            [
                row
                for row in fixed_base_rows
                if int(row.get("fixed_replacement_cap", -1)) == cap
            ]
        )
        stats = v30._paired_delta_stats(
            fixed,
            nested,
            repetitions=repetitions,
            block_months=block_months,
            seed=seed + cap,
        )
        output.append(
            {
                "fixed_replacement_cap": cap,
                "pre_registered_cap": cap == PRE_REGISTERED_CAP,
                "baseline": "V32_1_NESTED_BLOCKWISE_CAP_SELECTOR",
                **stats,
            }
        )
    return output


def _decision_rows(
    summary_rows: Sequence[Mapping[str, object]],
    paired_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str]:
    pair_by_cap = {
        int(row["fixed_replacement_cap"]): row for row in paired_rows
    }
    decisions: list[dict[str, object]] = []
    for row in summary_rows:
        cap = int(row["fixed_replacement_cap"])
        paired = pair_by_cap[cap]
        gates = {
            "base_relative_total_return_positive": _finite(
                row.get("base_relative_total_return"), name="base_relative"
            )
            > 0.0,
            "stress_relative_total_return_positive": _finite(
                row.get("stress_relative_total_return"), name="stress_relative"
            )
            > 0.0,
            "leave_best_period_out_relative_positive": _finite(
                row.get("base_leave_best_period_out_relative_total_return"),
                name="leave_best_relative",
            )
            > 0.0,
            "mean_turnover_at_most_half": _finite(
                row.get("base_mean_turnover"), name="mean_turnover"
            )
            <= 0.50,
            "paired_probability_vs_nested_at_least_080": _finite(
                paired.get("bootstrap_probability_delta_positive"),
                name="paired_probability",
            )
            >= 0.80,
            "leave_best_3_delta_vs_nested_positive": _finite(
                paired.get("leave_best_3_mean_net_excess_delta"),
                name="leave_best_3_delta",
            )
            > 0.0,
        }
        sensitivity_passed = all(gates.values())
        future_freeze_candidate = sensitivity_passed and cap == PRE_REGISTERED_CAP
        decisions.append(
            {
                "fixed_replacement_cap": cap,
                "pre_registered_cap": cap == PRE_REGISTERED_CAP,
                **gates,
                "sensitivity_gate_passed": sensitivity_passed,
                "future_holdout_freeze_candidate": future_freeze_candidate,
                "failed_gates": "|".join(
                    name for name, value in gates.items() if not value
                ),
                "historical_promotion_allowed": False,
                "research_eligible": False,
                "live_capital_approved": False,
                "actionable": False,
            }
        )
    cap3 = next(
        row for row in decisions
        if int(row["fixed_replacement_cap"]) == PRE_REGISTERED_CAP
    )
    recommendation = (
        "FREEZE_C3_FIXED_CAP_3_FOR_FUTURE_PAPER_HOLDOUT_ONLY"
        if bool(cap3["future_holdout_freeze_candidate"])
        else "KEEP_C3_NESTED_REFERENCE_AND_REDESIGN_TURNOVER_POLICY"
    )
    return decisions, recommendation


def run_v33(
    *,
    v32_artifact_zip: Path,
    output_dir: Path,
    expected_v32_sha256: str | None = None,
    caps: Sequence[int] = DEFAULT_CAPS,
    bootstrap_repetitions: int = 2000,
    bootstrap_block_months: int = 3,
    seed: int = 20260803,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V33_OUTPUT_EXISTS:{destination}")
    normalized_caps = _normalize_caps(caps)
    if bootstrap_repetitions < 100 or bootstrap_block_months < 1:
        raise ValueError("V33_BOOTSTRAP_CONFIG_INVALID")

    source_report, predictions, outer_rows, source_metadata = _load_artifact(
        v32_artifact_zip,
        expected_sha256=expected_v32_sha256,
    )
    nested_rows = _official_nested_rows(outer_rows)
    outer_dates = [str(row["signal_date"]) for row in nested_rows]
    c3_predictions = _c3_predictions(predictions, outer_dates)
    cost = _cost_from_report(source_report)

    summary_rows, base_rows, stress_rows = _fixed_cap_rows(
        c3_predictions,
        caps=normalized_caps,
        cost=cost,
    )
    paired_rows = _paired_rows(
        base_rows,
        nested_rows,
        caps=normalized_caps,
        repetitions=bootstrap_repetitions,
        block_months=bootstrap_block_months,
        seed=seed,
    )
    decision_rows, recommendation = _decision_rows(
        summary_rows,
        paired_rows,
    )

    destination.mkdir(parents=True)
    try:
        _write_csv(destination / "fixed_cap_summary_v33.csv", summary_rows)
        _write_csv(destination / "fixed_cap_periods_v33.csv", base_rows)
        _write_csv(destination / "fixed_cap_stress_periods_v33.csv", stress_rows)
        _write_csv(destination / "paired_vs_nested_v33.csv", paired_rows)
        _write_csv(destination / "decision_gates_v33.csv", decision_rows)

        cap3_summary = next(
            dict(row) for row in summary_rows
            if int(row["fixed_replacement_cap"]) == PRE_REGISTERED_CAP
        )
        cap3_paired = next(
            dict(row) for row in paired_rows
            if int(row["fixed_replacement_cap"]) == PRE_REGISTERED_CAP
        )
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": "POST_V32_C3_FIXED_TURNOVER_CAP_STABILITY_AUDIT",
            "source_v32_1": source_metadata,
            "source_v32_1_recommendation": source_report.get("recommendation"),
            "source_v32_1_outer_test_first_date": outer_dates[0],
            "source_v32_1_outer_test_last_date": outer_dates[-1],
            "source_v32_1_outer_test_period_count": len(outer_dates),
            "model": FROZEN_MODEL,
            "breadth": 10,
            "caps": list(normalized_caps),
            "pre_registered_cap": PRE_REGISTERED_CAP,
            "pre_registered_cap_provenance": (
                "V11_MAX_VOLUNTARY_REPLACEMENTS_FROZEN_BEFORE_V32_REVIEW"
            ),
            "cost_contract": cost.as_contract(),
            "fixed_cap_summary_rows": summary_rows,
            "paired_vs_nested_rows": paired_rows,
            "decision_rows": decision_rows,
            "cap3_summary": cap3_summary,
            "cap3_paired_vs_nested": cap3_paired,
            "recommendation": recommendation,
            "predictive_model_retrained": False,
            "rankings_changed": False,
            "historical_grid_is_post_selection_sensitivity": True,
            "future_holdout_clock_reset": False,
            "historical_promotion_allowed": False,
            "policy_freeze_is_for_future_paper_holdout_only": (
                recommendation
                == "FREEZE_C3_FIXED_CAP_3_FOR_FUTURE_PAPER_HOLDOUT_ONLY"
            ),
            "exact_cash_ledger_pnl_computed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "actionable": False,
            "data_blockers_unchanged": list(
                source_report.get("data_blockers_unchanged", [])
            ),
        }
        _write_json(destination / REPORT_FILE, report)
        return {**report, "output_dir": str(destination)}
    except Exception:
        for path in sorted(destination.glob("*")):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise


def _parse_int_list(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.turnover_policy_stability_v33"
    )
    parser.add_argument("--v32-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v32-sha256")
    parser.add_argument("--caps", type=_parse_int_list, default=DEFAULT_CAPS)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bootstrap-block-months", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260803)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v33(
            v32_artifact_zip=args.v32_artifact_zip,
            output_dir=args.output_dir,
            expected_v32_sha256=args.expected_v32_sha256,
            caps=args.caps,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            seed=args.seed,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                    "live_capital_approved": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_dir": result["output_dir"],
                "recommendation": result["recommendation"],
                "cap3_summary": result["cap3_summary"],
                "cap3_paired_vs_nested": result["cap3_paired_vs_nested"],
                "live_capital_approved": False,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "FROZEN_MODEL",
    "PRE_REGISTERED_CAP",
    "DEFAULT_CAPS",
    "_load_artifact",
    "_normalize_caps",
    "_decision_rows",
    "run_v33",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
