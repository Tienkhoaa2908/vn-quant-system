"""VN Quant Local Workstation."""

__version__ = "0.2.0"

# V45 chốt snapshot mở đầu bằng transaction riêng. Giữ alias tại package load
# để mọi entrypoint cũ import ``performance.start_observatory`` đều nhận bản đã
# kiểm tra placeholder/schema thay vì implementation ban đầu.
from . import performance as _performance
from .performance_start import start_observatory as _validated_start_observatory

_performance.start_observatory = _validated_start_observatory
