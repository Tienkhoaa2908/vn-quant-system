"""ASCII-safe V32.1 runner preserving the full eligible OOS horizon."""
from __future__ import annotations

from typing import Sequence

from . import portfolio_ablation_v32 as core
from . import portfolio_ablation_v32_1 as upgrade
from . import portfolio_ablation_v32_safe_runner as safe


def main(argv: Sequence[str] | None = None) -> int:
    core.run_v32 = upgrade.run_v32_1
    return safe.main(argv)


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
