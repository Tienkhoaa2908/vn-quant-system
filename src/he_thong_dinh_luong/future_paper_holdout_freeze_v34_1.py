"""Path-independent compatibility layer for the V34 freeze policy.

V34 originally included the local absolute V33 artifact path in the policy core,
which made the policy ID depend on workstation placement. V34.1 removes local
path/name fields before hashing while retaining cryptographic source hashes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from . import future_paper_holdout_freeze_v34 as base

UPGRADE_SCHEMA_VERSION = "future_paper_holdout_freeze_v34_1"
_ORIGINAL_POLICY_CORE = base._policy_core
_ORIGINAL_FREEZE_POLICY = base.freeze_policy


def _stable_policy_core(
    *,
    source: Mapping[str, object],
    evidence: Mapping[str, object],
    report: Mapping[str, object],
    freeze_timestamp: object,
    exclude_signal_through: object,
) -> dict[str, object]:
    stable_source = {
        key: value
        for key, value in source.items()
        if key not in {"artifact_zip", "artifact_filename", "source_path"}
    }
    return _ORIGINAL_POLICY_CORE(
        source=stable_source,
        evidence=evidence,
        report=report,
        freeze_timestamp=freeze_timestamp,
        exclude_signal_through=exclude_signal_through,
    )


def freeze_policy(**kwargs: object) -> dict[str, object]:
    original = base._policy_core
    base._policy_core = _stable_policy_core
    try:
        result = _ORIGINAL_FREEZE_POLICY(**kwargs)
    finally:
        base._policy_core = original

    output_dir = Path(str(result["output_dir"])).resolve()
    report_path = output_dir / base.REPORT_FILE
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    report.update(
        {
            "base_schema_version": base.SCHEMA_VERSION,
            "upgrade_schema_version": UPGRADE_SCHEMA_VERSION,
            "policy_id_path_independent": True,
            "local_artifact_path_excluded_from_policy_hash": True,
        }
    )
    base._write_json(report_path, report)
    return {
        **result,
        "base_schema_version": base.SCHEMA_VERSION,
        "upgrade_schema_version": UPGRADE_SCHEMA_VERSION,
        "policy_id_path_independent": True,
    }


__all__ = [
    "UPGRADE_SCHEMA_VERSION",
    "_stable_policy_core",
    "freeze_policy",
]
