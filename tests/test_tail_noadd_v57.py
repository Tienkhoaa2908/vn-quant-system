import unittest
from datetime import date

from he_thong_dinh_luong.tail_noadd_v57 import _position_loss_nav


class DummyPrices:
    def latest_close(self, symbol, day):
        return 90.0


class TailNoAddV57Tests(unittest.TestCase):
    def test_position_loss_nav_matches_portfolio_damage(self):
        value = _position_loss_nav(
            "AAA",
            2,
            100.0,
            prices=DummyPrices(),
            day=date(2026, 1, 1),
            nav=2000.0,
        )
        self.assertAlmostEqual(value, -0.01)

    def test_invalid_inputs_fail_closed_to_zero_damage(self):
        self.assertEqual(
            _position_loss_nav(
                "AAA",
                0,
                100.0,
                prices=DummyPrices(),
                day=date(2026, 1, 1),
                nav=2000.0,
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
