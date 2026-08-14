"""Model Lab v7: preserve deployment-status compatibility around v6.

V6 correctly blocks post-hoc predictive policies, but the inherited summary
stores ``deployment_status`` as a string. This wrapper adapts that field only
while v6 publishes its safety metadata, then restores the stable string contract
and moves structured safety detail to ``deployment_safety_v6``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v6 as v6

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v7"


def normalize_deployment_status(raw: object) -> tuple[str, dict[str, object]]:
    """Return the stable status string and a mutable structured representation."""
    if isinstance(raw, Mapping):
        structured = dict(raw)
        status = str(structured.get("status") or "NO_MODEL_APPROVED")
        structured["status"] = status
        return status, structured
    status = str(raw or "NO_MODEL_APPROVED")
    return status, {"status": status}


def _write_summary(path: Path, summary: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(dict(summary), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _compatible_v6_publish(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    stable_status, structured = normalize_deployment_status(
        summary.get("deployment_status")
    )
    summary["deployment_status"] = structured
    _write_summary(summary_path, summary)

    result = _ORIGINAL_V6_PUBLISH(output)

    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    _, published_structured = normalize_deployment_status(
        summary.get("deployment_status")
    )
    summary["base_upgrade_schema_version"] = v6.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["deployment_status"] = stable_status
    summary["deployment_safety_v6"] = {
        **published_structured,
        "stable_string_contract_preserved": True,
        "actionable": False,
    }
    _write_summary(summary_path, summary)
    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {**result, "upgrade_schema_version": SCHEMA_VERSION}


_ORIGINAL_V6_PUBLISH = v6.publish_v6_predictive_diagnostics


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original = v6.publish_v6_predictive_diagnostics
    v6.publish_v6_predictive_diagnostics = _compatible_v6_publish
    try:
        result = v6.run_model_lab(**kwargs)
        return {**result, "upgrade_schema_version": SCHEMA_VERSION}
    finally:
        v6.publish_v6_predictive_diagnostics = original


def _parser():
    return v6._parser()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(
            item.strip()
            for item in args.models.split(",")
            if item.strip()
        ),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
        turnover_buffer=args.turnover_buffer,
        seed=args.seed,
        strict_dependencies=args.strict_dependencies,
        buy_fee_bps=args.buy_fee_bps,
        sell_fee_bps=args.sell_fee_bps,
        sell_tax_bps=args.sell_tax_bps,
        slippage_bps=args.slippage_bps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "normalize_deployment_status",
    "run_model_lab",
    "main",
]
