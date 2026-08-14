"""Compatibility entrypoint for Vnstock 4 reference APIs."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        import vnstock  # type: ignore
        if not hasattr(vnstock, "Reference"):
            from vnstock_data import Reference  # type: ignore
            setattr(vnstock, "Reference", Reference)
    except Exception:
        # The core resolver records an import failure and still produces a
        # strict-blocked handoff rather than crashing the one-shot workflow.
        pass

    from .v39_one_shot_external_resolution import main as core_main
    return core_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
