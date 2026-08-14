"""Freeze the V33 C3/Top-10/fixed-cap-3 policy for a future paper holdout.

V34 is governance and monitoring infrastructure. It verifies the immutable V33
artifact, creates a deterministic policy bundle, and evaluates only observations
whose signal timestamp is strictly after the official freeze timestamp.

It never promotes historical evidence, approves live capital, or claims an exact
cash-ledger backtest.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Mapping, Sequence
import zipfile

SCHEMA_VERSION = "future_paper_holdout_freeze_v34"
POLICY_SCHEMA_VERSION = "frozen_c3_cap3_future_paper_policy_v34"
MONITOR_SCHEMA_VERSION = "future_paper_holdout_monitor_v34"
REPORT_FILE = "future_paper_holdout_freeze_v34.json"
POLICY_FILE = "frozen_policy_v34.json"
OBSERVATION_TEMPLATE_FILE = "future_holdout_observations_v34.csv"

EXPECTED_V33_SCHEMA = "turnover_policy_stability_v33"
EXPECTED_V33_REPORT = "turnover_policy_stability_v33.json"
EXPECTED_V33_MANIFEST = "analysis_bundle_manifest_v33.json"
EXPECTED_V33_DECISIONS = "decision_gates_v33.csv"
EXPECTED_RECOMMENDATION = "FREEZE_C3_FIXED_CAP_3_FOR_FUTURE_PAPER_HOLDOUT_ONLY"
FROZEN_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
FROZEN_BREADTH = 10
FROZEN_CAP = 3
MINIMUM_FUTURE_OBSERVATIONS = 12
VN_TZ = timezone(timedelta(hours=7))

DEFAULT_KILL_SWITCH = {
    "rolling_window": 6,
    "minimum_observations": 6,
    "mean_rank_ic_below": 0.0,
    "positive_rank_ic_ratio_below": 0.40,
    "average_net_excess_below": 0.0,
    "relative_drawdown_at_or_below": -0.12,
    "turnover_above": 0.60,
    "turnover_consecutive_periods": 3,
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    Path(path).write_bytes(_json_bytes(value))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fields),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(
        buffer.getvalue(),
        encoding="utf-8-sig",
        newline="",
    )


def _read_csv_bytes(value: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value.decode("utf-8-sig"))))


def _safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"V34_UNSAFE_ZIP_MEMBER:{name}")
    return path.name


def _finite(value: object, *, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"V34_NOT_NUMERIC:{name}") from exc
    if not math.isfinite(result):
        raise ValueError(f"V34_NOT_FINITE:{name}")
    return result


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _explicit_bool(value: object, *, name: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true"}:
        return True
    if text in {"0", "false"}:
        return False
    raise ValueError(f"V34_BOOLEAN_REQUIRED:{name}")


def _parse_date(value: object, *, name: str) -> date:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise ValueError(f"V34_INVALID_DATE:{name}") from exc


def _parse_timestamp(value: object, *, name: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"V34_INVALID_TIMESTAMP:{name}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"V34_TIMESTAMP_TIMEZONE_REQUIRED:{name}")
    return result


def _load_flat_zip(path: Path) -> tuple[dict[str, tuple[str, bytes]], str]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"V34_SOURCE_ZIP_NOT_FOUND:{source}")
    members: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V34_SOURCE_ZIP_CRC_ERROR:{bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_basename(info.filename)
            if basename in members:
                raise ValueError(f"V34_DUPLICATE_ZIP_BASENAME:{basename}")
            members[basename] = (info.filename, archive.read(info))
    return members, _sha256(source)


def _verify_analysis_manifest(
    members: Mapping[str, tuple[str, bytes]],
) -> dict[str, object]:
    if EXPECTED_V33_MANIFEST not in members:
        raise ValueError("V34_V33_MANIFEST_MISSING")
    manifest_bytes = members[EXPECTED_V33_MANIFEST][1]
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("V34_V33_MANIFEST_OBJECT_REQUIRED")
    if manifest.get("status") != "SUCCESS":
        raise ValueError("V34_V33_MANIFEST_STATUS_NOT_SUCCESS")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("V34_V33_MANIFEST_FILES_INVALID")
    for entry in files:
        if not isinstance(entry, Mapping):
            raise ValueError("V34_V33_MANIFEST_ENTRY_INVALID")
        name = _safe_basename(str(entry.get("path") or ""))
        if name not in members:
            raise ValueError(f"V34_V33_MANIFEST_FILE_MISSING:{name}")
        payload = members[name][1]
        if len(payload) != int(entry.get("size_bytes", -1)):
            raise ValueError(f"V34_V33_MANIFEST_SIZE_MISMATCH:{name}")
        if _bytes_sha256(payload) != str(entry.get("sha256") or ""):
            raise ValueError(f"V34_V33_MANIFEST_HASH_MISMATCH:{name}")
    return manifest


def _load_v33(
    path: Path,
    *,
    expected_sha256: str | None,
) -> tuple[dict[str, object], list[dict[str, str]], dict[str, object]]:
    members, artifact_sha = _load_flat_zip(path)
    if expected_sha256 and artifact_sha != expected_sha256:
        raise ValueError("V34_V33_ARTIFACT_SHA256_MISMATCH")
    required = {
        EXPECTED_V33_REPORT,
        EXPECTED_V33_MANIFEST,
        EXPECTED_V33_DECISIONS,
    }
    missing = required - set(members)
    if missing:
        raise ValueError(
            "V34_V33_REQUIRED_FILES_MISSING:" + "|".join(sorted(missing))
        )
    manifest = _verify_analysis_manifest(members)
    report_bytes = members[EXPECTED_V33_REPORT][1]
    report = json.loads(report_bytes.decode("utf-8-sig"))
    if not isinstance(report, dict):
        raise ValueError("V34_V33_REPORT_OBJECT_REQUIRED")
    decisions = _read_csv_bytes(members[EXPECTED_V33_DECISIONS][1])
    metadata = {
        "artifact_zip": str(Path(path).resolve()),
        "artifact_zip_sha256": artifact_sha,
        "report_member": members[EXPECTED_V33_REPORT][0],
        "report_sha256": _bytes_sha256(report_bytes),
        "decision_gates_sha256": _bytes_sha256(
            members[EXPECTED_V33_DECISIONS][1]
        ),
        "analysis_manifest_sha256": _bytes_sha256(
            members[EXPECTED_V33_MANIFEST][1]
        ),
        "manifest_file_count_excluding_manifest": manifest.get(
            "file_count_excluding_manifest"
        ),
    }
    return report, decisions, metadata


def _validate_v33_freeze_candidate(
    report: Mapping[str, object],
    decisions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if report.get("schema_version") != EXPECTED_V33_SCHEMA:
        raise ValueError("V34_V33_SCHEMA_MISMATCH")
    if report.get("status") != "SUCCESS":
        raise ValueError("V34_V33_STATUS_NOT_SUCCESS")
    if str(report.get("model") or "") != FROZEN_MODEL:
        raise ValueError("V34_V33_MODEL_MISMATCH")
    if int(report.get("breadth", 0) or 0) != FROZEN_BREADTH:
        raise ValueError("V34_V33_BREADTH_MISMATCH")
    if int(report.get("pre_registered_cap", -1) or -1) != FROZEN_CAP:
        raise ValueError("V34_V33_PRE_REGISTERED_CAP_MISMATCH")
    if report.get("recommendation") != EXPECTED_RECOMMENDATION:
        raise ValueError("V34_V33_RECOMMENDATION_MISMATCH")
    if report.get("historical_promotion_allowed") is not False:
        raise ValueError("V34_V33_HISTORICAL_PROMOTION_MUST_BE_FALSE")
    if report.get("live_capital_approved") is not False:
        raise ValueError("V34_V33_LIVE_APPROVAL_MUST_BE_FALSE")
    if report.get("exact_cash_ledger_pnl_computed") is not False:
        raise ValueError("V34_V33_EXACT_LEDGER_FLAG_INVALID")

    matches = [
        dict(row)
        for row in decisions
        if int(float(row.get("fixed_replacement_cap", -1) or -1))
        == FROZEN_CAP
    ]
    if len(matches) != 1:
        raise ValueError("V34_V33_CAP3_DECISION_NOT_UNIQUE")
    cap3 = matches[0]
    if not _truthy(cap3.get("pre_registered_cap")):
        raise ValueError("V34_V33_CAP3_NOT_PRE_REGISTERED")
    if not _truthy(cap3.get("sensitivity_gate_passed")):
        raise ValueError("V34_V33_CAP3_SENSITIVITY_GATE_FAILED")
    if not _truthy(cap3.get("future_holdout_freeze_candidate")):
        raise ValueError("V34_V33_CAP3_NOT_FUTURE_FREEZE_CANDIDATE")
    if _truthy(cap3.get("historical_promotion_allowed")):
        raise ValueError("V34_V33_CAP3_HISTORICAL_PROMOTION_INVALID")
    if any(
        _truthy(row.get("future_holdout_freeze_candidate"))
        and int(float(row.get("fixed_replacement_cap", -1) or -1))
        != FROZEN_CAP
        for row in decisions
    ):
        raise ValueError("V34_V33_MULTIPLE_FUTURE_FREEZE_CANDIDATES")

    summary = report.get("cap3_summary")
    paired = report.get("cap3_paired_vs_nested")
    if not isinstance(summary, Mapping) or not isinstance(paired, Mapping):
        raise ValueError("V34_V33_CAP3_EVIDENCE_MISSING")
    required_positive = (
        "base_relative_total_return",
        "stress_relative_total_return",
        "base_leave_best_period_out_relative_total_return",
    )
    if any(_finite(summary.get(name), name=name) <= 0.0 for name in required_positive):
        raise ValueError("V34_V33_CAP3_ROBUSTNESS_NOT_POSITIVE")
    if _finite(
        paired.get("bootstrap_probability_delta_positive"),
        name="bootstrap_probability_delta_positive",
    ) < 0.80:
        raise ValueError("V34_V33_CAP3_BOOTSTRAP_GATE_FAILED")
    if _finite(
        paired.get("leave_best_3_mean_net_excess_delta"),
        name="leave_best_3_mean_net_excess_delta",
    ) <= 0.0:
        raise ValueError("V34_V33_CAP3_LEAVE3_GATE_FAILED")
    return {
        "decision_row": cap3,
        "summary": dict(summary),
        "paired_vs_nested": dict(paired),
    }


def _policy_core(
    *,
    source: Mapping[str, object],
    evidence: Mapping[str, object],
    report: Mapping[str, object],
    freeze_timestamp: datetime,
    exclude_signal_through: date,
) -> dict[str, object]:
    frozen_at = freeze_timestamp.astimezone(VN_TZ)
    if exclude_signal_through > frozen_at.date():
        raise ValueError("V34_EXCLUDE_SIGNAL_DATE_AFTER_FREEZE")
    source_last_oos = _parse_date(
        report.get("source_v32_1_outer_test_last_date"),
        name="source_v32_1_outer_test_last_date",
    )
    if source_last_oos > exclude_signal_through:
        raise ValueError("V34_EXCLUDE_SIGNAL_DATE_BEFORE_SOURCE_OOS_END")
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "operations_schema_version": SCHEMA_VERSION,
        "status": "FROZEN_FOR_FUTURE_PAPER_HOLDOUT",
        "frozen_at": frozen_at.isoformat(),
        "frozen_timezone": "Asia/Ho_Chi_Minh",
        "source": dict(source),
        "policy": {
            "model": FROZEN_MODEL,
            "breadth": FROZEN_BREADTH,
            "fixed_voluntary_replacement_cap": FROZEN_CAP,
            "rebalance_frequency": "MONTHLY",
            "ranking_locked": True,
            "feature_definition_locked": True,
            "model_retraining_allowed_inside_holdout": False,
            "model_switching_allowed": False,
            "dynamic_breadth_allowed": False,
            "dynamic_replacement_cap_allowed": False,
            "historical_grid_selection_allowed": False,
            "eligibility_contract": "V22_PORTFOLIO_ELIGIBLE_TRUE",
        },
        "holdout_contract": {
            "signal_timestamp_rule": "STRICTLY_AFTER_FROZEN_AT",
            "known_pre_freeze_signals_excluded_through": (
                exclude_signal_through.isoformat()
            ),
            "historical_observations_counted": False,
            "pre_freeze_forward_snapshots_counted": False,
            "minimum_completed_monthly_observations": (
                MINIMUM_FUTURE_OBSERVATIONS
            ),
            "label_horizon_sessions": 20,
            "label_must_be_complete": True,
            "observation_must_be_recorded_after_label_end": True,
            "missing_months_must_not_be_backfilled_with_historical_data": True,
            "holdout_clock_started": True,
            "holdout_clock_reset_from_historical": False,
        },
        "historical_evidence": {
            "v33_recommendation": report.get("recommendation"),
            "cap3_summary": dict(evidence["summary"]),
            "cap3_paired_vs_nested": dict(evidence["paired_vs_nested"]),
            "historical_promotion_allowed": False,
            "historical_grid_is_post_selection_sensitivity": True,
        },
        "kill_switch": dict(DEFAULT_KILL_SWITCH),
        "permissions": {
            "paper_watchlist_allowed": True,
            "paper_trading_allowed": True,
            "historical_promotion_allowed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "actionable": False,
        },
        "known_limitations": {
            "exact_cash_ledger_pnl_computed": False,
            "exact_t1_open_execution_applied": False,
            "lot_size_100_applied": False,
            "inverse_volatility_allocation_applied": False,
            "single_name_cap_15_percent_applied": False,
            "sector_cap_25_percent_applied": False,
            "corporate_actions_complete": False,
            "price_basis_confirmed": False,
            "point_in_time_universe_complete": False,
            "survivorship_bias_resolved": False,
        },
        "change_control": {
            "requires_new_policy_version": [
                "MODEL_CHANGE",
                "FEATURE_CHANGE",
                "RANKING_CHANGE",
                "TOP_K_CHANGE",
                "REPLACEMENT_CAP_CHANGE",
                "ELIGIBILITY_CHANGE",
                "REBALANCE_FREQUENCY_CHANGE",
                "KILL_SWITCH_THRESHOLD_CHANGE",
            ],
            "allowed_without_new_policy_version": [
                "BUG_FIX_WITH_NO_SCORE_SELECTION_OR_RETURN_CHANGE",
                "DATA_CONNECTOR_RELIABILITY_FIX",
                "REPORTING_ONLY_CHANGE",
            ],
        },
    }


def freeze_policy(
    *,
    v33_artifact_zip: Path,
    output_dir: Path,
    freeze_timestamp: datetime,
    exclude_signal_through: date,
    expected_v33_sha256: str | None = None,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V34_OUTPUT_EXISTS:{destination}")
    report, decisions, source = _load_v33(
        Path(v33_artifact_zip),
        expected_sha256=expected_v33_sha256,
    )
    evidence = _validate_v33_freeze_candidate(report, decisions)
    core = _policy_core(
        source=source,
        evidence=evidence,
        report=report,
        freeze_timestamp=freeze_timestamp,
        exclude_signal_through=exclude_signal_through,
    )
    policy_hash = _bytes_sha256(_json_bytes(core))
    policy = {**core, "policy_id": f"c3-top10-cap3-{policy_hash[:16]}"}
    destination.mkdir(parents=True)
    _write_json(destination / POLICY_FILE, policy)
    observation_fields = (
        "policy_id",
        "signal_timestamp",
        "label_end",
        "observation_recorded_at",
        "rank_ic",
        "net_excess_return",
        "turnover",
        "relative_nav",
        "contract_ok",
        "data_quality_ok",
        "score_hash_match",
        "selection_policy_match",
        "exact_cash_ledger_pnl_computed",
        "notes",
    )
    _write_csv(destination / OBSERVATION_TEMPLATE_FILE, [], observation_fields)
    report_out = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "policy_id": policy["policy_id"],
        "policy_file": POLICY_FILE,
        "observation_template_file": OBSERVATION_TEMPLATE_FILE,
        "frozen_at": policy["frozen_at"],
        "known_pre_freeze_signals_excluded_through": (
            exclude_signal_through.isoformat()
        ),
        "first_countable_signal_rule": "SIGNAL_TIMESTAMP_STRICTLY_AFTER_FROZEN_AT",
        "minimum_future_observations": MINIMUM_FUTURE_OBSERVATIONS,
        "source_v33": source,
        "recommendation": "START_FUTURE_PAPER_HOLDOUT_NO_HISTORICAL_BACKFILL",
        "paper_trading_allowed": True,
        "historical_promotion_allowed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "exact_cash_ledger_pnl_computed": False,
        "actionable": False,
    }
    _write_json(destination / REPORT_FILE, report_out)
    return {**report_out, "output_dir": str(destination), "policy": policy}


def evaluate_observations(
    observations: Sequence[Mapping[str, object]],
    *,
    policy: Mapping[str, object],
) -> dict[str, object]:
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("V34_POLICY_SCHEMA_MISMATCH")
    if policy.get("status") != "FROZEN_FOR_FUTURE_PAPER_HOLDOUT":
        raise ValueError("V34_POLICY_NOT_FROZEN")
    policy_id = str(policy.get("policy_id") or "")
    if not policy_id:
        raise ValueError("V34_POLICY_ID_MISSING")
    frozen_at = _parse_timestamp(policy.get("frozen_at"), name="frozen_at")
    holdout = policy.get("holdout_contract")
    if not isinstance(holdout, Mapping):
        raise ValueError("V34_HOLDOUT_CONTRACT_MISSING")
    minimum = int(
        holdout.get(
            "minimum_completed_monthly_observations",
            MINIMUM_FUTURE_OBSERVATIONS,
        )
    )
    if minimum < 1:
        raise ValueError("V34_MINIMUM_OBSERVATIONS_INVALID")

    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in observations:
        row_policy = str(raw.get("policy_id") or "")
        if row_policy != policy_id:
            raise ValueError("V34_OBSERVATION_POLICY_MISMATCH")
        signal = _parse_timestamp(
            raw.get("signal_timestamp"),
            name="signal_timestamp",
        )
        signal_key = signal.isoformat()
        if signal_key in seen:
            raise ValueError(f"V34_DUPLICATE_SIGNAL:{signal_key}")
        seen.add(signal_key)
        if signal <= frozen_at:
            raise ValueError(f"V34_SIGNAL_NOT_STRICTLY_FUTURE:{signal_key}")
        label_end = _parse_date(raw.get("label_end"), name="label_end")
        if label_end <= signal.date():
            raise ValueError("V34_LABEL_END_NOT_AFTER_SIGNAL")
        recorded = _parse_timestamp(
            raw.get("observation_recorded_at"),
            name="observation_recorded_at",
        )
        if recorded.date() < label_end:
            raise ValueError("V34_OBSERVATION_RECORDED_BEFORE_LABEL_END")
        turnover = _finite(raw.get("turnover"), name="turnover")
        if turnover < 0.0 or turnover > 1.0:
            raise ValueError("V34_TURNOVER_OUT_OF_RANGE")
        relative_nav = _finite(raw.get("relative_nav"), name="relative_nav")
        if relative_nav <= 0.0:
            raise ValueError("V34_RELATIVE_NAV_NON_POSITIVE")
        normalized.append(
            {
                "policy_id": policy_id,
                "signal_timestamp": signal_key,
                "label_end": label_end.isoformat(),
                "observation_recorded_at": recorded.isoformat(),
                "rank_ic": _finite(raw.get("rank_ic"), name="rank_ic"),
                "net_excess_return": _finite(
                    raw.get("net_excess_return"),
                    name="net_excess_return",
                ),
                "turnover": turnover,
                "relative_nav": relative_nav,
                "contract_ok": _explicit_bool(
                    raw.get("contract_ok"),
                    name="contract_ok",
                ),
                "data_quality_ok": _explicit_bool(
                    raw.get("data_quality_ok"),
                    name="data_quality_ok",
                ),
                "score_hash_match": _explicit_bool(
                    raw.get("score_hash_match"),
                    name="score_hash_match",
                ),
                "selection_policy_match": _explicit_bool(
                    raw.get("selection_policy_match"),
                    name="selection_policy_match",
                ),
                "exact_cash_ledger_pnl_computed": _explicit_bool(
                    raw.get("exact_cash_ledger_pnl_computed", False),
                    name="exact_cash_ledger_pnl_computed",
                ),
                "notes": str(raw.get("notes") or ""),
            }
        )
    normalized.sort(key=lambda row: str(row["signal_timestamp"]))

    thresholds_raw = policy.get("kill_switch")
    thresholds = (
        dict(thresholds_raw)
        if isinstance(thresholds_raw, Mapping)
        else dict(DEFAULT_KILL_SWITCH)
    )
    window = int(thresholds.get("rolling_window", 6))
    operational_minimum = int(thresholds.get("minimum_observations", 6))
    turnover_periods = int(
        thresholds.get("turnover_consecutive_periods", 3)
    )
    if window < 1 or operational_minimum < 1 or turnover_periods < 1:
        raise ValueError("V34_KILL_SWITCH_THRESHOLD_INVALID")

    peak = 0.0
    worst_drawdown = 0.0
    for row in normalized:
        nav = float(row["relative_nav"])
        peak = max(peak, nav)
        drawdown = nav / peak - 1.0 if peak > 0.0 else 0.0
        row["relative_drawdown"] = drawdown
        worst_drawdown = min(worst_drawdown, drawdown)

    recent = normalized[-window:]
    rank_values = [float(row["rank_ic"]) for row in recent]
    excess_values = [float(row["net_excess_return"]) for row in recent]
    mean_ic = fmean(rank_values) if rank_values else 0.0
    positive_ic_ratio = (
        sum(value > 0.0 for value in rank_values) / len(rank_values)
        if rank_values
        else 0.0
    )
    average_excess = fmean(excess_values) if excess_values else 0.0
    recent_turnover = normalized[-turnover_periods:]

    triggers: list[str] = []
    contract_fields = (
        "contract_ok",
        "data_quality_ok",
        "score_hash_match",
        "selection_policy_match",
    )
    if any(
        not bool(row[field])
        for row in normalized
        for field in contract_fields
    ):
        triggers.append("POLICY_OR_DATA_CONTRACT_VIOLATION")
    if worst_drawdown <= float(
        thresholds.get("relative_drawdown_at_or_below", -0.12)
    ):
        triggers.append("RELATIVE_DRAWDOWN_LIMIT")
    if len(normalized) >= operational_minimum:
        if mean_ic < float(thresholds.get("mean_rank_ic_below", 0.0)):
            triggers.append("ROLLING_MEAN_IC_NEGATIVE")
        if positive_ic_ratio < float(
            thresholds.get("positive_rank_ic_ratio_below", 0.40)
        ):
            triggers.append("ROLLING_POSITIVE_IC_RATIO_LOW")
        if average_excess < float(
            thresholds.get("average_net_excess_below", 0.0)
        ):
            triggers.append("ROLLING_NET_EXCESS_NEGATIVE")
    if (
        len(recent_turnover) >= turnover_periods
        and all(
            float(row["turnover"])
            > float(thresholds.get("turnover_above", 0.60))
            for row in recent_turnover
        )
    ):
        triggers.append("TURNOVER_PERSISTENTLY_HIGH")

    completed = len(normalized) >= minimum
    blocked = bool(triggers)
    status = (
        "MODEL_UNDER_REVIEW"
        if blocked
        else "PAPER_HOLDOUT_COMPLETE_TECHNICAL_ONLY"
        if completed
        else "PAPER_WARMUP"
    )
    return {
        "schema_version": MONITOR_SCHEMA_VERSION,
        "status": status,
        "policy_id": policy_id,
        "future_observation_count": len(normalized),
        "minimum_future_observations": minimum,
        "future_holdout_complete": completed,
        "rolling_window_used": len(recent),
        "rolling_mean_rank_ic": mean_ic,
        "rolling_positive_rank_ic_ratio": positive_ic_ratio,
        "rolling_average_net_excess_return": average_excess,
        "worst_relative_drawdown": worst_drawdown,
        "latest_relative_nav": (
            float(normalized[-1]["relative_nav"]) if normalized else 1.0
        ),
        "latest_turnover": (
            float(normalized[-1]["turnover"]) if normalized else 0.0
        ),
        "kill_switch_triggers": triggers,
        "block_new_paper_positions": blocked,
        "historical_observations_counted": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "actionable": False,
        "observations": normalized,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.future_paper_holdout_freeze_v34"
    )
    parser.add_argument("--v33-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v33-sha256")
    parser.add_argument("--freeze-timestamp", required=True)
    parser.add_argument("--exclude-signal-through", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = freeze_policy(
            v33_artifact_zip=args.v33_artifact_zip,
            output_dir=args.output_dir,
            freeze_timestamp=_parse_timestamp(
                args.freeze_timestamp,
                name="freeze_timestamp",
            ),
            exclude_signal_through=_parse_date(
                args.exclude_signal_through,
                name="exclude_signal_through",
            ),
            expected_v33_sha256=args.expected_v33_sha256,
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
                "policy_id": result["policy_id"],
                "frozen_at": result["frozen_at"],
                "output_dir": result["output_dir"],
                "recommendation": result["recommendation"],
                "paper_trading_allowed": True,
                "live_capital_approved": False,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "POLICY_SCHEMA_VERSION",
    "MONITOR_SCHEMA_VERSION",
    "REPORT_FILE",
    "POLICY_FILE",
    "OBSERVATION_TEMPLATE_FILE",
    "FROZEN_MODEL",
    "FROZEN_BREADTH",
    "FROZEN_CAP",
    "MINIMUM_FUTURE_OBSERVATIONS",
    "freeze_policy",
    "evaluate_observations",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
