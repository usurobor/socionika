"""Executor protocol + StubExecutor (CadQuery-free) + CadQueryExecutor.

CadQuery may only be imported lazily inside :class:`CadQueryExecutor`
methods. A module-level ``import cadquery`` is forbidden and verified by
tests.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable

from socionics_medallion.geometry import (
    Profile,
    circle_profile,
    ethics_profile,
    place_profile_in_world,
    square_profile,
    triangle_profile,
)
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
    SymbolKind,
    op_to_dict,
)


class NotYetImplemented(Exception):
    """Raised by :class:`CadQueryExecutor` for ops not in IMPLEMENTED_OPS."""

    def __init__(self, op: CadOp):
        self.op = op
        super().__init__(
            f"CadQueryExecutor has no implementation for {type(op).__name__}"
        )


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

    The stub's output is the contract: counts + the full op stream as a
    list of dicts (sorted-key serializable). No translation, no rounding,
    no side effects.
    """

    def execute(self, ops: Iterable[CadOp]) -> dict:
        op_list = list(ops)
        counts: Counter = Counter(type(o).__name__ for o in op_list)
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
# CadQueryExecutor.
# ---------------------------------------------------------------------------
@dataclass
class CadQueryResult:
    """Wrapper around the CadQuery ``Workplane`` / solid we built."""

    solid: Any = None
    processed: Counter = field(default_factory=Counter)


_PROFILE_FOR_KIND = {
    SymbolKind.SQUARE: square_profile,
    SymbolKind.CIRCLE: circle_profile,
    SymbolKind.TRIANGLE: triangle_profile,
    SymbolKind.ETHICS: ethics_profile,
}


def _profile_for(kind: SymbolKind, S: float) -> Profile:
    """Return the local-frame profile for a given symbol kind.

    Circle is approximated with a fixed segment count; the segment count is
    high enough that the executor's downstream test (which checks
    ``bb.zmax``) is unaffected.
    """
    if kind is SymbolKind.CIRCLE:
        return circle_profile(S, segments=96)
    return _PROFILE_FOR_KIND[kind](S)


class CadQueryExecutor:
    """Translate a CadOp stream into CadQuery calls.

    Implements every variant in :data:`ALL_OP_TYPES`. Lazy CadQuery import
    inside :meth:`__init__` so module-level imports stay side-effect-free.
    """

    # Class-level — tests assert this set against ALL_OP_TYPES (AC9).
    IMPLEMENTED_OPS: frozenset = frozenset(
        {Prism, LowerField, RaisedSymbol, CutSymbol, RaisedDivider, EngravedDivider}
    )

    def __init__(self) -> None:
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
        if isinstance(op, LowerField):
            return self._exec_lower_field
        if isinstance(op, RaisedSymbol):
            return self._exec_raised_symbol
        if isinstance(op, CutSymbol):
            return self._exec_cut_symbol
        if isinstance(op, RaisedDivider):
            return self._exec_raised_divider
        if isinstance(op, EngravedDivider):
            return self._exec_engraved_divider
        raise NotYetImplemented(op)

    # -- helpers ------------------------------------------------------------
    def _sector_solid(
        self,
        center: tuple[float, float],
        inner_radius: float,
        outer_radius: float,
        angle_start_deg: float,
        angle_end_deg: float,
        center_angle_deg: float,
        z0: float,
        height: float,
    ) -> Any:
        """Build a sector prism volume.

        Resolves ``mid`` from the explicit ``center_angle_deg`` field (AC2)
        rather than recomputing the raw midpoint, which is wrap-fragile.
        """
        cq = self._cq
        cx, cy = center
        a_start = angle_start_deg
        a_end = angle_end_deg
        mid = center_angle_deg
        # Unwrap for CCW arc when the IR carries a (-180, 180] range that
        # straddles ±180°.
        if a_end <= a_start:
            a_end += 360.0
            if mid < a_start:
                mid += 360.0

        def pt(r: float, theta_deg: float) -> tuple[float, float]:
            t = math.radians(theta_deg)
            return (cx + r * math.cos(t), cy + r * math.sin(t))

        p_inner_start = pt(inner_radius, a_start)
        p_outer_start = pt(outer_radius, a_start)
        p_outer_mid = pt(outer_radius, mid)
        p_outer_end = pt(outer_radius, a_end)
        p_inner_end = pt(inner_radius, a_end)
        p_inner_mid = pt(inner_radius, mid)

        wp = cq.Workplane("XY").workplane(offset=z0)
        if inner_radius > 0.0:
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
        return sketch.extrude(height)

    def _symbol_solid(
        self,
        kind: SymbolKind,
        size_S: float,
        center_angle_deg: float,
        center_radius: float,
        z0: float,
        height: float,
    ) -> Any:
        """Build a symbol prism positioned and oriented per AC5."""
        cq = self._cq
        profile = _profile_for(kind, size_S)
        ax = center_radius * math.cos(math.radians(center_angle_deg))
        ay = center_radius * math.sin(math.radians(center_angle_deg))
        world_verts = place_profile_in_world(profile, (ax, ay), center_angle_deg)
        wp = cq.Workplane("XY").workplane(offset=z0)
        first = world_verts[0]
        sketch = wp.moveTo(*first)
        for v in world_verts[1:]:
            sketch = sketch.lineTo(*v)
        sketch = sketch.close()
        return sketch.extrude(height)

    # -- op implementations -------------------------------------------------
    def _exec_prism(self, op: Prism, solid: Any) -> Any:
        new_piece = self._sector_solid(
            center=op.center,
            inner_radius=op.inner_radius,
            outer_radius=op.outer_radius,
            angle_start_deg=op.angle_start_deg,
            angle_end_deg=op.angle_end_deg,
            center_angle_deg=op.center_angle_deg,
            z0=op.z0,
            height=op.z1 - op.z0,
        )
        if solid is None:
            return new_piece
        return solid.union(new_piece)

    def _exec_lower_field(self, op: LowerField, solid: Any) -> Any:
        # Cut a thin sector slab off the top of the existing solid.
        cutter = self._sector_solid(
            center=op.center,
            inner_radius=op.inner_radius,
            outer_radius=op.outer_radius,
            angle_start_deg=op.angle_start_deg,
            angle_end_deg=op.angle_end_deg,
            center_angle_deg=op.center_angle_deg,
            z0=op.surface_z - op.depth,
            height=op.depth,
        )
        if solid is None:
            # Without a base, cut from an empty solid is a no-op.
            return None
        return solid.cut(cutter)

    def _exec_raised_divider(self, op: RaisedDivider, solid: Any) -> Any:
        rib = self._sector_solid(
            center=(0.0, 0.0),
            inner_radius=op.inner_radius,
            outer_radius=op.outer_radius,
            angle_start_deg=op.angle_start_deg,
            angle_end_deg=op.angle_end_deg,
            center_angle_deg=op.center_angle_deg,
            z0=op.base_z,
            height=op.height,
        )
        if solid is None:
            return rib
        return solid.union(rib)

    def _exec_engraved_divider(self, op: EngravedDivider, solid: Any) -> Any:
        cutter = self._sector_solid(
            center=(0.0, 0.0),
            inner_radius=op.inner_radius,
            outer_radius=op.outer_radius,
            angle_start_deg=op.angle_start_deg,
            angle_end_deg=op.angle_end_deg,
            center_angle_deg=op.center_angle_deg,
            z0=op.surface_z - op.depth,
            height=op.depth,
        )
        if solid is None:
            return None
        return solid.cut(cutter)

    def _exec_raised_symbol(self, op: RaisedSymbol, solid: Any) -> Any:
        bump = self._symbol_solid(
            kind=op.symbol_kind,
            size_S=op.size_S,
            center_angle_deg=op.center_angle_deg,
            center_radius=op.center_radius,
            z0=op.base_z,
            height=op.height,
        )
        if solid is None:
            return bump
        return solid.union(bump)

    def _exec_cut_symbol(self, op: CutSymbol, solid: Any) -> Any:
        cutter = self._symbol_solid(
            kind=op.symbol_kind,
            size_S=op.size_S,
            center_angle_deg=op.center_angle_deg,
            center_radius=op.center_radius,
            z0=op.surface_z - op.depth,
            height=op.depth,
        )
        if solid is None:
            return None
        return solid.cut(cutter)


# ---------------------------------------------------------------------------
# Module-level alias + runtime invariant assertion (AC9).
# ---------------------------------------------------------------------------
IMPLEMENTED_OPS: frozenset = CadQueryExecutor.IMPLEMENTED_OPS

if IMPLEMENTED_OPS != ALL_OP_TYPES:  # pragma: no cover - structural invariant
    missing = ", ".join(sorted(t.__name__ for t in ALL_OP_TYPES - IMPLEMENTED_OPS))
    extra = ", ".join(sorted(t.__name__ for t in IMPLEMENTED_OPS - ALL_OP_TYPES))
    raise AssertionError(
        "CadQueryExecutor.IMPLEMENTED_OPS does not match ALL_OP_TYPES "
        f"(missing: {missing or '∅'}; extra: {extra or '∅'})"
    )
