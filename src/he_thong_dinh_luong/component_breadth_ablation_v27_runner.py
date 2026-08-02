"""Workstation entrypoint for V27 with strict boolean feature compatibility.

The V22 historical ZIP serializes ``vnindex_tren_ma250`` as ``true``/``false``.
The initial V27 parser treated all feature columns as floating-point strings.
This entrypoint adapts that one field without changing V27 scoring, folds,
portfolio evaluation, gates or output schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from . import component_breadth_ablation_v27 as base


def _finite_with_v22_boolean(value: object, *, name: str) -> float:
    if name != "vnindex_tren_ma250":
        return base._ORIGINAL_V27_FINITE(value, name=name)  # type: ignore[attr-defined]
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1.0
    if text in {"0", "false", "no", "n"}:
        return 0.0
    raise ValueError(f"V27_INVALID_BOOLEAN:{name}:{text}")


def run_v27_compatible(*args, **kwargs):
    original = base._finite
    base._ORIGINAL_V27_FINITE = original  # type: ignore[attr-defined]
    base._finite = _finite_with_v22_boolean
    try:
        return base.run_v27(*args, **kwargs)
    finally:
        base._finite = original
        try:
            delattr(base, "_ORIGINAL_V27_FINITE")
        except AttributeError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    args = base._parser().parse_args(argv)
    try:
        result = run_v27_compatible(
            args.input_zip,
            args.model_output,
            args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            nested_validation_months=args.nested_validation_months,
            nested_test_months=args.nested_test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            breadths=args.breadths,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result["status"],
        "output_dir": result["output_dir"],
        "report": str(Path(result["output_dir"]) / base.REPORT_FILE),
        "walk_forward_fold_count": result["walk_forward_fold_count"],
        "recommendation": result["recommendation"],
        "v22_boolean_compatibility_applied": True,
        "requires_confirmation_before_v28": True,
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["run_v27_compatible", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
