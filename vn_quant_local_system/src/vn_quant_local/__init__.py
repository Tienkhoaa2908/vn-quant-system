"""VN Quant Local Workstation package."""

__version__ = "0.3.0"

from .model_safety import apply as _apply_model_safety
from .performance_safety import apply as _apply_performance_safety

_apply_model_safety()
_apply_performance_safety()
