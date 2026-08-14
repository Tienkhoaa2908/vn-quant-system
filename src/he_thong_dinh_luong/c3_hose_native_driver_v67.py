"""Boundary-safe entry point for V67 C3-native HOSE research.

The core intentionally receives only completed monthly C3 signal dates.  This
wrapper prevents a mid-month analysis end (for example 2026-08-13) from being
mistaken for a completed monthly canonical snapshot.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from . import c3_hose_native_v67 as core


def _monthly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    end_key = (end.year, end.month)
    for day in calendar:
        key = (day.year, day.month)
        if day <= end and key < end_key:
            by_month[key] = day
    return [by_month[key] for key in sorted(by_month)]


# Patch the internal helper before any study runs.  All other implementation is
# kept in the core module so the research contract has one source of truth.
core._monthly_days = _monthly_days

CHAMPION_MODEL = core.CHAMPION_MODEL
SCHEMA_VERSION = core.SCHEMA_VERSION
VenueSource = core.VenueSource
Market = core.Market
FeatureState = core.FeatureState
C3Snapshot = core.C3Snapshot
resolve_venue_source = core.resolve_venue_source
score_states = core.score_states
_canonical_snapshot = core._canonical_snapshot
_forward_outcome = core._forward_outcome
run_study = core.run_study


def main(argv=None) -> int:
    core._monthly_days = _monthly_days
    return core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
