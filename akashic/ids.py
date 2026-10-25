"""Time-ordered ids and UTC timestamps."""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone


def uuid7() -> str:
    """RFC 9562 UUIDv7: 48-bit unix ms timestamp, then random bits. Sorts by creation time."""
    ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76                          # version
    value |= ((rand >> 62) & 0xFFF) << 64       # rand_a (12 bits)
    value |= 0b10 << 62                         # variant
    value |= rand & ((1 << 62) - 1)             # rand_b (62 bits)
    return str(uuid.UUID(int=value))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
