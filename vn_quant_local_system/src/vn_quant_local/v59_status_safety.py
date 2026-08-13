"""Preserve established workstation-status safety while retaining V59 fast coverage.

V51 deliberately makes every new-capital cycle default to zero. V59 must not
replace that public status function. The V51 wrapper resolves core.market_coverage
at runtime, so V59 still gets the no-SHA fast market coverage by restoring the
wrapper after V59 fast-path installation.
"""
from __future__ import annotations

from . import core, v51_safety, v59_fast_realtime

V59_STATUS_SAFETY_VERSION = "V59_PRESERVE_V51_ZERO_NEW_CAPITAL"


def apply() -> None:
    if getattr(v59_fast_realtime, "_v59_status_safety_applied", False):
        return
    core.workstation_status = v51_safety.workstation_status_zero_new_capital
    v59_fast_realtime.V59_STATUS_SAFETY_VERSION = V59_STATUS_SAFETY_VERSION
    v59_fast_realtime._v59_status_safety_applied = True
