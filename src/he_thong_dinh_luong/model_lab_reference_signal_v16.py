"""Publish a paper-trading signal package from a frozen Model Lab v15 policy.

The publisher keeps the validated strategy unchanged:

* the model family is the frozen v15 champion;
* Top-K is read from the immutable policy;
* maximum voluntary replacements is selected from the most recent completed
  OOS validation window only;
* holdings carry across monthly signal packages;
* the portfolio is equal-weighted to match the v15 historical evaluation.

The output matches ``paper_trading_daily``'s ZIP contract. No live order is sent.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from . import model_lab_upgrade_v13 as v13
from .paper_trading_daily import SIGNAL_FIELDS, SIGNAL_FILE
from .reference_operations_v16 import (
    EXPECTED_MODEL_LAB_SCHEMA,
    REFERENCE_POLICY_SCHEMA,
    _load_policy,
    _sha_file,
    _verified_archive,
)

SCHEMA_VERSION = "model_lab_reference_signal_v16"
MANIFEST_FILE = "manifest.json"
STATE_SCHEMA = "model_lab_reference_signal_state_v16"


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


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
    rows: Sequence[Mapping[str, object]],
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


def _read_csv_payload(payload: bytes) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    ]


def _finite(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"REFERENCE_SIGNAL_{name}_NOT_NUMERIC") from exc
    if not isfinite(result):
        raise ValueError(f"REFERENCE_SIGNAL_{name}_NOT_FINITE")
    return result


def _read_artifact_rows(
    model_lab_archive: Path,
) -> tuple[dict[str, object], list[dict[str, str]], list[dict[str, str]], str]:
    verified = _verified_archive(Path(model_lab_archive))
    summary = dict(verified["summary"])
    if summary.get("upgrade_schema_version") != EXPECTED_MODEL_LAB_SCHEMA:
        raise ValueError("REFERENCE_SIGNAL_REQUIRES_MODEL_LAB_V15")
    with ZipFile(model_lab_archive) as archive:
        names = set(archive.namelist())
        required = {"oos_predictions.csv", "forward_model_scores.csv"}
        missing = sorted(required - names)
        if missing:
            raise ValueError(
                "REFERENCE_SIGNAL_ARTIFACT_FILE_MISSING:" + "|".join(missing)
            )
        predictions = _read_csv_payload(archive.read("oos_predictions.csv"))
        forward = _read_csv_payload(archive.read("forward_model_scores.csv"))
    return summary, predictions, forward, str(verified["source_sha256"])


def _validation_cost(policy: Mapping[str, object]) -> v13.DnseCashCostConfig:
    contract = policy.get("cost_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("REFERENCE_SIGNAL_COST_CONTRACT_MISSING")
    base_slippage = _finite(
        contract.get("base_slippage_bps_each_side"),
        "BASE_SLIPPAGE",
    )
    stress_slippage = _finite(
        contract.get("stress_slippage_bps_each_side"),
        "STRESS_SLIPPAGE",
    )
    sell_tax = _finite(contract.get("sell_tax_bps"), "SELL_TAX")
    config = v13.DnseCashCostConfig(
        broker_buy_fee_bps=0.0,
        broker_sell_fee_bps=0.0,
        exchange_buy_fee_bps=2.7,
        exchange_sell_fee_bps=2.7,
        sell_tax_bps=sell_tax,
        transfer_fee_vnd_per_share=0.3,
        transfer_reference_price_vnd=10_000.0,
        slippage_bps=base_slippage,
        stress_slippage_bps=stress_slippage,
    )
    expected = _finite(
        contract.get("base_full_round_trip_bps"),
        "BASE_ROUND_TRIP",
    )
    actual = (
        config.combined_buy_fee_bps
        + config.combined_sell_fee_bps
        + config.sell_tax_bps
        + 2.0 * config.slippage_bps
    )
    if abs(actual - expected) > 1e-9:
        raise ValueError("REFERENCE_SIGNAL_COST_CONTRACT_MISMATCH")
    return config


def select_forward_cap(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    champion: str,
    signal_date: date,
    top_k: int,
    candidate_caps: Sequence[int],
    validation_months: int,
    cost: v13.DnseCashCostConfig,
) -> tuple[int, dict[str, float | int], tuple[str, ...]]:
    """Select cap using only completed OOS labels strictly before signal date."""
    completed_dates: list[str] = []
    by_date: dict[str, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if str(row.get("model") or "") != champion:
            continue
        test_date = str(row.get("test_date") or "")
        label_end = str(row.get("label_end") or "")
        if not test_date or not label_end:
            continue
        try:
            label_day = date.fromisoformat(label_end)
        except ValueError as exc:
            raise ValueError("REFERENCE_SIGNAL_LABEL_END_INVALID") from exc
        if label_day < signal_date:
            by_date.setdefault(test_date, []).append(row)
    completed_dates = sorted(by_date)
    if len(completed_dates) < validation_months:
        raise ValueError("REFERENCE_SIGNAL_VALIDATION_HISTORY_INSUFFICIENT")
    validation_dates = tuple(completed_dates[-validation_months:])
    usable = [
        dict(row)
        for day in completed_dates
        for row in by_date[day]
    ]
    caps = tuple(sorted(set(int(value) for value in candidate_caps)))
    if not caps or any(value < 0 or value > top_k for value in caps):
        raise ValueError("REFERENCE_SIGNAL_CAP_CANDIDATES_INVALID")
    cache = v13._period_cache(
        usable,
        top_k=top_k,
        candidate_models=(champion,),
        replacement_caps=caps,
        cost=cost,
        slippage_bps=cost.slippage_bps,
    )
    candidates: list[
        tuple[
            tuple[float, float, float, float, float, int, int],
            int,
            dict[str, float | int],
        ]
    ] = []
    for cap in caps:
        periods = v13._period_subset(cache[(champion, cap)], validation_dates)
        metrics = v13.v12.v11.capped_policy_metrics(periods)
        candidates.append((
            v13._validation_key(metrics, cap=cap, model_priority=0),
            cap,
            metrics,
        ))
    _, selected_cap, metrics = max(candidates, key=lambda item: item[0])
    return selected_cap, metrics, validation_dates


def select_forward_symbols(
    ranked_symbols: Sequence[str],
    *,
    previous_symbols: Sequence[str],
    top_k: int,
    max_voluntary_replacements: int,
) -> tuple[list[str], int, int]:
    """Apply the v11/v15 retention policy to the current forward ranking."""
    ranked = [str(symbol).strip().upper() for symbol in ranked_symbols]
    ranked = [symbol for symbol in ranked if symbol]
    if len(ranked) != len(set(ranked)):
        raise ValueError("REFERENCE_SIGNAL_FORWARD_SYMBOL_DUPLICATE")
    if len(ranked) < top_k:
        raise ValueError("REFERENCE_SIGNAL_FORWARD_SYMBOLS_INSUFFICIENT")
    cap = int(max_voluntary_replacements)
    if cap < 0 or cap > top_k:
        raise ValueError("REFERENCE_SIGNAL_SELECTED_CAP_INVALID")
    previous = [str(symbol).strip().upper() for symbol in previous_symbols]
    previous = [symbol for symbol in previous if symbol]
    previous_available = [symbol for symbol in previous if symbol in set(ranked)]
    forced_exit_count = len([symbol for symbol in previous if symbol not in set(ranked)])
    desired = ranked[:top_k]
    if not previous:
        return desired, forced_exit_count, 0
    rank_by_symbol = {
        symbol: index for index, symbol in enumerate(ranked, start=1)
    }
    minimum_retain = max(0, min(len(previous_available), top_k - cap))
    retained = [symbol for symbol in desired if symbol in previous_available]
    if len(retained) < minimum_retain:
        for symbol in sorted(
            previous_available,
            key=lambda item: (rank_by_symbol[item], item),
        ):
            if symbol not in retained:
                retained.append(symbol)
            if len(retained) >= minimum_retain:
                break
    selected = list(retained)
    for symbol in ranked:
        if symbol not in selected:
            selected.append(symbol)
        if len(selected) >= top_k:
            break
    selected = selected[:top_k]
    overlap = len(set(previous) & set(selected))
    total_replacements = max(0, top_k - overlap)
    voluntary = max(0, total_replacements - forced_exit_count)
    if voluntary > cap:
        raise ValueError("REFERENCE_SIGNAL_VOLUNTARY_CAP_BREACH")
    return selected, forced_exit_count, voluntary


def _load_state(path: Path, *, policy_id: str) -> dict[str, object]:
    if not path.exists():
        return {
            "schema_version": STATE_SCHEMA,
            "policy_id": policy_id,
            "latest_signal_date": None,
            "selected_symbols": [],
        }
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("REFERENCE_SIGNAL_STATE_INVALID")
    if value.get("schema_version") != STATE_SCHEMA:
        raise ValueError("REFERENCE_SIGNAL_STATE_SCHEMA_INVALID")
    if str(value.get("policy_id") or "") != policy_id:
        raise ValueError("REFERENCE_SIGNAL_STATE_POLICY_MISMATCH")
    selected = value.get("selected_symbols")
    if not isinstance(selected, list) or not all(
        isinstance(symbol, str) and symbol for symbol in selected
    ):
        raise ValueError("REFERENCE_SIGNAL_STATE_SYMBOLS_INVALID")
    return value


def _write_state(path: Path, state: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_json_bytes(state))
    temporary.replace(path)


def _zip_write(archive: ZipFile, name: str, payload: bytes) -> None:
    info = ZipInfo(name)
    info.date_time = (2020, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def publish_reference_signal(
    *,
    model_lab_archive: Path,
    policy_path: Path,
    state_dir: Path,
    output_zip: Path,
) -> dict[str, object]:
    policy = _load_policy(Path(policy_path))
    policy_id = str(policy.get("policy_id") or "")
    model_contract = policy.get("model")
    portfolio_contract = policy.get("portfolio_policy")
    if not isinstance(model_contract, Mapping) or not isinstance(
        portfolio_contract, Mapping
    ):
        raise ValueError("REFERENCE_SIGNAL_POLICY_CONTRACT_INVALID")
    champion = str(model_contract.get("champion") or "")
    top_k = int(model_contract.get("top_k", 0) or 0)
    if not champion or top_k < 1:
        raise ValueError("REFERENCE_SIGNAL_POLICY_MODEL_INVALID")
    candidate_caps = portfolio_contract.get("candidate_caps")
    if not isinstance(candidate_caps, list):
        raise ValueError("REFERENCE_SIGNAL_POLICY_CAPS_INVALID")
    validation_months = int(
        portfolio_contract.get("validation_months", 0) or 0
    )
    if validation_months < 3:
        raise ValueError("REFERENCE_SIGNAL_POLICY_VALIDATION_INVALID")

    summary, predictions, forward_rows, source_sha = _read_artifact_rows(
        Path(model_lab_archive)
    )
    current_contract = summary.get("nested_model_validation_contract_v15")
    if not isinstance(current_contract, Mapping):
        raise ValueError("REFERENCE_SIGNAL_V15_CONTRACT_MISSING")
    if (
        current_contract.get("evaluation_unit") != "MODEL_FAMILY"
        or current_contract.get("model_switching_inside_outer_portfolio") is not False
        or current_contract.get("cap_selected_only_from_prior_validation") is not True
    ):
        raise ValueError("REFERENCE_SIGNAL_V15_CONTRACT_DRIFT")

    champion_forward = [
        row for row in forward_rows if str(row.get("model") or "") == champion
    ]
    if not champion_forward:
        raise ValueError("REFERENCE_SIGNAL_CHAMPION_FORWARD_MISSING")
    signal_dates = {str(row.get("signal_date") or "") for row in champion_forward}
    if len(signal_dates) != 1 or "" in signal_dates:
        raise ValueError("REFERENCE_SIGNAL_DATE_INVALID")
    signal_date_text = next(iter(signal_dates))
    try:
        signal_date = date.fromisoformat(signal_date_text)
    except ValueError as exc:
        raise ValueError("REFERENCE_SIGNAL_DATE_INVALID") from exc

    rank_rows: list[tuple[int, str, Mapping[str, object]]] = []
    seen_ranks: set[int] = set()
    seen_symbols: set[str] = set()
    for row in champion_forward:
        symbol = str(row.get("symbol") or "").strip().upper()
        rank_value = _finite(row.get("rank"), "RANK")
        rank = int(rank_value)
        if rank_value != rank or rank < 1:
            raise ValueError("REFERENCE_SIGNAL_RANK_INVALID")
        if not symbol or symbol in seen_symbols or rank in seen_ranks:
            raise ValueError("REFERENCE_SIGNAL_FORWARD_DUPLICATE")
        seen_symbols.add(symbol)
        seen_ranks.add(rank)
        _finite(row.get("score"), "SCORE")
        if str(row.get("quality_status") or "PASS") != "PASS":
            raise ValueError(f"REFERENCE_SIGNAL_SCORE_QUALITY_FAILED:{symbol}")
        rank_rows.append((rank, symbol, row))
    rank_rows.sort(key=lambda item: (item[0], item[1]))
    ranked_symbols = [symbol for _, symbol, _ in rank_rows]

    cost = _validation_cost(policy)
    selected_cap, validation_metrics, validation_dates = select_forward_cap(
        predictions,
        champion=champion,
        signal_date=signal_date,
        top_k=top_k,
        candidate_caps=tuple(int(value) for value in candidate_caps),
        validation_months=validation_months,
        cost=cost,
    )

    state_root = Path(state_dir)
    state_path = state_root / "reference_signal_state_v16.json"
    state = _load_state(state_path, policy_id=policy_id)
    latest_text = state.get("latest_signal_date")
    if latest_text:
        latest = date.fromisoformat(str(latest_text))
        if signal_date <= latest:
            raise ValueError(
                f"REFERENCE_SIGNAL_NOT_AFTER_STATE:{signal_date}:{latest}"
            )
    previous = [str(value) for value in state.get("selected_symbols", [])]
    selected, forced_exits, voluntary = select_forward_symbols(
        ranked_symbols,
        previous_symbols=previous,
        top_k=top_k,
        max_voluntary_replacements=selected_cap,
    )

    rank_by_symbol = {symbol: rank for rank, symbol, _ in rank_rows}
    source_archive_sha = _sha_file(Path(model_lab_archive))
    unit = Decimal("100") / Decimal(top_k)
    weights = [unit for _ in selected]
    if weights:
        weights[-1] = Decimal("100") - sum(weights[:-1], Decimal("0"))
    portfolio_rows = [
        {
            "signal_date": signal_date_text,
            "symbol": symbol,
            "champion_model": champion,
            "rank": rank_by_symbol[symbol],
            "target_weight_pct": format(weights[index], ".12f").rstrip("0").rstrip("."),
            "status": "REFERENCE_PAPER_SIGNAL",
            "source_zip_sha256": source_archive_sha,
        }
        for index, symbol in enumerate(selected)
    ]
    signal_payload = _csv_bytes(portfolio_rows, SIGNAL_FIELDS)
    diagnostic = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "policy_id": policy_id,
        "signal_date": signal_date_text,
        "champion_model": champion,
        "top_k": top_k,
        "selected_replacement_cap": selected_cap,
        "validation_dates": list(validation_dates),
        "validation_metrics": validation_metrics,
        "previous_symbols": previous,
        "selected_symbols": selected,
        "forced_exit_count": forced_exits,
        "voluntary_replacement_count": voluntary,
        "voluntary_replacement_cap_respected": voluntary <= selected_cap,
        "equal_weight_matches_v15_evaluation": True,
        "source_model_lab_archive_sha256": source_sha,
        "frozen_source_archive_match": (
            source_sha
            == str(dict(policy.get("source") or {}).get("archive_sha256") or "")
        ),
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
        "actionable": False,
    }
    diagnostic_payload = _json_bytes(diagnostic)
    files = {
        SIGNAL_FILE: signal_payload,
        "reference_signal_diagnostic_v16.json": diagnostic_payload,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "signal_date": signal_date_text,
        "policy_id": policy_id,
        "champion_model": champion,
        "credentials_recorded": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in files.items()
        },
    }
    manifest_payload = _json_bytes(manifest)
    destination = Path(output_zip)
    if destination.exists():
        raise FileExistsError(f"REFERENCE_SIGNAL_OUTPUT_EXISTS:{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with ZipFile(temporary, "w") as archive:
            _zip_write(archive, SIGNAL_FILE, signal_payload)
            _zip_write(
                archive,
                "reference_signal_diagnostic_v16.json",
                diagnostic_payload,
            )
            _zip_write(archive, MANIFEST_FILE, manifest_payload)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    new_state = {
        "schema_version": STATE_SCHEMA,
        "policy_id": policy_id,
        "latest_signal_date": signal_date_text,
        "selected_symbols": selected,
        "selected_replacement_cap": selected_cap,
        "source_model_lab_archive_sha256": source_archive_sha,
        "signal_output_sha256": _sha_file(destination),
    }
    _write_state(state_path, new_state)
    return {
        "status": "SUCCESS",
        "schema_version": SCHEMA_VERSION,
        "policy_id": policy_id,
        "signal_date": signal_date_text,
        "champion_model": champion,
        "selected_replacement_cap": selected_cap,
        "selected_symbols": selected,
        "output_zip": str(destination),
        "output_zip_sha256": _sha_file(destination),
        "state_path": str(state_path),
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.model_lab_reference_signal_v16"
    )
    parser.add_argument("--model-lab-output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = publish_reference_signal(
            model_lab_archive=args.model_lab_output,
            policy_path=args.policy,
            state_dir=args.state_dir,
            output_zip=args.output_zip,
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
    "STATE_SCHEMA",
    "select_forward_cap",
    "select_forward_symbols",
    "publish_reference_signal",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
