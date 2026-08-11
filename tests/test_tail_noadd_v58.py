import unittest
from datetime import date

from he_thong_dinh_luong.tail_noadd_v58 import (
    LOSS_DECISION_TIMING,
    causal_loss_observation,
    previous_session_day,
)


class DummyPrices:
    def __init__(self):
        self.closes = {
            ("AAA", date(2026, 1, 2)): 95.0,
            ("AAA", date(2026, 1, 5)): 80.0,
        }

    def latest_close(self, symbol, day):
        return self.closes.get((symbol, day))


class TailNoAddV58Tests(unittest.TestCase):
    def test_previous_session_is_strictly_before_execution(self):
        calendar = [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 5),
        ]
        observed = previous_session_day(calendar, date(2026, 1, 5))
        self.assertEqual(observed, date(2026, 1, 2))
        self.assertLess(observed, date(2026, 1, 5))

    def test_current_session_close_cannot_trigger_current_open_block(self):
        prices = DummyPrices()
        calendar = [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 5),
        ]
        observation_day, loss_nav = causal_loss_observation(
            "AAA",
            2,
            100.0,
            prices=prices,
            calendar=calendar,
            execution_day=date(2026, 1, 5),
            nav=2000.0,
        )
        self.assertEqual(observation_day, date(2026, 1, 2))
        self.assertAlmostEqual(loss_nav, -0.005)
        self.assertGreater(loss_nav, -0.01)
        self.assertEqual(
            LOSS_DECISION_TIMING,
            "PREVIOUS_SESSION_CLOSE_TO_CURRENT_OPEN",
        )

    def test_first_session_has_no_loss_observation(self):
        prices = DummyPrices()
        calendar = [date(2026, 1, 5)]
        observation_day, loss_nav = causal_loss_observation(
            "AAA",
            2,
            100.0,
            prices=prices,
            calendar=calendar,
            execution_day=date(2026, 1, 5),
            nav=2000.0,
        )
        self.assertIsNone(observation_day)
        self.assertEqual(loss_nav, 0.0)


if __name__ == "__main__":
    unittest.main()
