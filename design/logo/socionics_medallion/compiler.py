"""Pure compiler: plan -> list[CadOp].

This module MUST NOT import cadquery (or any CAD toolchain). It is also
forbidden from importing the executor module.

Output order is fixed (deterministic):
    1. All inner-cell prisms (in clockwise order)
    2. All outer-cell prisms (sorted by cell_id, i.e. CCW by start_angle_deg)
    3. All lowered fields for black inner cells (clockwise order)
    4. All lowered fields for black outer cells (sorted by cell_id)
    5. All inner symbols (clockwise order); each symbol is raised or cut
       based on its cell's polarity.
    6. All outer symbols (sorted by cell_id)
    7. All inner-ring divider ops (sorted by boundary_id)
    8. All outer-ring divider ops (sorted by boundary_id)

Divider treatment rule for mixed-polarity boundaries (issue #3 §AC3 /
operator's 2026-05-21 AC6 supersession)
-------------------------------------------------------------------------
When two adjacent cells share a boundary:

* BLACK | BLACK → one :class:`RaisedDivider` (owner = either black cell)
* WHITE | WHITE → one :class:`EngravedDivider` (owner = either white cell)
* BLACK | WHITE → TWO owner-scoped ops:
    1. :class:`RaisedDivider` owned by the **black** cell, placed over the
       black cell's lowered field, with its angular footprint restricted to
       the black cell's half of the boundary strip.
    2. :class:`EngravedDivider` owned by the **white** cell, cut into the
       white cell's surface, with its angular footprint restricted to the
       white cell's half of the boundary strip.

This guarantees the two geometries are spatially disjoint across the
boundary line (AC7 — verified by a CadQuery-installed test).

Symbol orientation (issue #3 §AC5)
----------------------------------
Each symbol's ``local_top_angle_deg`` is the world-frame angle (degrees) of
the symbol's local +Y axis. For a medallion symbol it points radially inward
toward the medallion center, i.e.::

    local_top_angle_deg = (center_angle_deg + 180.0) wrapped into (-180, 180]
"""

from __future__ import annotations

from typing import List

from socionics_medallion.ir import (
    CadOp,
    CutSymbol,
    DividerTreatment,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
    normalized_angle_delta_deg,
)
from socionics_medallion.plan import (
    BASE_Z,
    BLACK_FIELD_Z,
    BoundarySpec,
    CellSpec,
    DIVIDER_DEPTH,
    DIVIDER_HEIGHT,
    FIELD_LOWER_DEPTH,
    Plan,
    Polarity,
    SURFACE_Z,
    SYMBOL_CUT_DEPTH,
    SYMBOL_HEIGHT,
    SymbolKind as PlanSymbolKind,
    SymbolSpec,
)

# Origin of the medallion's polar coordinates.
_CENTER: tuple[float, float] = (0.0, 0.0)


def _to_ir_symbol_kind(k: PlanSymbolKind) -> SymbolKind:
    return SymbolKind[k.name]


def _wrap_signed_deg(angle_deg: float) -> float:
    """Wrap ``angle_deg`` into ``(-180, 180]``."""
    a = angle_deg
    while a <= -180.0:
        a += 360.0
    while a > 180.0:
        a -= 360.0
    return a


def _inward_top_angle(center_angle_deg: float) -> float:
    """World-frame angle of a symbol's local +Y axis (pointing to medallion center)."""
    return _wrap_signed_deg(center_angle_deg + 180.0)


# ---------------------------------------------------------------------------
# Per-element sub-compilers.
# ---------------------------------------------------------------------------
def compile_cell_prism(cell: CellSpec) -> Prism:
    return Prism(
        center=_CENTER,
        inner_radius=cell.inner_radius,
        outer_radius=cell.outer_radius,
        angle_start_deg=cell.start_angle_deg,
        angle_end_deg=cell.end_angle_deg,
        center_angle_deg=cell.center_angle_deg,
        span_deg=cell.span_deg,
        z0=BASE_Z,
        z1=SURFACE_Z,
    )


def compile_cell_lower_field(cell: CellSpec) -> LowerField:
    return LowerField(
        owner_cell_id=cell.cell_id,
        center=_CENTER,
        inner_radius=cell.inner_radius,
        outer_radius=cell.outer_radius,
        angle_start_deg=cell.start_angle_deg,
        angle_end_deg=cell.end_angle_deg,
        center_angle_deg=cell.center_angle_deg,
        span_deg=cell.span_deg,
        surface_z=SURFACE_Z,
        depth=FIELD_LOWER_DEPTH,
    )


def compile_symbol(symbol: SymbolSpec) -> CadOp:
    """A black symbol becomes :class:`RaisedSymbol`; a white symbol becomes
    :class:`CutSymbol`.

    Orientation (AC5): ``local_top_angle_deg`` points radially inward, toward
    the medallion center.
    """
    kind = _to_ir_symbol_kind(symbol.kind)
    local_top = _inward_top_angle(symbol.center_angle_deg)
    if symbol.polarity is Polarity.BLACK:
        return RaisedSymbol(
            owner_cell_id=symbol.cell_id,
            symbol_kind=kind,
            center_angle_deg=symbol.center_angle_deg,
            center_radius=symbol.center_radius,
            local_top_angle_deg=local_top,
            size_S=symbol.size_S,
            height=SYMBOL_HEIGHT,
            base_z=BLACK_FIELD_Z,
        )
    return CutSymbol(
        owner_cell_id=symbol.cell_id,
        symbol_kind=kind,
        center_angle_deg=symbol.center_angle_deg,
        center_radius=symbol.center_radius,
        local_top_angle_deg=local_top,
        size_S=symbol.size_S,
        depth=SYMBOL_CUT_DEPTH,
        surface_z=SURFACE_Z,
    )


def _split_boundary_for_mixed(
    boundary: BoundarySpec,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Return ``((bs, be, bc, span), (ws, we, wc, span))`` for a mixed boundary.

    The boundary strip ``[start, end]`` is split at the shared edge
    (``center_angle_deg``). Cell-a's half is returned first when cell-a is
    BLACK, then cell-b's half. The caller filters by polarity.
    """
    mid = boundary.center_angle_deg
    left = (boundary.start_angle_deg, mid)
    right = (mid, boundary.end_angle_deg)
    return (
        (left[0], left[1], (left[0] + left[1]) / 2.0, left[1] - left[0]),
        (right[0], right[1], (right[0] + right[1]) / 2.0, right[1] - right[0]),
    )


def compile_boundary(boundary: BoundarySpec) -> List[CadOp]:
    """Emit one or two divider ops per boundary (see module docstring)."""
    ops: list[CadOp] = []
    a_polar, b_polar = boundary.polarity_a, boundary.polarity_b
    bs = boundary.start_angle_deg
    be = boundary.end_angle_deg
    bc = boundary.center_angle_deg
    span = boundary.span_deg

    if a_polar is Polarity.BLACK and b_polar is Polarity.BLACK:
        ops.append(
            RaisedDivider(
                owner_cell_id=boundary.cell_a_id,
                boundary_id=boundary.boundary_id,
                side="A",
                ring=boundary.ring,
                angle_start_deg=bs,
                angle_end_deg=be,
                center_angle_deg=bc,
                span_deg=span,
                inner_radius=boundary.inner_radius,
                outer_radius=boundary.outer_radius,
                height=DIVIDER_HEIGHT,
                base_z=BLACK_FIELD_Z,
                treatment=DividerTreatment.RAISED_RIB,
            )
        )
        return ops

    if a_polar is Polarity.WHITE and b_polar is Polarity.WHITE:
        ops.append(
            EngravedDivider(
                owner_cell_id=boundary.cell_a_id,
                boundary_id=boundary.boundary_id,
                side="A",
                ring=boundary.ring,
                angle_start_deg=bs,
                angle_end_deg=be,
                center_angle_deg=bc,
                span_deg=span,
                inner_radius=boundary.inner_radius,
                outer_radius=boundary.outer_radius,
                depth=DIVIDER_DEPTH,
                surface_z=SURFACE_Z,
                treatment=DividerTreatment.ENGRAVED_GROOVE,
            )
        )
        return ops

    # Mixed-polarity boundary: split the divider strip at the shared edge.
    # The half on the BLACK side carries the raised rib; the half on the
    # WHITE side carries the engraved groove. They are spatially disjoint.
    a_half, b_half = _split_boundary_for_mixed(boundary)
    if a_polar is Polarity.BLACK:
        black_cell_id, black_half, black_side = boundary.cell_a_id, a_half, "A"
        white_cell_id, white_half, white_side = boundary.cell_b_id, b_half, "B"
    else:
        black_cell_id, black_half, black_side = boundary.cell_b_id, b_half, "B"
        white_cell_id, white_half, white_side = boundary.cell_a_id, a_half, "A"

    ops.append(
        RaisedDivider(
            owner_cell_id=black_cell_id,
            boundary_id=boundary.boundary_id,
            side=black_side,
            ring=boundary.ring,
            angle_start_deg=black_half[0],
            angle_end_deg=black_half[1],
            center_angle_deg=black_half[2],
            span_deg=black_half[3],
            inner_radius=boundary.inner_radius,
            outer_radius=boundary.outer_radius,
            height=DIVIDER_HEIGHT,
            base_z=BLACK_FIELD_Z,
            treatment=DividerTreatment.RAISED_RIB,
        )
    )
    ops.append(
        EngravedDivider(
            owner_cell_id=white_cell_id,
            boundary_id=boundary.boundary_id,
            side=white_side,
            ring=boundary.ring,
            angle_start_deg=white_half[0],
            angle_end_deg=white_half[1],
            center_angle_deg=white_half[2],
            span_deg=white_half[3],
            inner_radius=boundary.inner_radius,
            outer_radius=boundary.outer_radius,
            depth=DIVIDER_DEPTH,
            surface_z=SURFACE_Z,
            treatment=DividerTreatment.ENGRAVED_GROOVE,
        )
    )
    return ops


# ---------------------------------------------------------------------------
# Top-level compile.
# ---------------------------------------------------------------------------
def compile_medallion(plan: Plan) -> List[CadOp]:
    """Compile a Plan into a deterministic ``list[CadOp]``."""
    inner = list(plan.inner_cells)
    outer = sorted(plan.outer_cells, key=lambda c: c.cell_id)

    ops: list[CadOp] = []

    # 1. Inner cell prisms.
    for c in inner:
        ops.append(compile_cell_prism(c))

    # 2. Outer cell prisms.
    for c in outer:
        ops.append(compile_cell_prism(c))

    # 3. Lowered fields for BLACK inner cells.
    for c in inner:
        if c.polarity is Polarity.BLACK:
            ops.append(compile_cell_lower_field(c))

    # 4. Lowered fields for BLACK outer cells.
    for c in outer:
        if c.polarity is Polarity.BLACK:
            ops.append(compile_cell_lower_field(c))

    # 5/6. Symbols.
    cell_by_id: dict[str, CellSpec] = {c.cell_id: c for c in inner}
    cell_by_id.update({c.cell_id: c for c in outer})

    inner_symbols = [s for s in plan.symbols if cell_by_id[s.cell_id].ring == "inner"]
    outer_symbols = [s for s in plan.symbols if cell_by_id[s.cell_id].ring == "outer"]
    inner_symbols_sorted = sorted(
        inner_symbols, key=lambda s: inner.index(cell_by_id[s.cell_id])
    )
    outer_symbols_sorted = sorted(outer_symbols, key=lambda s: s.cell_id)
    for s in inner_symbols_sorted:
        ops.append(compile_symbol(s))
    for s in outer_symbols_sorted:
        ops.append(compile_symbol(s))

    # 7/8. Boundaries (dividers).
    inner_boundaries = sorted(
        (b for b in plan.boundaries if b.ring == "inner"),
        key=lambda b: b.boundary_id,
    )
    outer_boundaries = sorted(
        (b for b in plan.boundaries if b.ring == "outer"),
        key=lambda b: b.boundary_id,
    )
    for b in inner_boundaries:
        ops.extend(compile_boundary(b))
    for b in outer_boundaries:
        ops.extend(compile_boundary(b))

    return ops


# ---------------------------------------------------------------------------
# Opposite-pair helper (AC2 — uses normalized delta, not raw subtraction).
# ---------------------------------------------------------------------------
def is_opposite_angle(a_deg: float, b_deg: float, tol_deg: float = 1e-6) -> bool:
    """Return True iff ``a`` and ``b`` are 180° apart (normalized)."""
    delta = normalized_angle_delta_deg(a_deg, b_deg)
    return abs(abs(delta) - 180.0) <= tol_deg
