"""Workstation entrypoint for V29 with strict frozen-V22 compatibility.

The frozen V22 research input serializes ``vnindex_tren_ma250`` as the text
values ``true`` and ``false``. The V27 core loader intentionally accepts only
finite numeric values, while the V27 workstation runner carries the historical
serialization adapter. V29 originally called the core loader directly, so all
real V22 rows were rejected and the run failed with ``V27_NO_USABLE_ROWS``.

V29 also writes heterogeneous hyperparameter metadata: Ridge rows have alpha
fields, Logistic rows have C/recall fields, and Hybrid rows have blend fields.
The core CSV helper derives its header from the first Ridge row, which silently
drops the Logistic and Hybrid audit columns. This runner uses a union-field CSV
writer during the run so every per-model field is retained.

Both compatibility patches are restored in ``finally``. They do not relax
chronology, predictive gates, data blockers, research eligibility, or
live-capital restrictions.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import io
import json
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

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


def _write_csv_with_union_fields(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        return
    if fields is None:
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    else:
        fieldnames = list(fields)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(
        buffer.getvalue(),
        encoding="utf-8-sig",
        newline="",
    )


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


@contextmanager
def _artifact_csv_compatibility() -> Iterator[None]:
    original = core._write_csv
    core._write_csv = _write_csv_with_union_fields  # type: ignore[assignment]
    try:
        yield
    finally:
        core._write_csv = original  # type: ignore[assignment]


def load_input_zip_v22_compatible(
    path: Path,
) -> tuple[list[v27.ResearchRow], dict[str, object]]:
    """Load the frozen V22 ZIP without changing the V27 core contract."""
    with _v22_boolean_compatibility():
        return v27._load_input_zip(path)


def run_predictive_target_lab_v22_compatible(
    **kwargs: object,
) -> dict[str, object]:
    """Run V29 with strict V22 parsing and complete audit CSV fields."""
    with _v22_boolean_compatibility(), _artifact_csv_compatibility():
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
        "complete_hyperparameter_audit_csv": True,
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
