from __future__ import annotations

import csv
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.model_lab_reference_signal_v16 import (
    publish_reference_signal,
    select_forward_cap,
    select_forward_symbols,
)
from he_thong_dinh_luong.model_lab_upgrade_v13 import DnseCashCostConfig
from he_thong_dinh_luong.paper_trading_daily import _load_daily_signal


SYMBOLS = tuple("ABCDEFGHIJKL")


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _prediction_rows() -> list[dict[str, object]]:
    dates = (
        "2025-11-28",
        "2025-12-31",
        "2026-01-30",
        "2026-02-27",
        "2026-03-31",
        "2026-04-29",
        "2026-05-29",
        "2026-06-30",
    )
    rows: list[dict[str, object]] = []
    for day_index, day in enumerate(dates):
        ordered = SYMBOLS if day_index % 2 == 0 else tuple(reversed(SYMBOLS))
        rank_by_symbol = {
            symbol: index + 1 for index, symbol in enumerate(ordered)
        }
        for symbol in SYMBOLS:
            rank = rank_by_symbol[symbol]
            stock_return = 0.03 - rank * 0.002
            rows.append({
                "model": "online_rank_ensemble_v1",
                "fold": f"wf_{day}",
                "test_date": day,
                "symbol": symbol,
                "score": float(len(SYMBOLS) - rank),
                "percentile": 1.0 - (rank - 1) / len(SYMBOLS),
                "rank": rank,
                "selected_top_k": str(rank <= 10).lower(),
                "label_end": day,
                "stock_return": stock_return,
                "benchmark_return": 0.0,
                "relative_return": stock_return,
            })
    return rows


def _forward_rows() -> list[dict[str, object]]:
    return [
        {
            "signal_date": "2026-07-30",
            "model": "online_rank_ensemble_v1",
            "symbol": symbol,
            "score": float(len(SYMBOLS) - index),
            "percentile": 1.0 - index / len(SYMBOLS),
            "rank": index + 1,
            "selected_top_k": str(index < 10).lower(),
            "research_champion": "online_rank_ensemble_v1",
            "reference_model": "online_rank_ensemble_v1",
            "live_capital_approved": "false",
            "diagnostic_top_k": str(index < 10).lower(),
            "research_approved": "true",
            "quality_status": "PASS",
        }
        for index, symbol in enumerate(SYMBOLS)
    ]


def _model_lab_archive(path: Path) -> None:
    summary = {
        "upgrade_schema_version": "vn_quant_model_lab_upgrade_v15",
        "nested_model_validation_contract_v15": {
            "evaluation_unit": "MODEL_FAMILY",
            "model_switching_inside_outer_portfolio": False,
            "cap_selected_only_from_prior_validation": True,
        },
    }
    validation = [{"model": "online_rank_ensemble_v1", "gate_passed": "true"}]
    selection = [{
        "model": "online_rank_ensemble_v1",
        "outer_fold": "outer_01",
        "test_start": "2026-01-30",
        "selected_replacement_cap": 3,
        "candidate_caps": "0|1|2|3|4|5",
        "selection_uses_outer_test_labels": "false",
    }]
    contract = [{
        "evaluation_unit": "MODEL_FAMILY",
        "model_switching_inside_outer_portfolio": "False",
        "inner_selected_parameter": "MAX_VOLUNTARY_REPLACEMENTS",
        "cap_selected_only_from_prior_validation": "True",
        "continuous_holdings_across_outer_blocks": "True",
        "outer_test_blocks_non_overlapping": "True",
    }]
    costs = [
        {
            "scenario": "BASE",
            "buy_fee_bps_ex_slippage": 2.7,
            "sell_fee_bps_ex_tax_slippage": 3.0,
            "sell_tax_bps": 10.0,
            "slippage_bps_each_side": 5.0,
            "full_round_trip_bps": 25.7,
        },
        {
            "scenario": "STRESS",
            "buy_fee_bps_ex_slippage": 2.7,
            "sell_fee_bps_ex_tax_slippage": 3.0,
            "sell_tax_bps": 10.0,
            "slippage_bps_each_side": 10.0,
            "full_round_trip_bps": 35.7,
        },
    ]
    files = {
        "model_lab_summary.json": _json_bytes(summary),
        "nested_model_historical_validation_v15.csv": _csv_bytes(validation),
        "nested_model_policy_selection_v15.csv": _csv_bytes(selection),
        "nested_model_validation_contract_v15.csv": _csv_bytes(contract),
        "dnse_cost_scenarios_v13.csv": _csv_bytes(costs),
        "oos_predictions.csv": _csv_bytes(_prediction_rows()),
        "forward_model_scores.csv": _csv_bytes(_forward_rows()),
    }
    manifest = {
        "status": "SUCCESS",
        "credentials_recorded": False,
        "files": {
            name: {"sha256": sha256(payload).hexdigest(), "size": len(payload)}
            for name, payload in files.items()
        },
    }
    files["manifest.json"] = _json_bytes(manifest)
    with ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def _policy(path: Path) -> None:
    value = {
        "schema_version": "vn_quant_reference_policy_v16",
        "status": "FROZEN_HISTORICAL_REFERENCE",
        "policy_id": "v15-test",
        "source": {"archive_sha256": "fixture"},
        "model": {
            "champion": "online_rank_ensemble_v1",
            "top_k": 10,
        },
        "portfolio_policy": {
            "candidate_caps": [0, 1, 2, 3, 4, 5],
            "validation_months": 6,
        },
        "cost_contract": {
            "base_full_round_trip_bps": 25.7,
            "stress_full_round_trip_bps": 35.7,
            "base_slippage_bps_each_side": 5.0,
            "stress_slippage_bps_each_side": 10.0,
            "sell_tax_bps": 10.0,
        },
        "permissions": {
            "paper_trading_allowed": True,
            "live_capital_approved": False,
        },
    }
    path.write_text(json.dumps(value), encoding="utf-8")


class ReferenceSignalSelectionTests(unittest.TestCase):
    def test_retention_cap_keeps_seven_previous_symbols(self):
        selected, forced, voluntary = select_forward_symbols(
            list("KLMABCDEFGHIJ"),
            previous_symbols=list("ABCDEFGHIJ"),
            top_k=10,
            max_voluntary_replacements=3,
        )
        self.assertEqual(forced, 0)
        self.assertEqual(voluntary, 3)
        self.assertEqual(
            set(selected),
            {"A", "B", "C", "D", "E", "F", "G", "K", "L", "M"},
        )

    def test_forced_exits_do_not_consume_cap(self):
        selected, forced, voluntary = select_forward_symbols(
            list("KLMNOABCDEPQ"),
            previous_symbols=list("ABCDEFGHIJ"),
            top_k=10,
            max_voluntary_replacements=3,
        )
        self.assertEqual(forced, 5)
        self.assertEqual(voluntary, 0)
        self.assertEqual(len(selected), 10)

    def test_cap_selection_uses_completed_dates_only(self):
        rows = _prediction_rows()
        cap, _, validation_dates = select_forward_cap(
            rows,
            champion="online_rank_ensemble_v1",
            signal_date=date(2026, 7, 30),
            top_k=10,
            candidate_caps=(0, 1, 2, 3, 4, 5),
            validation_months=6,
            cost=DnseCashCostConfig(),
        )
        self.assertIn(cap, range(6))
        self.assertEqual(len(validation_dates), 6)
        self.assertLess(validation_dates[-1], "2026-07-30")


class ReferenceSignalPublisherTests(unittest.TestCase):
    def test_publisher_outputs_paper_trading_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "model_lab_output.zip"
            policy = root / "reference_policy.json"
            output = root / "reference_signal.zip"
            state = root / "state"
            _model_lab_archive(archive)
            _policy(policy)
            result = publish_reference_signal(
                model_lab_archive=archive,
                policy_path=policy,
                state_dir=state,
                output_zip=output,
            )
            rows, manifest, _ = _load_daily_signal(output)
            self.assertEqual(result["champion_model"], "online_rank_ensemble_v1")
            self.assertEqual(len(rows), 10)
            self.assertEqual(
                {row["champion_model"] for row in rows},
                {"online_rank_ensemble_v1"},
            )
            self.assertEqual(
                sum(float(row["target_weight_pct"]) for row in rows),
                100.0,
            )
            self.assertEqual(manifest["schema_version"], "model_lab_reference_signal_v16")
            state_value = json.loads(
                (state / "reference_signal_state_v16.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(state_value["latest_signal_date"], "2026-07-30")
            self.assertFalse(result["live_capital_approved"])

    def test_same_signal_date_cannot_be_published_twice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "model_lab_output.zip"
            policy = root / "reference_policy.json"
            state = root / "state"
            _model_lab_archive(archive)
            _policy(policy)
            publish_reference_signal(
                model_lab_archive=archive,
                policy_path=policy,
                state_dir=state,
                output_zip=root / "signal-1.zip",
            )
            with self.assertRaisesRegex(
                ValueError,
                "REFERENCE_SIGNAL_NOT_AFTER_STATE",
            ):
                publish_reference_signal(
                    model_lab_archive=archive,
                    policy_path=policy,
                    state_dir=state,
                    output_zip=root / "signal-2.zip",
                )


if __name__ == "__main__":
    unittest.main()
