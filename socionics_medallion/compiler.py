"""Pure compiler: plan -> list[CadOp].

This module MUST NOT import cadquery (or any CAD toolchain). It is also
forbidden from importing the executor module.

Output order is fixed (deterministic):
    1. All inner-cell prisms (in clockwise order)
    2. All outer-cell prisms (sorted by start_angle_deg)
    3. All lowered fields for black inner cells (clockwise order)
    4. All lowered fields for black outer cells (sorted by start_angle_deg)
    5. All inner symbols (clockwise order); each symbol is raised or cut
       based on its cell's polarity.
    6. All outer symbols (sorted by start_angle_deg)
    7. All inner dividers (sorted by start_angle_deg)
    8. All outer dividers (sorted by start_angle_deg)

Divider treatment rule for mixed-polarity boundaries
----------------------------------------------------
When two adjacent cells share a boundary:
  - BLACK | BLACK  -> RaisedDivider only (a single rib above both lowered
                      fields).
  - WHITE | WHITE  -> EngravedDivider only (a single groove on the surface).
  - BLACK | WHITE  -> BOTH ops emitted: a RaisedDivider over the black
                      side's lowered field, AND an EngravedDivider in the
                      white side's surface. Each op covers the angular
                      width of the divider but uses the same start/end
                      angle. They differ only in radius footprint:
                      the raised rib sits on the black cell's radius
                      extent, the engraved groove sits on the white cell's
                      extent. Since adjacent cells in a ring share radii,
                      they overlap geometrically but represent two distinct
                      relief features (one above the black field, one cut
                      into the white field).
"""

from __future__ import annotations

from typing import Iterable, List

from socionics_medallion.ir import (
    CadOp,
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
)
from socionics_medallion.plan import (
    BASE_Z,
    BLACK_FIELD_Z,
    CellSpec,
    DIVIDER_DEPTH,
    DIVIDER_HEIGHT,
    DividerSpec,
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


# ---------------------------------------------------------------------------
# Per-element sub-compilers.
# ---------------------------------------------------------------------------
def compile_cell_prism(cell: CellSpec) -> Prism:
    return Prism(
        center=_CENTER,
        inner_radius=cell.inner_radius,
        outer_radius=cell.outer_radius,
        start_angle_deg=cell.start_angle_deg,
        end_angle_deg=cell.end_angle_deg,
        z0=BASE_Z,
        z1=SURFACE_Z,
    )


def compile_cell_lower_field(cell: CellSpec) -> LowerField:
    return LowerField(
        center=_CENTER,
        inner_radius=cell.inner_radius,
        outer_radius=cell.outer_radius,
        start_angle_deg=cell.start_angle_deg,
        end_angle_deg=cell.end_angle_deg,
        surface_z=SURFACE_Z,
        depth=FIELD_LOWER_DEPTH,
    )


def compile_symbol(symbol: SymbolSpec) -> CadOp:
    """A black symbol becomes RaisedSymbol; a white symbol becomes CutSymbol."""
    kind = _to_ir_symbol_kind(symbol.kind)
    if symbol.polarity is Polarity.BLACK:
        return RaisedSymbol(
            symbol_kind=kind,
            center_angle_deg=symbol.center_angle_deg,
            center_radius=symbol.center_radius,
            size_S=symbol.size_S,
            height=SYMBOL_HEIGHT,
            base_z=BLACK_FIELD_Z,
        )
    return CutSymbol(
        symbol_kind=kind,
        center_angle_deg=symbol.center_angle_deg,
        center_radius=symbol.center_radius,
        size_S=symbol.size_S,
        depth=SYMBOL_CUT_DEPTH,
        surface_z=SURFACE_Z,
    )


def compile_divider(divider: DividerSpec) -> List[CadOp]:
    """Emit zero, one, or two divider ops per boundary (see module docstring)."""
    ops: list[CadOp] = []
    a, b = divider.polarity_a, divider.polarity_b
    has_black = Polarity.BLACK in (a, b)
    has_white = Polarity.WHITE in (a, b)
    if has_black:
        ops.append(
            RaisedDivider(
                start_angle_deg=divider.start_angle_deg,
                end_angle_deg=divider.end_angle_deg,
                inner_radius=divider.inner_radius,
                outer_radius=divider.outer_radius,
                height=DIVIDER_HEIGHT,
                base_z=BLACK_FIELD_Z,
            )
        )
    if has_white:
        ops.append(
            EngravedDivider(
                start_angle_deg=divider.start_angle_deg,
                end_angle_deg=divider.end_angle_deg,
                inner_radius=divider.inner_radius,
                outer_radius=divider.outer_radius,
                depth=DIVIDER_DEPTH,
                surface_z=SURFACE_Z,
            )
        )
    return ops


# ---------------------------------------------------------------------------
# Top-level compile.
# ---------------------------------------------------------------------------
def compile_medallion(plan: Plan) -> List[CadOp]:
    """Compile a Plan into a deterministic list[CadOp]."""
    inner = list(plan.inner_cells)
    outer_sorted = sorted(plan.outer_cells, key=lambda c: c.start_angle_deg)

    ops: list[CadOp] = []

    # 1. Inner cell prisms.
    for c in inner:
        ops.append(compile_cell_prism(c))

    # 2. Outer cell prisms.
    for c in outer_sorted:
        ops.append(compile_cell_prism(c))

    # 3. Lowered fields for BLACK inner cells.
    for c in inner:
        if c.polarity is Polarity.BLACK:
            ops.append(compile_cell_lower_field(c))

    # 4. Lowered fields for BLACK outer cells.
    for c in outer_sorted:
        if c.polarity is Polarity.BLACK:
            ops.append(compile_cell_lower_field(c))

    # 5/6. Symbols. Match the cell ordering used for prisms above.
    cell_by_id = {c.cell_id: c for c in inner}
    cell_by_id.update({c.cell_id: c for c in outer_sorted})

    inner_symbols = [s for s in plan.symbols if cell_by_id[s.cell_id].ring == "inner"]
    outer_symbols = [s for s in plan.symbols if cell_by_id[s.cell_id].ring == "outer"]
    # Inner symbols in clockwise (inner_cells) order.
    inner_symbols_sorted = sorted(
        inner_symbols, key=lambda s: inner.index(cell_by_id[s.cell_id])
    )
    # Outer symbols sorted by their cell's start_angle_deg.
    outer_symbols_sorted = sorted(
        outer_symbols, key=lambda s: cell_by_id[s.cell_id].start_angle_deg
    )
    for s in inner_symbols_sorted:
        ops.append(compile_symbol(s))
    for s in outer_symbols_sorted:
        ops.append(compile_symbol(s))

    # 7/8. Dividers.
    inner_dividers = sorted(
        (d for d in plan.dividers if d.ring == "inner"),
        key=lambda d: d.start_angle_deg,
    )
    outer_dividers = sorted(
        (d for d in plan.dividers if d.ring == "outer"),
        key=lambda d: d.start_angle_deg,
    )
    for d in inner_dividers:
        ops.extend(compile_divider(d))
    for d in outer_dividers:
        ops.extend(compile_divider(d))

    return ops
