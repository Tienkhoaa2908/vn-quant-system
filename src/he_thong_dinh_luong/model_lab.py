"""Stable entrypoint for the multi-model research lab."""
from .model_lab_runner import main, run_model_lab

__all__ = ["main", "run_model_lab"]

if __name__ == "__main__":
    raise SystemExit(main())
