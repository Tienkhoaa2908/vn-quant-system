"""Resolve an anytime web request to a provisional snapshot or canonical final EOD.

AUTO mode runs a DNSE snapshot before 18:00 Vietnam time and the existing final EOD +
paper workflow at/after 18:00. Explicit SNAPSHOT is always allowed. Explicit FINAL keeps
the original finality gate.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

VN_TZ = timezone(timedelta(hours=7))
MODES = ("auto", "snapshot", "final")


def resolve_mode(mode: str, *, now: datetime | None = None, target_date: date | None = None) -> str:
    normalized = mode.strip().lower()
    if normalized not in MODES:
        raise ValueError(f"ANYTIME_MODE_INVALID:{mode}")
    if normalized != "auto":
        return normalized
    current = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    if target_date is not None and target_date < current.date():
        return "final"
    return "final" if current.hour >= 18 else "snapshot"


def _run(command: Sequence[str], *, cwd: Path) -> int:
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(cwd / "src"),
    })
    process = subprocess.Popen(
        tuple(command),
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
    return process.wait()


def run(
    *,
    repo_root: Path,
    data_root: Path,
    output_dir: Path,
    mode: str = "auto",
    target_date: date | None = None,
    secondary_source: str = "vci",
    crosscheck_sample_size: int = 20,
    min_coverage: float = 0.95,
    initial_capital_vnd: int = 1_000_000_000,
    buy_fee_bps: float = 15.0,
    sell_fee_bps: float = 15.0,
    sell_tax_bps: float = 100.0,
    slippage_bps: float = 10.0,
    lot_size: int = 100,
    now: datetime | None = None,
) -> dict[str, object]:
    root = Path(repo_root).resolve()
    data = Path(data_root).resolve()
    output = Path(output_dir).resolve()
    resolved = resolve_mode(mode, now=now, target_date=target_date)
    if output.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    if resolved == "snapshot":
        command = [
            sys.executable, "-m", "he_thong_dinh_luong.anytime_snapshot_cli",
            "--data-root", str(data),
            "--output-dir", str(output),
            "--min-coverage", str(min(0.80, min_coverage)),
        ]
        code = _run(command, cwd=root)
        if code != 0:
            raise RuntimeError(f"SNAPSHOT_STEP_FAILED:{code}")
        return {
            "status": "SUCCESS",
            "resolved_mode": "snapshot",
            "output_dir": str(output),
            "paper_updated": False,
        }

    eod_command = [
        sys.executable, "-m", "he_thong_dinh_luong.eod_hang_ngay_cli",
        "--data-root", str(data),
        "--output-dir", str(output),
        "--primary-source", "dnse",
        "--secondary-source", secondary_source,
        "--crosscheck-policy", "advisory",
        "--crosscheck-sample-size", str(crosscheck_sample_size),
        "--min-coverage", str(min_coverage),
        "--price-tolerance-bps", "10",
        "--volume-tolerance-ratio", "0.05",
    ]
    if target_date is not None:
        eod_command.extend(("--target-date", target_date.isoformat()))
    code = _run(eod_command, cwd=root)
    if code != 0:
        raise RuntimeError(f"FINAL_EOD_STEP_FAILED:{code}")
    paper_command = [
        sys.executable, "-m", "he_thong_dinh_luong.paper_trading_daily",
        "--daily-output", str(output / "daily_quant_output.zip"),
        "--publication-dir", str(output / "updated_publication"),
        "--state-dir", str(data / "paper-trading-live"),
        "--initial-capital-vnd", str(initial_capital_vnd),
        "--buy-fee-bps", str(buy_fee_bps),
        "--sell-fee-bps", str(sell_fee_bps),
        "--sell-tax-bps", str(sell_tax_bps),
        "--slippage-bps", str(slippage_bps),
        "--lot-size", str(lot_size),
    ]
    code = _run(paper_command, cwd=root)
    if code != 0:
        raise RuntimeError(f"PAPER_STEP_FAILED:{code}")
    return {
        "status": "SUCCESS",
        "resolved_mode": "final",
        "output_dir": str(output),
        "paper_updated": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.anytime_pipeline")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, default="auto")
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument("--secondary-source", choices=("kbs", "vci"), default="vci")
    parser.add_argument("--crosscheck-sample-size", type=int, default=20)
    parser.add_argument("--min-coverage", type=float, default=0.95)
    parser.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    parser.add_argument("--buy-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-tax-bps", type=float, default=100.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            repo_root=args.repo_root,
            data_root=args.data_root,
            output_dir=args.output_dir,
            mode=args.mode,
            target_date=args.target_date,
            secondary_source=args.secondary_source,
            crosscheck_sample_size=args.crosscheck_sample_size,
            min_coverage=args.min_coverage,
            initial_capital_vnd=args.initial_capital_vnd,
            buy_fee_bps=args.buy_fee_bps,
            sell_fee_bps=args.sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
