"""VN Quant Local Workstation package."""

__version__ = "0.5.3"

from .model_safety import apply as _apply_model_safety
from .performance_safety import apply as _apply_performance_safety
from .compat_v47 import apply as _apply_v47_compatibility
from .performance_corrections import apply as _apply_performance_corrections
from .source_integrity_v49 import apply as _apply_source_integrity
from .v51_integrity import apply as _apply_v51_integrity
from .v51_safety import apply as _apply_v51_safety
from .v52_cycle_management import apply as _apply_v52_cycle_management
from .v52_discard_safety import apply as _apply_v52_discard_safety
from .v52_status_safety import apply as _apply_v52_status_safety
from .v52_commands import apply as _apply_v52_commands
from .v53_cycle_cleanup import apply as _apply_v53_cycle_cleanup
from .v53_safety import apply as _apply_v53_safety

_apply_model_safety()
_apply_performance_safety()
_apply_v47_compatibility()
_apply_performance_corrections()
_apply_source_integrity()
_apply_v51_integrity()
_apply_v51_safety()
_apply_v52_cycle_management()
_apply_v52_discard_safety()
_apply_v52_status_safety()
_apply_v52_commands()
_apply_v53_cycle_cleanup()
_apply_v53_safety()
