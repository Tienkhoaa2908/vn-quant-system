from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong.v40_research_robustness import (
    DECISION_FILE,
    MANIFEST_FILE,
    PROTOCOL_FILE,
    SCORECARD_FILE,
    analyze_v40,
)


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _bundle(path: Path, *, corrupt_manifest_hash: bool = False) -> None:
    periods: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for strategy, scale in (
        ("FROZEN_SELECTION_FULLY_INVESTED", 1.0),
        ("MVP_REGIME_CASH_OVERLAY_DIAGNOSTIC", 0.6),
    ):
        for scenario, drag in (("BASE", 0.0), ("STRESS", 0.002)):
            values = []
            benchmark = []
            nav = 1_000_000_000.0
            peak = nav
            drawdown = 0.0
            for index in range(12):
                bench = 0.003 if index % 3 else -0.005
                ret = scale * (0.012 + 0.002 * (index % 4)) - drag
                values.append(ret)
                benchmark.append(bench)
                nav *= 1.0 + ret
                peak = max(peak, nav)
                drawdown = min(drawdown, nav / peak - 1.0)
                periods.append({
                    "strategy": strategy,
                    "scenario": scenario,
                    "signal_date": f"2025-{index + 1:02d}-01",
                    "period_net_return": ret,
                    "benchmark_return": bench,
                    "net_excess_return": ret - bench,
                })
            benchmark_total = 1.0
            for value in benchmark:
                benchmark_total *= 1.0 + value
            benchmark_total -= 1.0
            summaries.append({
                "strategy": strategy,
                "scenario": scenario,
                "net_total_return": nav / 1_000_000_000.0 - 1.0,
                "benchmark_total_return": benchmark_total,
                "relative_total_return": nav / 1_000_000_000.0 / (1.0 + benchmark_total) - 1.0,
                "max_drawdown": drawdown,
            })

    members = {
        "research_ledger_assumptions_v39.json": (
            json.dumps({
                "status": "RESEARCH_ONLY_COMPUTED",
                "policy_id": "test-policy",
            }, sort_keys=True).encode()
        ),
        "research_ledger_report_v39.json": (
            json.dumps({
                "strict_blockers": ["TEST_STRICT_BLOCKER"],
            }, sort_keys=True).encode()
        ),
        "research_ledger_periods_v39.csv": _csv_bytes(
            periods,
            (
                "strategy", "scenario", "signal_date", "period_net_return",
                "benchmark_return", "net_excess_return",
            ),
        ),
        "research_ledger_summary_v39.csv": _csv_bytes(
            summaries,
            (
                "strategy", "scenario", "net_total_return",
                "benchmark_total_return", "relative_total_return", "max_drawdown",
            ),
        ),
    }
    manifest_rows = []
    for name, payload in sorted(members.items()):
        digest = sha256(payload).hexdigest()
        if corrupt_manifest_hash and name == "research_ledger_periods_v39.csv":
            digest = "0" * 64
        manifest_rows.append({
            "path": name,
            "sha256": digest,
            "size_bytes": len(payload),
        })
    manifest = {
        "schema_version": "vn_quant_v39_research_ledger_analysis_manifest_v1",
        "files": manifest_rows,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    members["manifest_v39.json"] = json.dumps(manifest, sort_keys=True).encode()
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class V40ResearchRobustnessTest(unittest.TestCase):
    def test_builds_fail_closed_shadow_paper_pack(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "v39.zip"
            output = root / "v40"
            _bundle(source)
            report = analyze_v40(
                v39_analysis_zip=source,
                output_dir=output,
                bootstrap_draws=1_000,
                bootstrap_seed=2908,
            )
            self.assertIn(
                report["status"],
                {"SHADOW_PAPER_RESEARCH_APPROVED", "RESEARCH_GATE_NOT_PASSED"},
            )
            self.assertTrue((output / SCORECARD_FILE).is_file())
            self.assertTrue((output / DECISION_FILE).is_file())
            self.assertTrue((output / PROTOCOL_FILE).is_file())
            self.assertTrue((output / MANIFEST_FILE).is_file())
            decision = json.loads((output / DECISION_FILE).read_text())
            protocol = json.loads((output / PROTOCOL_FILE).read_text())
            self.assertFalse(decision["live_capital_approved"])
            self.assertFalse(decision["automatic_live_orders_allowed"])
            self.assertFalse(decision["broker_order_submission_allowed"])
            self.assertFalse(protocol["live_promotion_automatic"])

    def test_rejects_manifest_hash_mismatch(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "v39.zip"
            _bundle(source, corrupt_manifest_hash=True)
            with self.assertRaisesRegex(ValueError, "MANIFEST_HASH_MISMATCH"):
                analyze_v40(
                    v39_analysis_zip=source,
                    output_dir=root / "v40",
                    bootstrap_draws=1_000,
                )


if __name__ == "__main__":
    unittest.main()
