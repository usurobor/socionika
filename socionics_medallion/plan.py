"""Pure-Python plan/spec for the socionics medallion.

This module MUST NOT import cadquery (or any CAD toolchain). It is consumed
read-only by the compiler.
"""

from __future__ import annotations

from typing import Iterable

# Stubs for Phase 1; Phase 2 fills these in.

INNER_SECTORS: int = 8
OUTER_SECTORS: int = 16

INNER_SECTOR_DEG: float = 45.0
OUTER_SECTOR_DEG: float = 22.5


def build_plan():  # pragma: no cover - stubbed for Phase 1
    raise NotImplementedError("build_plan() not yet implemented")
