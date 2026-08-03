from __future__ import annotations

import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.reference_operations_v16 import (
    EXPECTED_MODEL_LAB_SCHEMA,
    EXPECTED_REFERENCE_STATUS,
    PAPER_MONITOR_SCHEMA,
    audit_historical_extension,
    evaluate_paper_observations,
    freeze_reference_policy,
)


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = StringIO(newline="")
    fields = list(rows[0])
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _v15_archive(path: Path, *, gate: bool = True) -> None:
    summary = {
        "upgrade_schema_version": EXPECTED_MODEL_LAB_SCHEMA,
        "historical_reference_status": (
            EXPECTED_REFERENCE_STATUS if gate else "REJECTED"
        ),
        "historical_reference_gate_passed": gate,
        "historical_reference_model": (
            "online_rank_ensemble_v1" if gate else "NO_MODEL_APPROVED"
        ),
        "research_champion": (
            "online_rank_ensemble_v1" if gate else "NO_MODEL_APPROVED"
        ),
        "live_capital_approved": False,
        "signal_date": "2026-07-30",
        "backtest_contract": {"costs": {"top_k": 10}},
        "nested_model_validation_v15": {
            "validation_months": 6,
            "test_months": 3,
            "protocol_provenance": "TEST",
        },
    }
    comparison = {
        "model": "online_rank_ensemble_v1",
        "gate_passed": str(gate),
        "outer_test_period_count": 18,
        "mean_rank_ic": 0.058,
        "positive_rank_ic_ratio": 0.6111,
        "outer_block_positive_net_excess_ratio": 0.6667,
        "base_net_total_return": 0.8228,
        "base_benchmark_total_return": 0.4400,
        "base_relative_total_return": 0.2658,
        "base_average_net_excess_return": 0.01517,
        "base_positive_net_excess_ratio": 0.5556,
        "base_mean_turnover": 0.35,
        "base_max_drawdown": -0.0823,
        "base_leave_best_period_out_relative_total_return": 0.0714,
        "base_best_positive_excess_contribution_share": 0.4128,
        "stress_relative_total_return": 0.2586,
    }
    selection = {
        "model": "online_rank_ensemble_v1",
        "outer_fold": "outer_01",
        "test_start": "2025-01-31",
        "selected_replacement_cap": 3,
        "candidate_caps": "0|1|2|3|4|5",
        "selection_uses_outer_test_labels": "false",
    }
    contract = {
        "evaluation_unit": "MODEL_FAMILY",
        "model_switching_inside_outer_portfolio": "False",
        "inner_selected_parameter": "MAX_VOLUNTARY_REPLACEMENTS",
        "cap_selected_only_from_prior_validation": "True",
        "continuous_holdings_across_outer_blocks": "True",
        "outer_test_blocks_non_overlapping": "True",
    }
    costs = [
        {
            "scenario": "BASE",
            "full_round_trip_bps": 25.7,
            "slippage_bps_each_side": 5.0,
            "sell_tax_bps": 10.0,
        },
        {
            "scenario": "STRESS",
            "full_round_trip_bps": 35.7,
            "slippage_bps_each_side": 10.0,
            "sell_tax_bps": 10.0,
        },
    ]
    files = {
        "model_lab_summary.json": _json_bytes(summary),
        "nested_model_historical_validation_v15.csv": _csv_bytes([comparison]),
        "nested_model_policy_selection_v15.csv": _csv_bytes([selection]),
        "nested_model_validation_contract_v15.csv": _csv_bytes([contract]),
        "dnse_cost_scenarios_v13.csv": _csv_bytes(costs),
    }
    manifest = {
        "status": "SUCCESS",
        "credentials_recorded": False,
        "signal_date": "2026-07-30",
        "files": {
            name: {"sha256": sha256(payload).hexdigest(), "size": len(payload)}
            for name, payload in files.items()
        },
    }
    files["manifest.json"] = _json_bytes(manifest)
    with ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def _policy() -> dict[str, object]:
    return {
        "schema_version": "vn_quant_reference_policy_v16",
        "status": "FROZEN_HISTORICAL_REFERENCE",
        "policy_id": "v15-test",
        "kill_switch": {
            "rolling_window": 6,
            "minimum_observations": 6,
            "mean_rank_ic_below": 0.0,
            "positive_rank_ic_ratio_below": 0.40,
            "average_net_excess_below": 0.0,
            "relative_drawdown_at_or_below": -0.12,
            "turnover_above": 0.60,
            "turnover_consecutive_periods": 3,
        },
        "permissions": {
            "paper_trading_allowed": True,
            "live_capital_approved": False,
        },
    }


def _observations(
    *,
    rank_ic: float = 0.03,
    excess: float = 0.01,
    turnover: float = 0.3,
    count: int = 6,
) -> list[dict[str, object]]:
    return [
        {
            "observation_date": f"2026-{index + 1:02d}-28",
            "policy_id": "v15-test",
            "rank_ic": rank_ic,
            "net_excess_return": excess,
            "turnover": turnover,
            "relative_nav": 1.0 + 0.01 * index,
            "contract_ok": "true",
            "data_quality_ok": "true",
        }
        for index in range(count)
    ]


class ReferenceFreezeTests(unittest.TestCase):
    def test_freeze_verified_v15_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "model_lab_output.zip"
            _v15_archive(archive)
            output = root / "policy"
            result = freeze_reference_policy(
                model_lab_archive=archive,
                output_dir=output,
                freeze_date=date(2026, 8, 1),
            )
            policy = json.loads(
                (output / "reference_policy.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["champion_model"], "online_rank_ensemble_v1")
            self.assertTrue(policy["model"]["tuning_locked"])
            self.assertEqual(policy["portfolio_policy"]["candidate_caps"], [0, 1, 2, 3, 4, 5])
            self.assertAlmostEqual(
                policy["cost_contract"]["base_full_round_trip_bps"],
                25.7,
            )
            self.assertFalse(policy["permissions"]["live_capital_approved"])

    def test_freeze_rejects_unvalidated_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "model_lab_output.zip"
            _v15_archive(archive, gate=False)
            with self.assertRaisesRegex(
                ValueError,
                "REFERENCE_FREEZE_STATUS_NOT_VALIDATED",
            ):
                freeze_reference_policy(
                    model_lab_archive=archive,
                    output_dir=root / "policy",
                    freeze_date=date(2026, 8, 1),
                )


class PaperMonitorTests(unittest.TestCase):
    def test_monitor_active_after_six_positive_observations(self):
        result = evaluate_paper_observations(_observations(), policy=_policy())
        self.assertEqual(result["schema_version"], PAPER_MONITOR_SCHEMA)
        self.assertEqual(result["status"], "PAPER_ACTIVE")
        self.assertFalse(result["block_new_positions"])

    def test_monitor_warmup_before_six_observations(self):
        result = evaluate_paper_observations(
            _observations(count=3),
            policy=_policy(),
        )
        self.assertEqual(result["status"], "PAPER_WARMUP")
        self.assertFalse(result["block_new_positions"])

    def test_negative_rolling_evidence_activates_kill_switch(self):
        result = evaluate_paper_observations(
            _observations(rank_ic=-0.02, excess=-0.01),
            policy=_policy(),
        )
        self.assertEqual(result["status"], "MODEL_UNDER_REVIEW")
        self.assertTrue(result["block_new_positions"])
        self.assertIn("ROLLING_MEAN_IC_NEGATIVE", result["kill_switch_triggers"])
        self.assertIn("ROLLING_NET_EXCESS_NEGATIVE", result["kill_switch_triggers"])

    def test_contract_violation_is_immediate(self):
        rows = _observations(count=1)
        rows[0]["contract_ok"] = "false"
        result = evaluate_paper_observations(rows, policy=_policy())
        self.assertTrue(result["block_new_positions"])
        self.assertIn("CONTRACT_VIOLATION", result["kill_switch_triggers"])


class HistoricalExtensionTests(unittest.TestCase):
    def test_complete_point_in_time_history_is_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            symbols = [f"S{index:02d}" for index in range(10)]
            warmup_start = date(2018, 1, 1)
            warmup_days: list[date] = []
            day = warmup_start
            while len(warmup_days) < 251:
                if day.weekday() < 5:
                    warmup_days.append(day)
                day += timedelta(days=1)
            monthly_days: list[date] = []
            year, month = 2020, 1
            for _ in range(48):
                monthly_days.append(date(year, month, 28))
                month += 1
                if month == 13:
                    year += 1
                    month = 1
            price_days = warmup_days + monthly_days
            prices: list[dict[str, object]] = []
            for symbol in symbols:
                for index, price_day in enumerate(price_days):
                    close = 10.0 + index / 1000.0
                    prices.append({
                        "ma": symbol,
                        "ngay": price_day.isoformat(),
                        "gia_mo_cua": close,
                        "gia_cao_nhat": close + 1.0,
                        "gia_thap_nhat": close - 1.0,
                        "gia_dong_cua": close + 0.1,
                        "khoi_luong": 1000,
                        "nguon": "fixture",
                        "phien_ban": "1",
                        "co_so_gia": "gia_dieu_chinh",
                    })
            benchmark = [
                {
                    "ma": "VNINDEX",
                    "ngay": signal.isoformat(),
                    "gia_dong_cua": 1000 + index,
                }
                for index, signal in enumerate(monthly_days)
            ]
            universe = [
                {
                    "ngay_hieu_luc": "2017-01-01",
                    "ma": symbol,
                    "thuoc_universe": "true",
                    "nguon": "fixture",
                    "phien_ban": "1",
                    "thoi_diem_cong_bo": "2016-12-01T00:00:00+07:00",
                }
                for symbol in symbols
            ]
            _write_csv(root / "prices.csv", prices)
            _write_csv(root / "benchmark.csv", benchmark)
            _write_csv(root / "universe.csv", universe)
            result = audit_historical_extension(
                price_path=root / "prices.csv",
                benchmark_path=root / "benchmark.csv",
                universe_path=root / "universe.csv",
                metadata_pit_path=None,
                output_dir=root / "audit",
                minimum_train_months=24,
                validation_months=3,
                target_outer_test_months=12,
                minimum_eligible_symbols=10,
                minimum_monthly_coverage=0.95,
                required_warmup_sessions=251,
            )
            self.assertTrue(result["extended_v15_ready"])
            self.assertGreaterEqual(result["estimated_outer_test_months"], 12)


if __name__ == "__main__":
    unittest.main()
