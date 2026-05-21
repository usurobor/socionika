"""Executor protocol + StubExecutor (CadQuery-free) + CadQueryExecutor.

CadQuery may only be imported lazily inside CadQueryExecutor methods.
A module-level ``import cadquery`` is forbidden and verified by tests.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable

from socionics_medallion.ir import (
    ALL_OP_TYPES,
    ALL_OP_TYPES_ORDERED,
    CadOp,
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    op_to_dict,
)


class NotYetImplemented(Exception):
    """Raised by CadQueryExecutor for ops not in IMPLEMENTED_OPS."""

    def __init__(self, op: CadOp):
        self.op = op
        super().__init__(f"CadQueryExecutor has no implementation for {type(op).__name__}")


@runtime_checkable
class Executor(Protocol):
    """A consumer of compiled CadOp streams."""

    def execute(self, ops: Iterable[CadOp]) -> Any:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# StubExecutor — CadQuery-free; emits a JSON-friendly dump.
# ---------------------------------------------------------------------------
class StubExecutor:
    """Records a faithful dump of every CadOp it sees.

    The stub's output is the contract: counts + the full op stream as a list
    of dicts (sorted-key serializable). No translation, no rounding, no
    side effects.
    """

    def execute(self, ops: Iterable[CadOp]) -> dict:
        op_list = list(ops)
        counts: Counter = Counter(type(o).__name__ for o in op_list)
        # Guarantee a stable counts schema by initialising all op types.
        counts_dict = {
            t.__name__: counts.get(t.__name__, 0) for t in ALL_OP_TYPES_ORDERED
        }
        return {
            "counts": counts_dict,
            "ops": [op_to_dict(o) for o in op_list],
            "implemented_ops": sorted(
                t.__name__ for t in CadQueryExecutor.IMPLEMENTED_OPS
            ),
            "not_yet_implemented": sorted(
                t.__name__
                for t in ALL_OP_TYPES_ORDERED
                if t not in CadQueryExecutor.IMPLEMENTED_OPS
            ),
        }


# ---------------------------------------------------------------------------
# CadQueryExecutor — lazy cadquery import; Prism implemented end-to-end.
# ---------------------------------------------------------------------------
@dataclass
class CadQueryResult:
    """Wrapper around the CadQuery Workplane / solid we built."""

    solid: Any = None
    # Track how many ops of each type were processed (for inspection).
    processed: Counter = field(default_factory=Counter)


class CadQueryExecutor:
    """Translate a CadOp stream into CadQuery calls.

    Implements Prism end-to-end. Other ops raise NotYetImplemented(op) so
    callers know precisely which variant is missing rather than seeing
    silent geometric drift.
    """

    # Class-level — tests assert this set. Update as ops are added.
    IMPLEMENTED_OPS: frozenset = frozenset({Prism})

    def __init__(self) -> None:
        # Lazy import: cadquery is only loaded when an executor is actually
        # instantiated. This keeps module import side-effect-free.
        import cadquery  # noqa: F401  (verified import; assigned below)

        self._cq = cadquery

    def execute(self, ops: Iterable[CadOp]) -> CadQueryResult:
        result = CadQueryResult()
        solid = None
        for op in ops:
            handler = self._dispatch(op)
            solid = handler(op, solid)
            result.processed[type(op).__name__] += 1
        result.solid = solid
        return result

    # -- dispatch -----------------------------------------------------------
    def _dispatch(self, op: CadOp):
        if isinstance(op, Prism):
            return self._exec_prism
        raise NotYetImplemented(op)

    # -- op implementations -------------------------------------------------
    def _exec_prism(self, op: Prism, solid: Any) -> Any:
        cq = self._cq
        cx, cy = op.center
        height = op.z1 - op.z0
        start = op.angle_start_deg
        end = op.angle_end_deg
        # Resolve the midpoint from the IR field — never via (start + end)/2,
        # which is fragile across wrap-arounds (AC2).
        mid = op.center_angle_deg
        # If end <= start in the unwrapped representation, unwrap end and the
        # mid so the arc remains a proper CCW sweep.
        if end <= start:
            end += 360.0
            if mid < start:
                mid += 360.0

        def pt(r: float, theta_deg: float) -> tuple[float, float]:
            t = math.radians(theta_deg)
            return (cx + r * math.cos(t), cy + r * math.sin(t))

        p_inner_start = pt(op.inner_radius, start)
        p_outer_start = pt(op.outer_radius, start)
        p_outer_mid = pt(op.outer_radius, mid)
        p_outer_end = pt(op.outer_radius, end)
        p_inner_end = pt(op.inner_radius, end)
        p_inner_mid = pt(op.inner_radius, mid)

        wp = cq.Workplane("XY").workplane(offset=op.z0)
        if op.inner_radius > 0.0:
            sketch = (
                wp.moveTo(*p_inner_start)
                .lineTo(*p_outer_start)
                .threePointArc(p_outer_mid, p_outer_end)
                .lineTo(*p_inner_end)
                .threePointArc(p_inner_mid, p_inner_start)
                .close()
            )
        else:
            sketch = (
                wp.moveTo(cx, cy)
                .lineTo(*p_outer_start)
                .threePointArc(p_outer_mid, p_outer_end)
                .close()
            )
        new_piece = sketch.extrude(height)
        if solid is None:
            return new_piece
        return solid.union(new_piece)


# ---------------------------------------------------------------------------
# Module-level alias so AC9's CLI smoke check works without instantiating
# the executor (which would require cadquery).
# ---------------------------------------------------------------------------
IMPLEMENTED_OPS: frozenset = CadQueryExecutor.IMPLEMENTED_OPS
