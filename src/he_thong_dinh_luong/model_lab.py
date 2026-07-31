"""Stable entrypoint for the quality-gated multi-model research lab."""
from .model_lab_runner_v2 import main, run_model_lab

__all__ = ["main", "run_model_lab"]

if __name__ == "__main__":
    raise SystemExit(main())
