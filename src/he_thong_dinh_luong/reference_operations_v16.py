"""Operational controls for the frozen Model Lab v15 reference candidate.

This module does not retrain or tune the reference model. It provides three
fail-closed workflows:

* freeze a verified v15 Model Lab artifact into an immutable reference policy;
* audit whether a longer point-in-time historical dataset is ready for the
  unchanged v15 protocol;
* evaluate paper-trading observations and publish a deterministic kill-switch
  decision.

Live capital is never approved by this module.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path
import shutil
from statistics import fmean
from typing import Iterable, Mapping, Sequence
from zipfile import BadZipFile, ZipFile

SCHEMA_VERSION = "vn_quant_reference_operations_v16"
REFERENCE_POLICY_SCHEMA = "vn_quant_reference_policy_v16"
PAPER_MONITOR_SCHEMA = "vn_quant_paper_monitor_v16"
HISTORY_READINESS_SCHEMA = "vn_quant_historical_extension_readiness_v16"
EXPECTED_MODEL_LAB_SCHEMA = "vn_quant_model_lab_upgrade_v15"
EXPECTED_REFERENCE_STATUS = "HISTORICALLY_VALIDATED_REFERENCE"
NO_MODEL = "NO_MODEL_APPROVED"
VN_TZ = timezone(timedelta(hours=7))
SIGNAL_TIME = time(15, 0)

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


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _csv_bytes(
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fields),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    ]


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV_HEADER_MISSING:{path}")
        return [dict(row) for row in reader], tuple(reader.fieldnames)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _explicit_bool(value: object, name: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true"}:
        return True
    if text in {"0", "false"}:
        return False
    raise ValueError(f"{name}_BOOLEAN_REQUIRED")


def _finite_float(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}_NOT_NUMERIC") from exc
    if not isfinite(result):
        raise ValueError(f"{name}_NOT_FINITE")
    return result


def _parse_date(value: object, name: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{name}_INVALID_DATE") from exc


def _parse_datetime(value: object, name: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name}_INVALID_DATETIME") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name}_TIMEZONE_REQUIRED")
    return result


def _publish_immutable(destination: Path, files: Mapping[str, bytes]) -> None:
    output = Path(destination)
    if output.exists():
        raise FileExistsError(f"OUTPUT_DIR_EXISTS:{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        for name, payload in sorted(files.items()):
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        staging.replace(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _verified_archive(path: Path) -> dict[str, object]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("MODEL_LAB_ARCHIVE_NOT_FOUND")
    try:
        with ZipFile(source) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f"MODEL_LAB_ARCHIVE_CRC_ERROR:{bad}")
            names = set(archive.namelist())
            required = {
                "manifest.json",
                "model_lab_summary.json",
                "nested_model_historical_validation_v15.csv",
                "nested_model_policy_selection_v15.csv",
                "nested_model_validation_contract_v15.csv",
                "dnse_cost_scenarios_v13.csv",
            }
            missing = sorted(required - names)
            if missing:
                raise ValueError(
                    "MODEL_LAB_ARCHIVE_REQUIRED_FILE_MISSING:"
                    + "|".join(missing)
                )
            manifest_payload = archive.read("manifest.json")
            summary_payload = archive.read("model_lab_summary.json")
            manifest = json.loads(manifest_payload.decode("utf-8-sig"))
            summary = json.loads(summary_payload.decode("utf-8-sig"))
            if not isinstance(manifest, dict) or not isinstance(summary, dict):
                raise ValueError("MODEL_LAB_ARCHIVE_JSON_CONTRACT_INVALID")
            files = manifest.get("files")
            if not isinstance(files, Mapping) or not files:
                raise ValueError("MODEL_LAB_MANIFEST_FILES_INVALID")
            for name, contract in files.items():
                if name not in names:
                    raise ValueError(f"MODEL_LAB_MANIFEST_FILE_MISSING:{name}")
                if not isinstance(contract, Mapping):
                    raise ValueError(f"MODEL_LAB_MANIFEST_ENTRY_INVALID:{name}")
                payload = archive.read(name)
                expected_hash = str(contract.get("sha256") or "")
                expected_size = int(contract.get("size", -1))
                if _sha_bytes(payload) != expected_hash:
                    raise ValueError(f"MODEL_LAB_MANIFEST_HASH_MISMATCH:{name}")
                if len(payload) != expected_size:
                    raise ValueError(f"MODEL_LAB_MANIFEST_SIZE_MISMATCH:{name}")
            if manifest.get("credentials_recorded") is True:
                raise ValueError("MODEL_LAB_ARCHIVE_RECORDS_CREDENTIALS")
            payloads = {
                name: archive.read(name)
                for name in required
                if name != "manifest.json"
            }
    except BadZipFile as exc:
        raise ValueError("MODEL_LAB_ARCHIVE_INVALID_ZIP") from exc
    return {
        "source_path": source,
        "source_sha256": _sha_file(source),
        "manifest_sha256": _sha_bytes(manifest_payload),
        "manifest": manifest,
        "summary": summary,
        "payloads": payloads,
    }


def freeze_reference_policy(
    *,
    model_lab_archive: Path,
    output_dir: Path,
    freeze_date: date,
) -> dict[str, object]:
    """Freeze a verified v15 champion into an immutable paper-only policy."""
    verified = _verified_archive(Path(model_lab_archive))
    summary = dict(verified["summary"])
    if summary.get("upgrade_schema_version") != EXPECTED_MODEL_LAB_SCHEMA:
        raise ValueError("REFERENCE_FREEZE_REQUIRES_V15")
    if summary.get("historical_reference_status") != EXPECTED_REFERENCE_STATUS:
        raise ValueError("REFERENCE_FREEZE_STATUS_NOT_VALIDATED")
    if summary.get("historical_reference_gate_passed") is not True:
        raise ValueError("REFERENCE_FREEZE_GATE_NOT_PASSED")
    champion = str(summary.get("historical_reference_model") or "")
    if not champion or champion == NO_MODEL:
        raise ValueError("REFERENCE_FREEZE_CHAMPION_INVALID")
    if summary.get("live_capital_approved") is True:
        raise ValueError("REFERENCE_FREEZE_LIVE_APPROVAL_MUST_BE_FALSE")

    payloads = dict(verified["payloads"])
    comparison = _read_csv_bytes(
        payloads["nested_model_historical_validation_v15.csv"]
    )
    champion_rows = [row for row in comparison if row.get("model") == champion]
    if len(champion_rows) != 1 or not _truthy(champion_rows[0].get("gate_passed")):
        raise ValueError("REFERENCE_FREEZE_CHAMPION_ROW_INVALID")
    champion_row = champion_rows[0]

    contract_rows = _read_csv_bytes(
        payloads["nested_model_validation_contract_v15.csv"]
    )
    if len(contract_rows) != 1:
        raise ValueError("REFERENCE_FREEZE_VALIDATION_CONTRACT_INVALID")
    contract = contract_rows[0]
    required_contract = {
        "evaluation_unit": "MODEL_FAMILY",
        "model_switching_inside_outer_portfolio": "False",
        "inner_selected_parameter": "MAX_VOLUNTARY_REPLACEMENTS",
        "cap_selected_only_from_prior_validation": "True",
        "continuous_holdings_across_outer_blocks": "True",
        "outer_test_blocks_non_overlapping": "True",
    }
    for key, expected in required_contract.items():
        if str(contract.get(key)) != expected:
            raise ValueError(f"REFERENCE_FREEZE_CONTRACT_MISMATCH:{key}")

    selection_rows = [
        row
        for row in _read_csv_bytes(
            payloads["nested_model_policy_selection_v15.csv"]
        )
        if row.get("model") == champion
    ]
    if not selection_rows:
        raise ValueError("REFERENCE_FREEZE_SELECTION_HISTORY_MISSING")
    selection_rows.sort(key=lambda row: (row.get("test_start", ""), row.get("outer_fold", "")))
    selected_caps = [int(row["selected_replacement_cap"]) for row in selection_rows]
    cap_candidates = sorted({
        int(item)
        for row in selection_rows
        for item in str(row.get("candidate_caps") or "").split("|")
        if item.strip()
    })
    if not cap_candidates or any(value < 0 or value > 10 for value in cap_candidates):
        raise ValueError("REFERENCE_FREEZE_CAP_CANDIDATES_INVALID")
    if any(value not in cap_candidates for value in selected_caps):
        raise ValueError("REFERENCE_FREEZE_SELECTED_CAP_INVALID")
    if any(_truthy(row.get("selection_uses_outer_test_labels")) for row in selection_rows):
        raise ValueError("REFERENCE_FREEZE_OUTER_LABEL_LEAKAGE")

    cost_rows = _read_csv_bytes(payloads["dnse_cost_scenarios_v13.csv"])
    costs = {str(row.get("scenario")): row for row in cost_rows}
    if set(costs) != {"BASE", "STRESS"}:
        raise ValueError("REFERENCE_FREEZE_COST_SCENARIOS_INVALID")

    nested = summary.get("nested_model_validation_v15")
    if not isinstance(nested, Mapping):
        raise ValueError("REFERENCE_FREEZE_NESTED_SUMMARY_MISSING")
    backtest = summary.get("backtest_contract")
    backtest = dict(backtest) if isinstance(backtest, Mapping) else {}
    backtest_costs = backtest.get("costs")
    backtest_costs = (
        dict(backtest_costs) if isinstance(backtest_costs, Mapping) else {}
    )
    top_k = int(backtest_costs.get("top_k", backtest.get("top_k", 10)) or 10)

    metric_names = (
        "outer_test_period_count",
        "mean_rank_ic",
        "positive_rank_ic_ratio",
        "outer_block_positive_net_excess_ratio",
        "base_net_total_return",
        "base_benchmark_total_return",
        "base_relative_total_return",
        "base_average_net_excess_return",
        "base_positive_net_excess_ratio",
        "base_mean_turnover",
        "base_max_drawdown",
        "base_leave_best_period_out_relative_total_return",
        "base_best_positive_excess_contribution_share",
        "stress_relative_total_return",
    )
    historical_metrics = {
        name: _finite_float(champion_row.get(name), name)
        for name in metric_names
    }
    historical_metrics["outer_test_period_count"] = int(
        historical_metrics["outer_test_period_count"]
    )

    policy_core = {
        "schema_version": REFERENCE_POLICY_SCHEMA,
        "operations_schema_version": SCHEMA_VERSION,
        "status": "FROZEN_HISTORICAL_REFERENCE",
        "frozen_on": freeze_date.isoformat(),
        "source": {
            "model_lab_schema": EXPECTED_MODEL_LAB_SCHEMA,
            "archive_sha256": verified["source_sha256"],
            "manifest_sha256": verified["manifest_sha256"],
            "signal_date": summary.get("signal_date")
            or dict(verified["manifest"]).get("signal_date"),
            "protocol_provenance": nested.get("protocol_provenance"),
        },
        "model": {
            "champion": champion,
            "top_k": top_k,
            "rebalance_frequency": "MONTHLY",
            "model_fixed_across_outer_blocks": True,
            "tuning_locked": True,
            "feature_tuning_locked": True,
            "ensemble_tuning_locked": True,
        },
        "portfolio_policy": {
            "inner_selected_parameter": "MAX_VOLUNTARY_REPLACEMENTS",
            "candidate_caps": cap_candidates,
            "validation_months": int(nested.get("validation_months", 6)),
            "test_months": int(nested.get("test_months", 3)),
            "selected_caps_historical_audit": selected_caps,
            "cap_selected_only_from_prior_validation": True,
            "continuous_holdings": True,
        },
        "cost_contract": {
            "base_full_round_trip_bps": _finite_float(
                costs["BASE"].get("full_round_trip_bps"),
                "base_full_round_trip_bps",
            ),
            "stress_full_round_trip_bps": _finite_float(
                costs["STRESS"].get("full_round_trip_bps"),
                "stress_full_round_trip_bps",
            ),
            "base_slippage_bps_each_side": _finite_float(
                costs["BASE"].get("slippage_bps_each_side"),
                "base_slippage_bps_each_side",
            ),
            "stress_slippage_bps_each_side": _finite_float(
                costs["STRESS"].get("slippage_bps_each_side"),
                "stress_slippage_bps_each_side",
            ),
            "sell_tax_bps": _finite_float(
                costs["BASE"].get("sell_tax_bps"),
                "sell_tax_bps",
            ),
            "exact_execution_cost_claimed": False,
        },
        "historical_evidence": historical_metrics,
        "kill_switch": dict(DEFAULT_KILL_SWITCH),
        "permissions": {
            "paper_trading_allowed": True,
            "watchlist_allowed": True,
            "automatic_live_orders_allowed": False,
            "live_capital_approved": False,
            "actionable": False,
        },
        "change_control": {
            "allowed_without_new_model_version": [
                "BUG_FIX_WITH_NO_SELECTION_OR_RETURN_CHANGE",
                "DATA_CONNECTOR_RELIABILITY_FIX",
                "REPORTING_ONLY_CHANGE",
            ],
            "requires_new_model_version": [
                "FEATURE_CHANGE",
                "MODEL_CHANGE",
                "ENSEMBLE_WEIGHT_CHANGE",
                "TOP_K_CHANGE",
                "CAP_CANDIDATE_CHANGE",
                "VALIDATION_OBJECTIVE_CHANGE",
                "GATE_CHANGE",
            ],
        },
    }
    policy_hash = _sha_bytes(_json_bytes(policy_core))
    policy = {**policy_core, "policy_id": f"v15-{policy_hash[:16]}"}
    policy_payload = _json_bytes(policy)
    source_hash_payload = (
        f"{verified['source_sha256']}  {Path(model_lab_archive).name}\n"
    ).encode("utf-8")
    output_files = {
        "reference_policy.json": policy_payload,
        "source_archive.sha256": source_hash_payload,
    }
    manifest = {
        "schema_version": REFERENCE_POLICY_SCHEMA,
        "status": "SUCCESS",
        "policy_id": policy["policy_id"],
        "credentials_recorded": False,
        "live_capital_approved": False,
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in output_files.items()
        },
    }
    output_files["manifest.json"] = _json_bytes(manifest)
    _publish_immutable(Path(output_dir), output_files)
    return {
        "status": "SUCCESS",
        "policy_id": policy["policy_id"],
        "champion_model": champion,
        "output_dir": str(Path(output_dir)),
        "paper_trading_allowed": True,
        "live_capital_approved": False,
    }


def _load_policy(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("REFERENCE_POLICY_INVALID")
    if value.get("schema_version") != REFERENCE_POLICY_SCHEMA:
        raise ValueError("REFERENCE_POLICY_SCHEMA_INVALID")
    if value.get("status") != "FROZEN_HISTORICAL_REFERENCE":
        raise ValueError("REFERENCE_POLICY_NOT_FROZEN")
    permissions = value.get("permissions")
    if not isinstance(permissions, Mapping):
        raise ValueError("REFERENCE_POLICY_PERMISSIONS_MISSING")
    if permissions.get("live_capital_approved") is not False:
        raise ValueError("REFERENCE_POLICY_LIVE_APPROVAL_INVALID")
    return value


def evaluate_paper_observations(
    observations: Sequence[Mapping[str, object]],
    *,
    policy: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate rolling paper evidence and return a fail-closed decision."""
    policy_id = str(policy.get("policy_id") or "")
    if not policy_id:
        raise ValueError("PAPER_MONITOR_POLICY_ID_MISSING")
    thresholds_raw = policy.get("kill_switch")
    thresholds = (
        dict(thresholds_raw)
        if isinstance(thresholds_raw, Mapping)
        else dict(DEFAULT_KILL_SWITCH)
    )
    window = int(thresholds.get("rolling_window", 6))
    minimum = int(thresholds.get("minimum_observations", window))
    turnover_periods = int(
        thresholds.get("turnover_consecutive_periods", 3)
    )
    if window < 1 or minimum < 1 or turnover_periods < 1:
        raise ValueError("PAPER_MONITOR_THRESHOLD_INVALID")

    normalized: list[dict[str, object]] = []
    seen_dates: set[str] = set()
    for raw in observations:
        day = _parse_date(raw.get("observation_date"), "observation_date")
        day_text = day.isoformat()
        if day_text in seen_dates:
            raise ValueError(f"PAPER_MONITOR_DUPLICATE_DATE:{day_text}")
        seen_dates.add(day_text)
        row_policy = str(raw.get("policy_id") or "")
        if row_policy != policy_id:
            raise ValueError(f"PAPER_MONITOR_POLICY_MISMATCH:{day_text}")
        relative_nav = _finite_float(raw.get("relative_nav"), "relative_nav")
        if relative_nav <= 0.0:
            raise ValueError("PAPER_MONITOR_RELATIVE_NAV_NON_POSITIVE")
        turnover = _finite_float(raw.get("turnover"), "turnover")
        if turnover < 0.0 or turnover > 1.0:
            raise ValueError("PAPER_MONITOR_TURNOVER_OUT_OF_RANGE")
        normalized.append({
            "observation_date": day_text,
            "policy_id": policy_id,
            "rank_ic": _finite_float(raw.get("rank_ic"), "rank_ic"),
            "net_excess_return": _finite_float(
                raw.get("net_excess_return"), "net_excess_return"
            ),
            "turnover": turnover,
            "relative_nav": relative_nav,
            "contract_ok": _truthy(raw.get("contract_ok")),
            "data_quality_ok": _truthy(raw.get("data_quality_ok")),
            "notes": str(raw.get("notes") or ""),
        })
    normalized.sort(key=lambda row: str(row["observation_date"]))

    peak = 0.0
    worst_drawdown = 0.0
    for row in normalized:
        nav = float(row["relative_nav"])
        peak = max(peak, nav)
        drawdown = nav / peak - 1.0 if peak > 0 else 0.0
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
    if any(not bool(row["contract_ok"]) for row in normalized):
        triggers.append("CONTRACT_VIOLATION")
    if any(not bool(row["data_quality_ok"]) for row in normalized):
        triggers.append("DATA_QUALITY_VIOLATION")
    if worst_drawdown <= float(
        thresholds.get("relative_drawdown_at_or_below", -0.12)
    ):
        triggers.append("RELATIVE_DRAWDOWN_LIMIT")
    if len(normalized) >= minimum:
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

    block = bool(triggers)
    status = (
        "MODEL_UNDER_REVIEW"
        if block
        else "PAPER_WARMUP"
        if len(normalized) < minimum
        else "PAPER_ACTIVE"
    )
    return {
        "schema_version": PAPER_MONITOR_SCHEMA,
        "status": status,
        "policy_id": policy_id,
        "observation_count": len(normalized),
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
        "block_new_positions": block,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
        "actionable": False,
        "thresholds": thresholds,
        "observations": normalized,
    }


def publish_paper_monitor(
    *,
    policy_path: Path,
    observations_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    policy = _load_policy(Path(policy_path))
    observations, fields = _read_csv(Path(observations_path))
    required = {
        "observation_date",
        "policy_id",
        "rank_ic",
        "net_excess_return",
        "turnover",
        "relative_nav",
        "contract_ok",
        "data_quality_ok",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(
            "PAPER_MONITOR_OBSERVATION_COLUMNS_MISSING:"
            + "|".join(missing)
        )
    decision = evaluate_paper_observations(observations, policy=policy)
    detail_rows = list(decision.pop("observations"))
    monitor_payload = _json_bytes(decision)
    detail_fields = (
        "observation_date",
        "policy_id",
        "rank_ic",
        "net_excess_return",
        "turnover",
        "relative_nav",
        "relative_drawdown",
        "contract_ok",
        "data_quality_ok",
        "notes",
    )
    detail_payload = _csv_bytes(detail_rows, detail_fields)
    output_files = {
        "paper_model_monitor_v16.json": monitor_payload,
        "paper_observations_audit_v16.csv": detail_payload,
    }
    manifest = {
        "schema_version": PAPER_MONITOR_SCHEMA,
        "status": "SUCCESS",
        "policy_id": decision["policy_id"],
        "paper_status": decision["status"],
        "block_new_positions": decision["block_new_positions"],
        "live_capital_approved": False,
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in output_files.items()
        },
    }
    output_files["manifest.json"] = _json_bytes(manifest)
    _publish_immutable(Path(output_dir), output_files)
    return {
        "status": "SUCCESS",
        "paper_status": decision["status"],
        "block_new_positions": decision["block_new_positions"],
        "kill_switch_triggers": decision["kill_switch_triggers"],
        "output_dir": str(Path(output_dir)),
        "live_capital_approved": False,
    }


def _month_end_dates(days: Iterable[date]) -> list[date]:
    last_by_month: dict[tuple[int, int], date] = {}
    for day in days:
        key = (day.year, day.month)
        last_by_month[key] = max(last_by_month.get(key, day), day)
    return [last_by_month[key] for key in sorted(last_by_month)]


def audit_historical_extension(
    *,
    price_path: Path,
    benchmark_path: Path,
    universe_path: Path,
    metadata_pit_path: Path | None,
    output_dir: Path,
    minimum_train_months: int = 60,
    validation_months: int = 6,
    target_outer_test_months: int = 48,
    minimum_eligible_symbols: int = 80,
    minimum_monthly_coverage: float = 0.95,
    required_warmup_sessions: int = 251,
) -> dict[str, object]:
    """Audit canonical PIT inputs for a longer unchanged v15 evaluation."""
    if minimum_train_months < 24:
        raise ValueError("HISTORY_MINIMUM_TRAIN_MONTHS_TOO_SMALL")
    if validation_months < 3 or target_outer_test_months < 12:
        raise ValueError("HISTORY_EVALUATION_WINDOW_TOO_SMALL")
    if minimum_eligible_symbols < 10:
        raise ValueError("HISTORY_MINIMUM_ELIGIBLE_SYMBOLS_TOO_SMALL")
    if not 0.0 < minimum_monthly_coverage <= 1.0:
        raise ValueError("HISTORY_COVERAGE_THRESHOLD_INVALID")
    if required_warmup_sessions < 250:
        raise ValueError("HISTORY_WARMUP_TOO_SMALL")

    prices, price_fields = _read_csv(Path(price_path))
    strict_required = {
        "ma",
        "ngay",
        "gia_mo_cua",
        "gia_cao_nhat",
        "gia_thap_nhat",
        "gia_dong_cua",
        "khoi_luong",
        "nguon",
        "phien_ban",
        "co_so_gia",
    }
    reduced_required = {
        "ma",
        "ngay",
        "gia_mo_cua",
        "gia_dong_cua",
        "khoi_luong",
        "nguon",
        "phien_ban",
        "co_so_gia",
    }
    if strict_required.issubset(price_fields):
        price_contract = "strict_ohlcv"
    elif reduced_required.issubset(price_fields):
        price_contract = "reduced_open_close_volume_v1"
    else:
        raise ValueError("HISTORY_PRICE_SCHEMA_INVALID")

    by_symbol_dates: dict[str, list[date]] = {}
    price_basis: set[str] = set()
    seen_prices: set[tuple[str, date]] = set()
    for number, row in enumerate(prices, 2):
        symbol = str(row.get("ma") or "").strip().upper()
        if not symbol:
            raise ValueError(f"HISTORY_PRICE_SYMBOL_EMPTY:{number}")
        day = _parse_date(row.get("ngay"), "price_date")
        key = (symbol, day)
        if key in seen_prices:
            raise ValueError(f"HISTORY_PRICE_DUPLICATE:{symbol}:{day}")
        seen_prices.add(key)
        for name in ("gia_mo_cua", "gia_dong_cua"):
            if _finite_float(row.get(name), name) <= 0.0:
                raise ValueError(f"HISTORY_PRICE_NON_POSITIVE:{name}:{number}")
        volume = _finite_float(row.get("khoi_luong"), "khoi_luong")
        if volume < 0.0:
            raise ValueError(f"HISTORY_VOLUME_NEGATIVE:{number}")
        by_symbol_dates.setdefault(symbol, []).append(day)
        price_basis.add(str(row.get("co_so_gia") or "").strip())
    if not by_symbol_dates:
        raise ValueError("HISTORY_PRICE_EMPTY")
    if len(price_basis) != 1 or "" in price_basis:
        raise ValueError("HISTORY_PRICE_BASIS_AMBIGUOUS")
    basis = next(iter(price_basis))
    for values in by_symbol_dates.values():
        values.sort()

    benchmarks, benchmark_fields = _read_csv(Path(benchmark_path))
    if not {"ngay", "gia_dong_cua"}.issubset(benchmark_fields):
        raise ValueError("HISTORY_BENCHMARK_SCHEMA_INVALID")
    benchmark_days: list[date] = []
    seen_benchmark: set[date] = set()
    benchmark_symbols: set[str] = set()
    for number, row in enumerate(benchmarks, 2):
        day = _parse_date(row.get("ngay"), "benchmark_date")
        if day in seen_benchmark:
            raise ValueError(f"HISTORY_BENCHMARK_DUPLICATE:{day}")
        seen_benchmark.add(day)
        if _finite_float(row.get("gia_dong_cua"), "benchmark_close") <= 0.0:
            raise ValueError(f"HISTORY_BENCHMARK_NON_POSITIVE:{number}")
        benchmark_days.append(day)
        symbol = str(row.get("ma") or "VNINDEX").strip().upper()
        benchmark_symbols.add(symbol)
    if not benchmark_days or len(benchmark_symbols) != 1:
        raise ValueError("HISTORY_BENCHMARK_IDENTITY_INVALID")
    benchmark_days.sort()

    universe_rows, universe_fields = _read_csv(Path(universe_path))
    required_universe = {
        "ngay_hieu_luc",
        "ma",
        "thuoc_universe",
        "nguon",
        "phien_ban",
        "thoi_diem_cong_bo",
    }
    missing_universe = sorted(required_universe - set(universe_fields))
    if missing_universe:
        raise ValueError(
            "HISTORY_UNIVERSE_COLUMNS_MISSING:"
            + "|".join(missing_universe)
        )
    universe_by_symbol: dict[str, list[dict[str, object]]] = {}
    seen_universe: set[tuple[str, date, datetime]] = set()
    for number, row in enumerate(universe_rows, 2):
        symbol = str(row.get("ma") or "").strip().upper()
        effective = _parse_date(row.get("ngay_hieu_luc"), "universe_effective")
        published = _parse_datetime(
            row.get("thoi_diem_cong_bo"), "universe_published"
        )
        key = (symbol, effective, published)
        if not symbol or key in seen_universe:
            raise ValueError(f"HISTORY_UNIVERSE_DUPLICATE_OR_EMPTY:{number}")
        seen_universe.add(key)
        universe_by_symbol.setdefault(symbol, []).append({
            "effective": effective,
            "published": published,
            "member": _explicit_bool(row.get("thuoc_universe"), "thuoc_universe"),
        })
    for values in universe_by_symbol.values():
        values.sort(key=lambda item: (item["effective"], item["published"]))

    metadata_rows: list[dict[str, str]] = []
    if metadata_pit_path is not None:
        metadata_rows, metadata_fields = _read_csv(Path(metadata_pit_path))
        required_metadata = {
            "loai_du_lieu",
            "khoa_ban_ghi",
            "ngay_hieu_luc",
            "nguon",
            "phien_ban",
            "thoi_diem_cong_bo",
        }
        missing_metadata = sorted(required_metadata - set(metadata_fields))
        if missing_metadata:
            raise ValueError(
                "HISTORY_METADATA_COLUMNS_MISSING:"
                + "|".join(missing_metadata)
            )
        for row in metadata_rows:
            _parse_date(row.get("ngay_hieu_luc"), "metadata_effective")
            _parse_datetime(row.get("thoi_diem_cong_bo"), "metadata_published")

    basis_confirmed = basis in {"gia_dieu_chinh", "gia_khong_dieu_chinh"}
    corporate_action_count = sum(
        str(row.get("loai_du_lieu") or "") == "corporate_action"
        for row in metadata_rows
    )
    corporate_actions_ready = (
        basis == "gia_dieu_chinh"
        or (basis == "gia_khong_dieu_chinh" and corporate_action_count > 0)
    )

    signal_dates = _month_end_dates(benchmark_days)
    benchmark_symbol = next(iter(benchmark_symbols))
    symbols = sorted((set(by_symbol_dates) | set(universe_by_symbol)) - {benchmark_symbol})
    monthly_rows: list[dict[str, object]] = []
    ready_dates: list[date] = []
    for signal_day in signal_dates:
        signal_dt = datetime.combine(signal_day, SIGNAL_TIME, tzinfo=VN_TZ)
        known = 0
        eligible: list[str] = []
        warm = 0
        for symbol in symbols:
            candidates = [
                item
                for item in universe_by_symbol.get(symbol, ())
                if item["effective"] <= signal_day
                and item["published"].astimezone(VN_TZ) <= signal_dt
            ]
            if not candidates:
                continue
            known += 1
            selected = max(
                candidates,
                key=lambda item: (item["effective"], item["published"]),
            )
            if bool(selected["member"]):
                eligible.append(symbol)
                observations = sum(
                    day <= signal_day
                    for day in by_symbol_dates.get(symbol, ())
                )
                if observations >= required_warmup_sessions:
                    warm += 1
        universe_coverage = known / len(symbols) if symbols else 0.0
        warmup_coverage = warm / len(eligible) if eligible else 0.0
        ready = (
            universe_coverage >= minimum_monthly_coverage
            and len(eligible) >= minimum_eligible_symbols
            and warmup_coverage >= minimum_monthly_coverage
            and basis_confirmed
            and corporate_actions_ready
            and price_contract == "strict_ohlcv"
        )
        if ready:
            ready_dates.append(signal_day)
        monthly_rows.append({
            "signal_date": signal_day.isoformat(),
            "candidate_symbol_count": len(symbols),
            "known_universe_symbol_count": known,
            "universe_coverage": universe_coverage,
            "eligible_symbol_count": len(eligible),
            "warmup_eligible_symbol_count": warm,
            "warmup_coverage": warmup_coverage,
            "price_basis_confirmed": str(basis_confirmed).lower(),
            "corporate_actions_ready": str(corporate_actions_ready).lower(),
            "strict_ohlcv": str(price_contract == "strict_ohlcv").lower(),
            "research_ready": str(ready).lower(),
        })

    required_ready_months = (
        minimum_train_months + validation_months + target_outer_test_months
    )
    ready_month_count = len(ready_dates)
    longest_ready_streak = 0
    current_streak = 0
    previous_month: tuple[int, int] | None = None
    for row in monthly_rows:
        day = date.fromisoformat(str(row["signal_date"]))
        month = (day.year, day.month)
        consecutive = False
        if previous_month is not None:
            year, value = previous_month
            next_month = (year + 1, 1) if value == 12 else (year, value + 1)
            consecutive = month == next_month
        if str(row["research_ready"]) == "true":
            current_streak = current_streak + 1 if consecutive else 1
            longest_ready_streak = max(longest_ready_streak, current_streak)
        else:
            current_streak = 0
        previous_month = month
    estimated_outer_months = max(
        0, longest_ready_streak - minimum_train_months - validation_months
    )
    history_pass = estimated_outer_months >= target_outer_test_months
    latest_day = max(benchmark_days)
    target_start = latest_day - timedelta(
        days=int(required_ready_months * 30.5) + 400
    )
    status = (
        "READY_FOR_EXTENDED_V15"
        if history_pass
        else "HISTORICAL_DATA_EXTENSION_REQUIRED"
    )
    summary = {
        "schema_version": HISTORY_READINESS_SCHEMA,
        "status": status,
        "price_contract": price_contract,
        "price_basis": basis,
        "price_basis_confirmed": basis_confirmed,
        "corporate_action_record_count": corporate_action_count,
        "corporate_actions_ready": corporate_actions_ready,
        "benchmark_symbol": next(iter(benchmark_symbols)),
        "benchmark_first_date": min(benchmark_days).isoformat(),
        "benchmark_last_date": latest_day.isoformat(),
        "candidate_symbol_count": len(symbols),
        "monthly_signal_count": len(signal_dates),
        "research_ready_month_count": ready_month_count,
        "longest_contiguous_ready_months": longest_ready_streak,
        "minimum_train_months": minimum_train_months,
        "validation_months": validation_months,
        "target_outer_test_months": target_outer_test_months,
        "estimated_outer_test_months": estimated_outer_months,
        "required_ready_months": required_ready_months,
        "minimum_eligible_symbols": minimum_eligible_symbols,
        "minimum_monthly_coverage": minimum_monthly_coverage,
        "required_warmup_sessions": required_warmup_sessions,
        "recommended_download_start_no_later_than": target_start.isoformat(),
        "extended_v15_ready": history_pass,
        "live_capital_approved": False,
        "actionable": False,
    }
    summary_payload = _json_bytes(summary)
    monthly_fields = (
        "signal_date",
        "candidate_symbol_count",
        "known_universe_symbol_count",
        "universe_coverage",
        "eligible_symbol_count",
        "warmup_eligible_symbol_count",
        "warmup_coverage",
        "price_basis_confirmed",
        "corporate_actions_ready",
        "strict_ohlcv",
        "research_ready",
    )
    monthly_payload = _csv_bytes(monthly_rows, monthly_fields)
    run_args = {
        "protocol": "UNCHANGED_MODEL_LAB_V15",
        "minimum_train_months": minimum_train_months,
        "evaluation_months": validation_months + target_outer_test_months,
        "nested_validation_months": validation_months,
        "nested_test_months": 3,
        "minimum_outer_test_periods": target_outer_test_months,
        "replacement_caps": [0, 1, 2, 3, 4, 5],
        "tuning_locked": True,
    }
    run_args_payload = _json_bytes(run_args)
    output_files = {
        "historical_extension_readiness_v16.json": summary_payload,
        "historical_monthly_coverage_v16.csv": monthly_payload,
        "extended_v15_run_contract.json": run_args_payload,
    }
    manifest = {
        "schema_version": HISTORY_READINESS_SCHEMA,
        "status": "SUCCESS",
        "extended_v15_ready": history_pass,
        "live_capital_approved": False,
        "inputs": {
            "price_sha256": _sha_file(Path(price_path)),
            "benchmark_sha256": _sha_file(Path(benchmark_path)),
            "universe_sha256": _sha_file(Path(universe_path)),
            "metadata_pit_sha256": (
                _sha_file(Path(metadata_pit_path))
                if metadata_pit_path is not None
                else None
            ),
        },
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in output_files.items()
        },
    }
    output_files["manifest.json"] = _json_bytes(manifest)
    _publish_immutable(Path(output_dir), output_files)
    return {
        "status": "SUCCESS",
        "history_status": status,
        "extended_v15_ready": history_pass,
        "estimated_outer_test_months": estimated_outer_months,
        "recommended_download_start_no_later_than": target_start.isoformat(),
        "output_dir": str(Path(output_dir)),
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.reference_operations_v16"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--model-lab-output", type=Path, required=True)
    freeze.add_argument("--output-dir", type=Path, required=True)
    freeze.add_argument("--freeze-date", type=date.fromisoformat, required=True)

    monitor = sub.add_parser("monitor")
    monitor.add_argument("--policy", type=Path, required=True)
    monitor.add_argument("--observations", type=Path, required=True)
    monitor.add_argument("--output-dir", type=Path, required=True)

    history = sub.add_parser("history-audit")
    history.add_argument("--prices", type=Path, required=True)
    history.add_argument("--benchmark", type=Path, required=True)
    history.add_argument("--universe", type=Path, required=True)
    history.add_argument("--metadata-pit", type=Path)
    history.add_argument("--output-dir", type=Path, required=True)
    history.add_argument("--minimum-train-months", type=int, default=60)
    history.add_argument("--validation-months", type=int, default=6)
    history.add_argument("--target-outer-test-months", type=int, default=48)
    history.add_argument("--minimum-eligible-symbols", type=int, default=80)
    history.add_argument("--minimum-monthly-coverage", type=float, default=0.95)
    history.add_argument("--required-warmup-sessions", type=int, default=251)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "freeze":
            result = freeze_reference_policy(
                model_lab_archive=args.model_lab_output,
                output_dir=args.output_dir,
                freeze_date=args.freeze_date,
            )
        elif args.command == "monitor":
            result = publish_paper_monitor(
                policy_path=args.policy,
                observations_path=args.observations,
                output_dir=args.output_dir,
            )
        else:
            result = audit_historical_extension(
                price_path=args.prices,
                benchmark_path=args.benchmark,
                universe_path=args.universe,
                metadata_pit_path=args.metadata_pit,
                output_dir=args.output_dir,
                minimum_train_months=args.minimum_train_months,
                validation_months=args.validation_months,
                target_outer_test_months=args.target_outer_test_months,
                minimum_eligible_symbols=args.minimum_eligible_symbols,
                minimum_monthly_coverage=args.minimum_monthly_coverage,
                required_warmup_sessions=args.required_warmup_sessions,
            )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REFERENCE_POLICY_SCHEMA",
    "PAPER_MONITOR_SCHEMA",
    "HISTORY_READINESS_SCHEMA",
    "DEFAULT_KILL_SWITCH",
    "freeze_reference_policy",
    "evaluate_paper_observations",
    "publish_paper_monitor",
    "audit_historical_extension",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
