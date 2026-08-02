"""Workstation entrypoint for V29 with strict frozen-V22 compatibility.

The frozen V22 research input serializes ``vnindex_tren_ma250`` as the text
values ``true`` and ``false``.  The V27 core loader intentionally accepts only
finite numeric values, while the V27 workstation runner carries the historical
serialization adapter.  V29 originally called the core loader directly, so
all real V22 rows were rejected and the run failed with
``V27_NO_USABLE_ROWS``.

This adapter changes only the parsing of that one regime field while V29 is
loading/running.  It restores the original parser in ``finally`` and does not
relax chronology, predictive gates, data blockers, research eligibility, or
live-capital restrictions.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from typing import Callable, Iterator, Sequence

from . import component_breadth_ablation_v27 as v27
from . import predictive_target_lab_v29 as core


FiniteParser = Callable[..., float]


def _finite_with_v22_boolean(
    original: FiniteParser,
    value: object,
    *,
    name: str,
) -> float:
    if name != "vnindex_tren_ma250":
        return original(value, name=name)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1.0
    if text in {"0", "false", "no", "n"}:
        return 0.0
    raise ValueError(f"V29_INVALID_V22_BOOLEAN:{name}:{text}")


@contextmanager
def _v22_boolean_compatibility() -> Iterator[None]:
    original = v27._finite

    def compatible(value: object, *, name: str) -> float:
        return _finite_with_v22_boolean(
            original,
            value,
            name=name,
        )

    v27._finite = compatible  # type: ignore[assignment]
    try:
        yield
    finally:
        v27._finite = original  # type: ignore[assignment]


def load_input_zip_v22_compatible(
    path: Path,
) -> tuple[list[v27.ResearchRow], dict[str, object]]:
    """Load the frozen V22 ZIP without changing the V27 core contract."""
    with _v22_boolean_compatibility():
        return v27._load_input_zip(path)


def run_predictive_target_lab_v22_compatible(
    **kwargs: object,
) -> dict[str, object]:
    """Run V29 while adapting only the historical V22 regime serialization."""
    with _v22_boolean_compatibility():
        return core.run_predictive_target_lab(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    try:
        report = run_predictive_target_lab_v22_compatible(
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            effective_trials=args.effective_trials,
            seed=args.seed,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "output_dir": report["output_dir"],
        "walk_forward_fold_count": report["walk_forward_fold_count"],
        "recommendation": report["recommendation"],
        "passing_models": report["passing_models"],
        "v22_boolean_compatibility_applied": True,
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "load_input_zip_v22_compatible",
    "run_predictive_target_lab_v22_compatible",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
