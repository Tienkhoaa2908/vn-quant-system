from __future__ import annotations

import unittest

from vn_quant_local import source_integrity_v49 as v49
from vn_quant_local import v59_fast_realtime as v59
from vn_quant_local import v59_market_stream as market


class _Reader:
    def __init__(self) -> None:
        self.balance_calls = 0
        self.position_calls = 0

    def accounts(self):
        return [
            {"accountNo": "ACC-ONE"},
            {"accountNo": "ACC-TWO"},
        ]

    def balances(self, account_no):
        self.balance_calls += 1
        return {"availableCash": 123}

    def positions(self, account_no):
        self.position_calls += 1
        return []


class _ModelMessage:
    def model_dump(self, by_alias=False):
        return {"symbol": "VPI", "qty": 2, "by_alias": by_alias}


class V59FastRealtimeTests(unittest.TestCase):
    def test_message_model_dump_is_supported(self) -> None:
        value = v59._message_dict(_ModelMessage())
        self.assertEqual(value["symbol"], "VPI")
        self.assertEqual(value["qty"], 2)
        self.assertTrue(value["by_alias"])

    def test_selected_account_identity_does_not_probe_balances_or_positions(self) -> None:
        reader = _Reader()
        original = v49._read_account_selection
        try:
            v49._read_account_selection = lambda: v49._account_token("ACC-TWO")
            selected, elapsed = v59._account_identity(reader)
        finally:
            v49._read_account_selection = original
        self.assertEqual(selected["account_no"], "ACC-TWO")
        self.assertEqual(reader.balance_calls, 0)
        self.assertEqual(reader.position_calls, 0)
        self.assertGreaterEqual(elapsed, 0.0)

    def test_market_message_aliases(self) -> None:
        payload = {
            "symbol": "ACB",
            "bidPrice": 22650,
            "ask_price": 22700,
            "refPrice": 22500,
        }
        self.assertEqual(market._symbol(payload), "ACB")
        self.assertEqual(market._price(payload, "bidPrice", "bid_price"), 22650)
        self.assertEqual(market._price(payload, "askPrice", "ask_price"), 22700)
        self.assertEqual(market._price(payload, "refPrice", "ref_price"), 22500)

    def test_runtime_is_read_only_by_contract(self) -> None:
        self.assertEqual(v59.REALTIME_MODE, "DNSE_TRADING_STREAM_READ_ONLY_DIAGNOSTIC")
        self.assertIn("READ_ONLY", market.V59_MARKET_VERSION)


if __name__ == "__main__":
    unittest.main()
