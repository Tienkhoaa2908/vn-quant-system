from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vn_quant_local.capital_plan import _ensure_schema as ensure_capital_schema
from vn_quant_local import performance
from vn_quant_local.performance_safety import select_plans_after_opening


class V46EventPlanningTests(unittest.TestCase):
    def test_capital_plan_schema_is_additive(self) -> None:
        db = sqlite3.connect(":memory:")
        try:
            ensure_capital_schema(db)
            ensure_capital_schema(db)
            columns = {
                row[1]
                for row in db.execute("PRAGMA table_info(capital_plans)").fetchall()
            }
        finally:
            db.close()
        self.assertTrue(
            {
                "cycle_id",
                "plan_id",
                "created_at",
                "new_capital_vnd",
                "details_json",
            }.issubset(columns)
        )

    def test_two_cycles_in_same_week_are_both_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"

            @contextmanager
            def temporary_state_db():
                db = sqlite3.connect(database)
                db.row_factory = sqlite3.Row
                try:
                    yield db
                    db.commit()
                finally:
                    db.close()

            with patch(
                "vn_quant_local.performance_safety.state_db",
                temporary_state_db,
            ), patch(
                "vn_quant_local.capital_plan.state_db",
                temporary_state_db,
            ), patch(
                "vn_quant_local.performance._next_session",
                return_value="2026-08-05",
            ):
                with temporary_state_db() as db:
                    performance._ensure_schema(db)
                    ensure_capital_schema(db)
                    for index, hour in enumerate(("09", "14"), start=1):
                        plan = {
                            "plan_id": f"plan-{index}",
                            "buy_orders": [
                                {
                                    "symbol": "FPT",
                                    "quantity": index,
                                }
                            ],
                            "position_reviews": [],
                            "exit_candidates": [],
                            "rationale": {"maximum_buy_orders": 3},
                        }
                        db.execute(
                            """
                            INSERT INTO capital_plans VALUES(?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                f"cycle-{index}",
                                f"plan-{index}",
                                f"2026-08-04T{hour}:00:00+07:00",
                                "NEW_CAPITAL",
                                250_000.0,
                                "broker-test",
                                "2026-08-04",
                                "model-test",
                                None,
                                json.dumps(plan),
                            ),
                        )
                select_plans_after_opening(
                    {"started_at": "2026-08-04T08:00:00+07:00"}
                )
                with temporary_state_db() as db:
                    rows = db.execute(
                        """
                        SELECT week_key,planned_contribution_vnd
                        FROM performance_shadow_plans
                        ORDER BY created_at
                        """
                    ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                [row[0] for row in rows],
                ["CYCLE:cycle-1", "CYCLE:cycle-2"],
            )
            self.assertEqual(sum(row[1] for row in rows), 500_000.0)

    def test_cycle_before_opening_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"

            @contextmanager
            def temporary_state_db():
                db = sqlite3.connect(database)
                db.row_factory = sqlite3.Row
                try:
                    yield db
                    db.commit()
                finally:
                    db.close()

            with patch(
                "vn_quant_local.performance_safety.state_db",
                temporary_state_db,
            ), patch(
                "vn_quant_local.capital_plan.state_db",
                temporary_state_db,
            ):
                with temporary_state_db() as db:
                    performance._ensure_schema(db)
                    ensure_capital_schema(db)
                    db.execute(
                        "INSERT INTO capital_plans VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            "cycle-old",
                            "plan-old",
                            "2026-08-04T07:00:00+07:00",
                            "NEW_CAPITAL",
                            250_000.0,
                            None,
                            "2026-08-04",
                            "model-test",
                            None,
                            json.dumps({"plan_id": "plan-old"}),
                        ),
                    )
                select_plans_after_opening(
                    {"started_at": "2026-08-04T08:00:00+07:00"}
                )
                with temporary_state_db() as db:
                    count = db.execute(
                        "SELECT COUNT(*) FROM performance_shadow_plans"
                    ).fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
