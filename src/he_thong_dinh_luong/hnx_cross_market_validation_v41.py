"""Integrity-checked loader for V41 HNX cross-market validation."""
from __future__ import annotations
import base64 as _base64
import gzip as _gzip
import hashlib as _hashlib
from .hnx_cross_market_validation_v41_payload_1 import DATA as _P1
from .hnx_cross_market_validation_v41_payload_2 import DATA as _P2
from .hnx_cross_market_validation_v41_payload_3 import DATA as _P3
from .hnx_cross_market_validation_v41_payload_4 import DATA as _P4
from .hnx_cross_market_validation_v41_payload_5 import DATA as _P5
from .hnx_cross_market_validation_v41_payload_6 import DATA as _P6
_PAYLOAD = _P1 + _P2 + _P3 + _P4 + _P5 + _P6
_EXPECTED_SHA256 = "87707c495a7b3e508c66839515510d333f7a4d55a0c5a226538d6c56794bb862"
_SOURCE = _gzip.decompress(_base64.b64decode(_PAYLOAD))
if _hashlib.sha256(_SOURCE).hexdigest() != _EXPECTED_SHA256:
    raise RuntimeError("V41_EMBEDDED_SOURCE_SHA256_MISMATCH")
exec(compile(_SOURCE, __file__, "exec"), globals(), globals())
