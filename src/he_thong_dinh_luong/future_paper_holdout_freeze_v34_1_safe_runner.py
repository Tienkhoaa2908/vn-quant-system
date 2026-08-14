"""ASCII-safe V34.1 wrapper with path-independent policy hashing."""
from __future__ import annotations

from typing import Sequence

from . import future_paper_holdout_freeze_v34 as base_core
from . import future_paper_holdout_freeze_v34_1 as compat
from . import future_paper_holdout_freeze_v34_safe_runner as base_runner


def main(argv: Sequence[str] | None = None) -> int:
    original = base_runner.core.freeze_policy
    base_runner.core.freeze_policy = compat.freeze_policy
    try:
        return base_runner.main(argv)
    finally:
        base_runner.core.freeze_policy = original
        base_core._policy_core = compat._ORIGINAL_POLICY_CORE


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
