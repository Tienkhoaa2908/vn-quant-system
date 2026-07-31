"""Stable entrypoint for the predictive-value multi-model research lab."""
from .model_lab_upgrade_v3 import main, run_model_lab

__all__ = ["main", "run_model_lab"]

if __name__ == "__main__":
    raise SystemExit(main())
