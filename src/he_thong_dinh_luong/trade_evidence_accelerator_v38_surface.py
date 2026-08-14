"""Decision-surface extraction for V38."""
from __future__ import annotations

from typing import Mapping, Sequence

EXPECTED_PERIODS = 51
EXPECTED_BREADTH = 10


def selected_symbols(row: Mapping[str, str]) -> list[str]:
    raw = (
        row.get("rebuilt_selected_symbols")
        or row.get("expected_selected_symbols")
        or row.get("selected_symbols")
        or ""
    )
    symbols = [value.strip().upper() for value in str(raw).split("|") if value.strip()]
    if len(symbols) != EXPECTED_BREADTH or len(set(symbols)) != len(symbols):
        raise ValueError(f"V38_SELECTION_BREADTH_INVALID:{row.get('signal_date')}")
    return symbols


def build_decision_surface(
    selection_rows: Sequence[Mapping[str, str]],
    benchmark_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    selections = sorted(selection_rows, key=lambda row: str(row.get("signal_date") or ""))
    if len(selections) != EXPECTED_PERIODS:
        raise ValueError(f"V38_EXPECTED_51_SELECTION_PERIODS:{len(selections)}")
    if not all(
        str(row.get("exact_order_match") or "").strip().lower() in {"true", "1"}
        for row in selections
    ):
        raise ValueError("V38_SELECTION_LINEAGE_NOT_EXACT")

    execution_dates = sorted(
        {
            str(row.get("day") or "")[:10]
            for row in benchmark_rows
            if str(row.get("required") or "").strip().lower() in {"true", "1"}
            and str(row.get("covered") or "").strip().lower() in {"true", "1"}
            and str(row.get("day") or "")
        }
    )
    if len(execution_dates) != EXPECTED_PERIODS + 1:
        raise ValueError(f"V38_EXPECTED_52_EXECUTION_DATES:{len(execution_dates)}")

    sector_keys: list[dict[str, object]] = []
    action_windows: list[dict[str, object]] = []
    unique_symbols: set[str] = set()
    for index, row in enumerate(selections):
        signal_date = str(row.get("signal_date") or "")[:10]
        start, end = execution_dates[index], execution_dates[index + 1]
        for symbol in selected_symbols(row):
            unique_symbols.add(symbol)
            sector_keys.append({
                "signal_date": signal_date,
                "execution_day": start,
                "symbol": symbol,
                "sector": "",
                "effective_from": "",
                "effective_to": "",
                "source_url": "",
                "source_document_date": "",
                "verified": False,
            })
            action_windows.append({
                "signal_date": signal_date,
                "holding_start": start,
                "holding_end": end,
                "symbol": symbol,
                "source_checked": False,
                "event_count": "",
                "source_url": "",
                "verified_complete": False,
            })

    price_dates = [{
        "execution_day": day,
        "price_basis_mode": "RAW_UNADJUSTED_EXECUTION_PRICES",
        "price_unit_vnd_multiplier": "",
        "official_source_url": "",
        "crosscheck_symbol_count": "",
        "verified": False,
    } for day in execution_dates]
    return {
        "sector_keys": sector_keys,
        "action_windows": action_windows,
        "price_dates": price_dates,
        "period_count": len(selections),
        "position_time_key_count": len(sector_keys),
        "holding_window_count": len(action_windows),
        "unique_symbol_count": len(unique_symbols),
        "execution_date_count": len(execution_dates),
        "first_execution_day": execution_dates[0],
        "last_execution_day": execution_dates[-1],
        "unique_symbols": sorted(unique_symbols),
    }
