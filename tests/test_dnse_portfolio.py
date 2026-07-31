from __future__ import annotations

from datetime import date, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import zoneinfo

FIXED_VN_TZ = timezone(timedelta(hours=7))
try:
    zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except zoneinfo.ZoneInfoNotFoundError:
    _original_zoneinfo = zoneinfo.ZoneInfo
    zoneinfo.ZoneInfo = lambda _key: FIXED_VN_TZ  # type: ignore[assignment]
    try:
        from he_thong_dinh_luong.dnse_portfolio import DnseReadOnlyClient, sync_portfolio
        from he_thong_dinh_luong.eod_hang_ngay import EodRow
    finally:
        zoneinfo.ZoneInfo = _original_zoneinfo  # type: ignore[assignment]
else:
    from he_thong_dinh_luong.dnse_portfolio import DnseReadOnlyClient, sync_portfolio
    from he_thong_dinh_luong.eod_hang_ngay import EodRow
from he_thong_dinh_luong.technical_indicators import compute_indicators


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        return self.payload


class _HttpClient:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.closed = False

    def get(self, path: str, **kwargs: object) -> _Response:
        self.paths.append(path)
        if path == "/accounts":
            return _Response({"accounts": [{"id": "0000123456", "accountType": "STOCK"}]})
        if path.endswith("/balances"):
            return _Response({"stock": {"availableCash": 5_000_000, "totalCash": 6_000_000, "totalDebt": 0}})
        if path.endswith("/positions"):
            return _Response({"positions": [{
                "symbol": "AAA", "openQuantity": 1000, "tradeQuantity": 900,
                "costPrice": 10000, "marketPrice": 12000, "status": "OPEN",
            }]})
        return _Response({"status": "ok"})

    def close(self) -> None:
        self.closed = True


class _ReadClient:
    def accounts(self):
        return [{"id": "0000123456", "accountType": "STOCK"}]

    def balances(self, account_no: str):
        self.account_no = account_no
        return {"stock": {"availableCash": 5_000_000, "totalCash": 6_000_000, "totalDebt": 0}}

    def positions(self, account_no: str):
        return [{
            "symbol": "AAA", "openQuantity": 1000, "tradeQuantity": 900,
            "costPrice": 10000, "marketPrice": 12000, "status": "OPEN",
        }]

    def market_context(self, symbol: str):
        return {"latest_trade": {"symbol": symbol}, "errors": {}}

    def close(self) -> None:
        pass


class _MarketSource:
    def __init__(self) -> None:
        start = date(2025, 1, 1)
        self.rows = []
        for index in range(320):
            close = 10.0 + index * 0.01
            self.rows.append(EodRow(
                symbol="AAA",
                day=start + timedelta(days=index),
                open=close - 0.05,
                high=close + 0.10,
                low=close - 0.10,
                close=close,
                volume=1_000_000 + index * 1000,
                source="dnse_openapi",
                version="0.5.0",
            ))

    def fetch(self, symbol: str, start: date, end: date, *, is_index: bool = False):
        return tuple(row for row in self.rows if start <= row.day <= end)

    def close(self) -> None:
        pass


class IndicatorTests(unittest.TestCase):
    def test_indicator_pack_has_long_horizon_and_finite_outputs(self) -> None:
        rows = _MarketSource().rows
        result = compute_indicators(rows)
        self.assertEqual(result["bar_count"], 320)
        self.assertIsNotNone(result["ma250"])
        self.assertIsNotNone(result["rsi14"])
        self.assertIsNotNone(result["macd_histogram"])
        self.assertIsNotNone(result["atr14_pct"])
        self.assertTrue(result["above_ma250"])
        self.assertGreater(float(result["trend_score"]), 0.5)


class ReadOnlyClientTests(unittest.TestCase):
    def test_only_allowlisted_get_endpoints_and_no_secret_in_repr(self) -> None:
        transport = _HttpClient()
        with patch("he_thong_dinh_luong.dnse_portfolio.metadata.version", return_value="0.5.0"):
            client = DnseReadOnlyClient(
                "API_KEY_VALUE", "API_SECRET_VALUE",
                client_factory=lambda *_: transport,
            )
        self.assertEqual(len(client.accounts()), 1)
        self.assertEqual(len(client.positions("0000123456")), 1)
        with self.assertRaisesRegex(ValueError, "DNSE_READ_ONLY_ENDPOINT_REJECTED"):
            client.get("/orders")
        self.assertNotIn("API_SECRET_VALUE", repr(client))
        client.close()
        self.assertTrue(transport.closed)


class PortfolioSyncTests(unittest.TestCase):
    def _write_analysis(self, root: Path) -> None:
        run = root / "anytime-web-test"
        (run / "prediction").mkdir(parents=True)
        (run / "manifest.json").write_text(json.dumps({"status": "SUCCESS"}), encoding="utf-8")
        (run / "prediction" / "latest_prediction.csv").write_text(
            "symbol,ranking_model,ranking_rank,ranking_score,champion_model,above_ma250\n"
            "AAA,robust_technical_ensemble_v1,1,0.9,momentum_baseline,true\n",
            encoding="utf-8",
        )
        (run / "paper_portfolio.csv").write_text(
            "symbol,target_weight_pct\nAAA,10\n", encoding="utf-8"
        )
        (run / "prediction" / "model_comparison.json").write_text(json.dumps({
            "market_regime": "NEUTRAL",
            "capital_budget_pct": 30,
            "champion_model": "momentum_baseline",
            "ranking_model": "robust_technical_ensemble_v1",
            "robust_validation_status": "PASS",
            "research_eligible": False,
        }), encoding="utf-8")

    def test_sync_masks_account_and_never_records_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_analysis(root)
            output = root / "portfolio-output"
            result = sync_portfolio(
                data_root=root,
                output_dir=output,
                account_no="0000123456",
                read_client=_ReadClient(),
                market_source=_MarketSource(),
                sync_local_planner=False,
                include_market_context=True,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["position_count"], 1)
            summary = json.loads((output / "portfolio_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["masked_account"], "******3456")
            row = (output / "portfolio_analysis.csv").read_text(encoding="utf-8-sig")
            self.assertIn("rsi14", row)
            self.assertIn("target_gap_vnd", row)
            for path in output.iterdir():
                if path.is_file():
                    content = path.read_bytes()
                    self.assertNotIn(b"0000123456", content)
                    self.assertNotIn(b"API_SECRET", content)
            with ZipFile(output / "dnse_portfolio_analysis.zip") as archive:
                self.assertNotIn("raw.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
