from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong.paper_trading_reference_v16 import run


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _policy() -> dict[str, object]:
    return {
        "schema_version": "vn_quant_reference_policy_v16",
        "status": "FROZEN_HISTORICAL_REFERENCE",
        "policy_id": "v15-test",
        "model": {"champion": "online_rank_ensemble_v1"},
        "permissions": {
            "paper_trading_allowed": True,
            "live_capital_approved": False,
        },
    }


def _monitor(*, blocked: bool = False) -> dict[str, object]:
    return {
        "schema_version": "vn_quant_paper_monitor_v16",
        "status": "MODEL_UNDER_REVIEW" if blocked else "PAPER_WARMUP",
        "policy_id": "v15-test",
        "block_new_positions": blocked,
        "kill_switch_triggers": ["TEST"] if blocked else [],
        "live_capital_approved": False,
    }


class GuardedPaperTradingTests(unittest.TestCase):
    def test_dnse_defaults_and_frozen_champion_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy_path = root / "policy.json"
            monitor_path = root / "monitor.json"
            _write_json(policy_path, _policy())
            _write_json(monitor_path, _monitor())
            with patch(
                "he_thong_dinh_luong.paper_trading_reference_v16.base._load_daily_signal",
                return_value=([
                    {"champion_model": "online_rank_ensemble_v1"}
                ], {}, "sha"),
            ), patch(
                "he_thong_dinh_luong.paper_trading_reference_v16.base.run",
                return_value={"status": "SUCCESS"},
            ) as base_run:
                result = run(
                    daily_output=root / "daily.zip",
                    publication_dir=root / "publication",
                    state_dir=root / "state",
                    policy_path=policy_path,
                    monitor_path=monitor_path,
                )
            kwargs = base_run.call_args.kwargs
            self.assertEqual(kwargs["buy_fee_bps"], Decimal("2.7"))
            self.assertEqual(kwargs["sell_fee_bps"], Decimal("3.0"))
            self.assertEqual(kwargs["sell_tax_bps"], Decimal("10"))
            self.assertEqual(kwargs["slippage_bps"], Decimal("5"))
            self.assertEqual(result["reference_model"], "online_rank_ensemble_v1")
            self.assertFalse(result["live_capital_approved"])

    def test_kill_switch_blocks_before_signal_is_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy_path = root / "policy.json"
            monitor_path = root / "monitor.json"
            _write_json(policy_path, _policy())
            _write_json(monitor_path, _monitor(blocked=True))
            with patch(
                "he_thong_dinh_luong.paper_trading_reference_v16.base.run"
            ) as base_run:
                with self.assertRaisesRegex(
                    ValueError,
                    "PAPER_REFERENCE_KILL_SWITCH_ACTIVE",
                ):
                    run(
                        daily_output=root / "daily.zip",
                        publication_dir=root / "publication",
                        state_dir=root / "state",
                        policy_path=policy_path,
                        monitor_path=monitor_path,
                    )
            base_run.assert_not_called()

    def test_daily_signal_must_match_frozen_champion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy_path = root / "policy.json"
            monitor_path = root / "monitor.json"
            _write_json(policy_path, _policy())
            _write_json(monitor_path, _monitor())
            with patch(
                "he_thong_dinh_luong.paper_trading_reference_v16.base._load_daily_signal",
                return_value=([{"champion_model": "ridge_ranker"}], {}, "sha"),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "PAPER_REFERENCE_CHAMPION_MISMATCH",
                ):
                    run(
                        daily_output=root / "daily.zip",
                        publication_dir=root / "publication",
                        state_dir=root / "state",
                        policy_path=policy_path,
                        monitor_path=monitor_path,
                    )


if __name__ == "__main__":
    unittest.main()
