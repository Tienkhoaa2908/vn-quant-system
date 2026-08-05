"""VN Quant Local Workstation package."""

__version__ = "0.6.0"

from .model_safety import apply as _apply_model_safety
from .performance_safety import apply as _apply_performance_safety
from .compat_v47 import apply as _apply_v47_compatibility
from .performance_corrections import apply as _apply_performance_corrections
from .source_integrity_v49 import apply as _apply_source_integrity
from .buying_power_v50 import apply as _apply_buying_power
from .buying_power_safety_v50 import apply as _apply_buying_power_safety
from .compat_v50 import apply as _apply_v50_compatibility

_apply_model_safety()
_apply_performance_safety()
_apply_v47_compatibility()
_apply_performance_corrections()
_apply_source_integrity()
_apply_buying_power()
_apply_buying_power_safety()
_apply_v50_compatibility()
