"""Final safety corrections for V51.

DNSE documents account-balance fields at the response top level.  Prefer those
exact fields and use recursive discovery only as an explicit fallback.  Also
preserve the V49 broker payload version so the established V49 portfolio UI keeps
rendering; V51 is exposed through a separate ``v51_version`` field.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from . import source_integrity_v49
from . import v51_integrity as v51

_ORIGINAL_ANNOTATE = None


def _top_level_number(payload: object, names: Sequence[str]) -> float | None:
    if not isinstance(payload, Mapping):
        return None
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        key = name.lower()
        if key not in lowered or lowered[key] is None:
            continue
        value = v51._optional_nonnegative(lowered[key])
        if value is not None:
            return value
    return None


def extract_cash_fields(payload: object) -> dict[str, object]:
    total = _top_level_number(payload, ("totalCash", "total_cash"))
    available = _top_level_number(payload, ("availableCash", "available_cash"))
    withdrawable = _top_level_number(
        payload,
        ("withdrawableCash", "withdrawable_cash"),
    )
    source = "TOP_LEVEL_DNSE_BALANCE_FIELDS"
    if total is None and available is None and withdrawable is None:
        total = source_integrity_v49._find_number(
            payload, ("totalCash", "total_cash")
        )
        available = source_integrity_v49._find_number(
            payload, ("availableCash", "available_cash")
        )
        withdrawable = source_integrity_v49._find_number(
            payload, ("withdrawableCash", "withdrawable_cash")
        )
        source = "RECURSIVE_FALLBACK_NO_TOP_LEVEL_FIELDS"
    return {
        "total_cash_vnd": total,
        "available_cash_vnd": available,
        "withdrawable_cash_vnd": withdrawable,
        "field_source": source,
    }


def probe_accounts_safe(reader) -> list[dict[str, object]]:
    assert v51._ORIGINAL_PROBE is not None
    rows = [dict(row) for row in v51._ORIGINAL_PROBE(reader)]
    for row in rows:
        fields = extract_cash_fields(row.get("balance"))
        diagnostic = v51.validate_cash_contract(
            total_cash_vnd=fields["total_cash_vnd"],
            available_cash_vnd=fields["available_cash_vnd"],
            withdrawable_cash_vnd=fields["withdrawable_cash_vnd"],
        )
        diagnostic["field_source"] = fields["field_source"]
        row["reported_available_cash_vnd"] = fields["available_cash_vnd"]
        row["reported_withdrawable_cash_vnd"] = fields[
            "withdrawable_cash_vnd"
        ]
        row["reported_total_cash_vnd"] = fields["total_cash_vnd"]
        row["available_cash_vnd"] = diagnostic[
            "validated_available_cash_vnd"
        ]
        row["withdrawable_cash_vnd"] = diagnostic[
            "validated_withdrawable_cash_vnd"
        ]
        row["total_cash_vnd"] = max(
            float(fields["total_cash_vnd"] or 0.0), 0.0
        )
        row["planner_cash_vnd"] = diagnostic["planner_cash_vnd"]
        row["cash_integrity"] = diagnostic
        token = str(row.get("selection_token") or "")
        if token:
            v51._CASH_DIAGNOSTICS[token] = diagnostic
    return rows


def annotate_preserve_v49_version(
    result: Mapping[str, object] | None,
) -> dict[str, object] | None:
    assert _ORIGINAL_ANNOTATE is not None
    if result is None:
        return None
    original_version = result.get("version")
    value = _ORIGINAL_ANNOTATE(result)
    if value is None:
        return None
    if original_version:
        value["version"] = original_version
    else:
        details = value.get("details")
        if isinstance(details, Mapping) and details.get("version"):
            value["version"] = details["version"]
    value["v51_version"] = v51.V51_VERSION
    return value


def apply() -> None:
    if getattr(v51, "_v51_final_safety_applied", False):
        return
    global _ORIGINAL_ANNOTATE
    _ORIGINAL_ANNOTATE = v51._annotate_latest_cash
    source_integrity_v49._probe_accounts = probe_accounts_safe
    v51._annotate_latest_cash = annotate_preserve_v49_version
    v51._v51_final_safety_applied = True
