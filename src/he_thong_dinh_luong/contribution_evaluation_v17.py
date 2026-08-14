"""Monthly-horizon evaluation for a strategy funded by periodic contributions.

Predictive quality is evaluated with monthly label-horizon returns. T+1 belongs
to execution accounting only. External investor cash flows are reported in two
ways:

* time-weighted return (TWR) for the strategy itself, independent of deposits;
* money-weighted return (XIRR) and terminal wealth for the investor experience.

Contributions arriving between monthly signals accumulate and are deployed at
the next published monthly signal. This module does not retrain or tune a model.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

SCHEMA_VERSION = "contribution_evaluation_v17"
PERIOD_FILE = "nested_model_outer_test_periods_v15.csv"
SUMMARY_FILE = "model_lab_summary.json"
MANIFEST_FILE = "manifest.json"


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    ]


def _csv_bytes(rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _date(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(code) from exc


def _float(value: object, code: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if not math.isfinite(result):
        raise ValueError(code)
    return result


def _verified_archive(path: Path) -> tuple[dict[str, object], list[dict[str, str]], str]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("CONTRIBUTION_MODEL_LAB_ARCHIVE_NOT_FOUND")
    try:
        with ZipFile(source) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"CONTRIBUTION_MODEL_LAB_CRC_ERROR:{bad}")
            names = set(archive.namelist())
            required = {SUMMARY_FILE, PERIOD_FILE, MANIFEST_FILE}
            missing = sorted(required - names)
            if missing:
                raise ValueError(
                    "CONTRIBUTION_MODEL_LAB_FILE_MISSING:" + "|".join(missing)
                )
            summary_payload = archive.read(SUMMARY_FILE)
            period_payload = archive.read(PERIOD_FILE)
            manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8-sig"))
            summary = json.loads(summary_payload.decode("utf-8-sig"))
            files = manifest.get("files") if isinstance(manifest, Mapping) else None
            if not isinstance(files, Mapping):
                raise ValueError("CONTRIBUTION_MODEL_LAB_MANIFEST_INVALID")
            for name in (SUMMARY_FILE, PERIOD_FILE):
                contract = files.get(name)
                if not isinstance(contract, Mapping):
                    raise ValueError(f"CONTRIBUTION_MODEL_LAB_MANIFEST_ENTRY_MISSING:{name}")
                payload = summary_payload if name == SUMMARY_FILE else period_payload
                if str(contract.get("sha256") or "") != _sha(payload):
                    raise ValueError(f"CONTRIBUTION_MODEL_LAB_HASH_MISMATCH:{name}")
                if int(contract.get("size", -1)) != len(payload):
                    raise ValueError(f"CONTRIBUTION_MODEL_LAB_SIZE_MISMATCH:{name}")
            if manifest.get("credentials_recorded") is True:
                raise ValueError("CONTRIBUTION_MODEL_LAB_RECORDS_CREDENTIALS")
    except BadZipFile as exc:
        raise ValueError("CONTRIBUTION_MODEL_LAB_INVALID_ZIP") from exc
    return summary, _read_csv_bytes(period_payload), _sha(source.read_bytes())


def generate_periodic_contributions(
    *,
    start: date,
    end: date,
    amount_vnd: int,
    every_days: int,
) -> list[dict[str, object]]:
    if amount_vnd <= 0:
        raise ValueError("CONTRIBUTION_AMOUNT_MUST_BE_POSITIVE")
    if every_days <= 0:
        raise ValueError("CONTRIBUTION_INTERVAL_MUST_BE_POSITIVE")
    if end < start:
        raise ValueError("CONTRIBUTION_DATE_RANGE_INVALID")
    rows: list[dict[str, object]] = []
    current = start
    while current <= end:
        rows.append({"contribution_date": current.isoformat(), "amount_vnd": amount_vnd})
        current += timedelta(days=every_days)
    return rows


def _load_contributions(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"contribution_date", "amount_vnd"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("CONTRIBUTION_CSV_SCHEMA_INVALID")
        for raw in reader:
            day = _date(raw.get("contribution_date"), "CONTRIBUTION_DATE_INVALID")
            amount = int(float(str(raw.get("amount_vnd") or "0")))
            if amount <= 0:
                raise ValueError("CONTRIBUTION_AMOUNT_MUST_BE_POSITIVE")
            rows.append({"contribution_date": day.isoformat(), "amount_vnd": amount})
    rows.sort(key=lambda row: str(row["contribution_date"]))
    return rows


def _xirr(cashflows: Sequence[tuple[date, float]]) -> float | None:
    if len(cashflows) < 2:
        return None
    ordered = sorted(cashflows, key=lambda item: item[0])
    if not any(amount < 0 for _, amount in ordered) or not any(
        amount > 0 for _, amount in ordered
    ):
        return None
    origin = ordered[0][0]

    def npv(rate: float) -> float:
        return sum(
            amount / ((1.0 + rate) ** ((day - origin).days / 365.2425))
            for day, amount in ordered
        )

    low = -0.9999
    high = 1.0
    left = npv(low)
    right = npv(high)
    for _ in range(80):
        if left == 0.0:
            return low
        if right == 0.0:
            return high
        if left * right < 0.0:
            break
        high *= 2.0
        if high > 1_000_000:
            return None
        right = npv(high)
    else:
        return None
    for _ in range(160):
        mid = (low + high) / 2.0
        value = npv(mid)
        if abs(value) <= 1e-8:
            return mid
        if left * value <= 0.0:
            high = mid
            right = value
        else:
            low = mid
            left = value
    return (low + high) / 2.0


def evaluate_monthly_contributions(
    *,
    period_rows: Sequence[Mapping[str, object]],
    contribution_rows: Sequence[Mapping[str, object]],
    initial_capital_vnd: int = 0,
    minimum_periods: int = 48,
) -> dict[str, object]:
    if initial_capital_vnd < 0:
        raise ValueError("CONTRIBUTION_INITIAL_CAPITAL_INVALID")
    if minimum_periods < 12:
        raise ValueError("CONTRIBUTION_MINIMUM_PERIODS_TOO_SMALL")
    periods = sorted(
        [dict(row) for row in period_rows],
        key=lambda row: str(row.get("signal_date") or ""),
    )
    if not periods:
        raise ValueError("CONTRIBUTION_PERIODS_EMPTY")

    parsed: list[dict[str, object]] = []
    previous_signal: date | None = None
    previous_end: date | None = None
    for raw in periods:
        signal = _date(raw.get("signal_date"), "CONTRIBUTION_SIGNAL_DATE_INVALID")
        label_end = _date(raw.get("label_end"), "CONTRIBUTION_LABEL_END_INVALID")
        horizon_days = (label_end - signal).days
        if horizon_days < 20 or horizon_days > 45:
            raise ValueError(
                f"CONTRIBUTION_NOT_MONTHLY_HORIZON:{signal}:{label_end}:{horizon_days}"
            )
        if previous_signal is not None and signal <= previous_signal:
            raise ValueError("CONTRIBUTION_PERIODS_NOT_STRICTLY_ORDERED")
        if previous_end is not None and previous_end > signal:
            raise ValueError("CONTRIBUTION_MONTHLY_HORIZONS_OVERLAP")
        parsed.append({
            **raw,
            "signal": signal,
            "label_end_date": label_end,
            "horizon_days": horizon_days,
            "net_return_value": _float(raw.get("net_return"), "CONTRIBUTION_NET_RETURN_INVALID"),
            "benchmark_return_value": _float(
                raw.get("benchmark_return"),
                "CONTRIBUTION_BENCHMARK_RETURN_INVALID",
            ),
        })
        previous_signal = signal
        previous_end = label_end

    events = sorted(
        [
            {
                "contribution_date": _date(
                    row.get("contribution_date"),
                    "CONTRIBUTION_DATE_INVALID",
                ),
                "amount_vnd": int(float(str(row.get("amount_vnd") or "0"))),
            }
            for row in contribution_rows
        ],
        key=lambda row: row["contribution_date"],
    )
    if any(int(row["amount_vnd"]) <= 0 for row in events):
        raise ValueError("CONTRIBUTION_AMOUNT_MUST_BE_POSITIVE")

    mapped_flow = {item["signal"]: 0 for item in parsed}
    event_output: list[dict[str, object]] = []
    unmapped = 0
    for event in events:
        effective = next(
            (item["signal"] for item in parsed if item["signal"] >= event["contribution_date"]),
            None,
        )
        if effective is None:
            unmapped += int(event["amount_vnd"])
            event_output.append({
                "contribution_date": event["contribution_date"].isoformat(),
                "amount_vnd": int(event["amount_vnd"]),
                "effective_signal_date": "",
                "status": "AFTER_LAST_SIGNAL_NOT_EVALUATED",
            })
            continue
        mapped_flow[effective] += int(event["amount_vnd"])
        event_output.append({
            "contribution_date": event["contribution_date"].isoformat(),
            "amount_vnd": int(event["amount_vnd"]),
            "effective_signal_date": effective.isoformat(),
            "status": "ACCUMULATED_TO_NEXT_MONTHLY_SIGNAL",
        })

    strategy_nav = float(initial_capital_vnd)
    benchmark_nav = float(initial_capital_vnd)
    total_external_flow = 0
    monthly_rows: list[dict[str, object]] = []
    twr_factor = 1.0
    benchmark_twr_factor = 1.0
    cashflows: list[tuple[date, float]] = []
    if initial_capital_vnd > 0:
        cashflows.append((parsed[0]["signal"], -float(initial_capital_vnd)))

    for item in parsed:
        signal = item["signal"]
        flow = int(mapped_flow[signal])
        total_external_flow += flow
        if flow:
            cashflows.append((signal, -float(flow)))
        begin_strategy = strategy_nav + flow
        begin_benchmark = benchmark_nav + flow
        strategy_return = float(item["net_return_value"])
        benchmark_return = float(item["benchmark_return_value"])
        strategy_nav = begin_strategy * (1.0 + strategy_return)
        benchmark_nav = begin_benchmark * (1.0 + benchmark_return)
        twr_factor *= 1.0 + strategy_return
        benchmark_twr_factor *= 1.0 + benchmark_return
        monthly_rows.append({
            "signal_date": signal.isoformat(),
            "label_end": item["label_end_date"].isoformat(),
            "horizon_days": item["horizon_days"],
            "external_cash_flow_vnd": flow,
            "strategy_begin_value_vnd": begin_strategy,
            "strategy_net_return": strategy_return,
            "strategy_end_value_vnd": strategy_nav,
            "benchmark_begin_value_vnd": begin_benchmark,
            "benchmark_return": benchmark_return,
            "benchmark_end_value_vnd": benchmark_nav,
            "wealth_advantage_vnd": strategy_nav - benchmark_nav,
        })

    end_date = parsed[-1]["label_end_date"]
    cashflows.append((end_date, strategy_nav))
    mwr = _xirr(cashflows)
    total_invested = initial_capital_vnd + total_external_flow
    status = (
        "EXTENDED_MONTHLY_HISTORY_READY"
        if len(parsed) >= minimum_periods
        else "INSUFFICIENT_MONTHLY_HISTORY"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "period_count": len(parsed),
        "minimum_required_periods": minimum_periods,
        "monthly_horizon_verified": True,
        "minimum_horizon_days": min(int(item["horizon_days"]) for item in parsed),
        "maximum_horizon_days": max(int(item["horizon_days"]) for item in parsed),
        "evaluation_start": parsed[0]["signal"].isoformat(),
        "evaluation_end": end_date.isoformat(),
        "initial_capital_vnd": initial_capital_vnd,
        "mapped_contributions_vnd": total_external_flow,
        "unmapped_contributions_vnd": unmapped,
        "total_invested_vnd": total_invested,
        "strategy_terminal_wealth_vnd": strategy_nav,
        "benchmark_terminal_wealth_vnd": benchmark_nav,
        "strategy_profit_vnd": strategy_nav - total_invested,
        "benchmark_profit_vnd": benchmark_nav - total_invested,
        "terminal_wealth_advantage_vnd": strategy_nav - benchmark_nav,
        "time_weighted_return": twr_factor - 1.0,
        "benchmark_time_weighted_return": benchmark_twr_factor - 1.0,
        "relative_time_weighted_return": (
            twr_factor / benchmark_twr_factor - 1.0
            if benchmark_twr_factor > 0 else 0.0
        ),
        "money_weighted_return_xirr": mwr,
        "contribution_execution_policy": "ACCUMULATE_UNTIL_NEXT_MONTHLY_SIGNAL",
        "t_plus_one_role": "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
        "historical_gate_passed": len(parsed) >= minimum_periods,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "monthly_rows": monthly_rows,
        "contribution_rows": event_output,
    }


def evaluate_archive(
    *,
    model_lab_output: Path,
    output_dir: Path,
    contribution_rows: Sequence[Mapping[str, object]],
    initial_capital_vnd: int = 0,
    minimum_periods: int = 48,
    model: str | None = None,
) -> dict[str, object]:
    summary, period_rows, archive_sha = _verified_archive(model_lab_output)
    champion = str(
        model
        or summary.get("historical_reference_model")
        or summary.get("research_champion")
        or ""
    )
    if not champion or champion == "NO_MODEL_APPROVED":
        raise ValueError("CONTRIBUTION_REFERENCE_MODEL_INVALID")
    filtered = [
        row
        for row in period_rows
        if str(row.get("model") or row.get("selected_model") or "") == champion
        and str(row.get("cost_scenario") or "BASE") == "BASE"
    ]
    result = evaluate_monthly_contributions(
        period_rows=filtered,
        contribution_rows=contribution_rows,
        initial_capital_vnd=initial_capital_vnd,
        minimum_periods=minimum_periods,
    )
    result.update({
        "reference_model": champion,
        "source_model_lab_schema": summary.get("upgrade_schema_version"),
        "source_archive_sha256": archive_sha,
    })

    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"CONTRIBUTION_OUTPUT_EXISTS:{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        monthly_rows = list(result.pop("monthly_rows"))
        events = list(result.pop("contribution_rows"))
        payloads = {
            "contribution_evaluation_v17.json": _json_bytes(result),
            "contribution_monthly_periods_v17.csv": _csv_bytes(
                monthly_rows,
                tuple(monthly_rows[0]) if monthly_rows else ("signal_date",),
            ),
            "contribution_events_v17.csv": _csv_bytes(
                events,
                tuple(events[0]) if events else (
                    "contribution_date",
                    "amount_vnd",
                    "effective_signal_date",
                    "status",
                ),
            ),
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "credentials_recorded": False,
            "live_trading_enabled": False,
            "files": {
                name: {"sha256": _sha(payload), "size": len(payload)}
                for name, payload in payloads.items()
            },
        }
        payloads["manifest.json"] = _json_bytes(manifest)
        for name, payload in payloads.items():
            (staging / name).write_bytes(payload)
        archive_path = staging / "contribution_evaluation_v17.zip"
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
            for name in sorted(payloads):
                archive.write(staging / name, arcname=name)
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        **result,
        "output_dir": str(destination),
        "output_zip": str(destination / "contribution_evaluation_v17.zip"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.contribution_evaluation_v17"
    )
    parser.add_argument("--model-lab-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital-vnd", type=int, default=0)
    parser.add_argument("--minimum-periods", type=int, default=48)
    parser.add_argument("--model")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--contributions-csv", type=Path)
    source.add_argument("--contribution-amount-vnd", type=int)
    parser.add_argument("--contribution-every-days", type=int, default=14)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary, periods, _ = _verified_archive(args.model_lab_output)
    champion = str(
        args.model
        or summary.get("historical_reference_model")
        or summary.get("research_champion")
        or ""
    )
    candidate = [
        row
        for row in periods
        if str(row.get("model") or row.get("selected_model") or "") == champion
        and str(row.get("cost_scenario") or "BASE") == "BASE"
    ]
    if not candidate:
        raise ValueError("CONTRIBUTION_REFERENCE_PERIODS_MISSING")
    start = min(_date(row["signal_date"], "CONTRIBUTION_SIGNAL_DATE_INVALID") for row in candidate)
    end = max(_date(row["signal_date"], "CONTRIBUTION_SIGNAL_DATE_INVALID") for row in candidate)
    if args.contributions_csv:
        events = _load_contributions(args.contributions_csv)
    else:
        events = generate_periodic_contributions(
            start=start,
            end=end,
            amount_vnd=int(args.contribution_amount_vnd),
            every_days=args.contribution_every_days,
        )
    result = evaluate_archive(
        model_lab_output=args.model_lab_output,
        output_dir=args.output_dir,
        contribution_rows=events,
        initial_capital_vnd=args.initial_capital_vnd,
        minimum_periods=args.minimum_periods,
        model=args.model,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
