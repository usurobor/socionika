"""Pure-Python plan/spec for the socionics medallion.

This module MUST NOT import cadquery (or any CAD toolchain). It is consumed
read-only by the compiler.

Layout (issue #1 AC3, AC4):
    Inner clockwise from 12:00: ЧИ, ЧС, ЧЛ, ЧЭ, БИ, БС, БЛ, БЭ
    Polarity: Ч* are BLACK; Б* are WHITE.
    Aspect: *И = TRIANGLE, *С = CIRCLE, *Л = SQUARE, *Э = ETHICS.
    Each inner cell has two outer half-sized cells of opposite polarity per
    the AC4 mapping table.

Cell-id scheme
--------------
Per issue #3 §AC1 the Cyrillic function code (``ЧИ``, ``БЛ`` etc.) is the cell's
``function_code`` — it is *not* unique repo-wide, because each outer-ring
function code appears twice (once on each side of its sponsoring inner cell).

The unique ``cell_id`` is positional:

* Inner cells: ``inner:NN`` where ``NN`` is the clockwise index 00..07
  (``inner:00`` = ЧИ at 12:00, ``inner:01`` = ЧС, … ``inner:07`` = БЭ).
* Outer cells: ``outer:NN`` where ``NN`` is the index 00..15 produced by
  sorting outer cells by ``angle_start_deg`` ascending and assigning indices
  in that order. The sort is deterministic because outer-ring boundaries are
  on the 22.5° grid.

Lookups (symbol kind, polarity, opposite) key on ``cell_id``; ``function_code``
is informational and may collide across the outer ring.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Tuple

# ---------------------------------------------------------------------------
# Topology constants (issue #1 AC2).
# ---------------------------------------------------------------------------
INNER_SECTORS: int = 8
OUTER_SECTORS: int = 16

INNER_SECTOR_DEG: float = 360.0 / INNER_SECTORS  # 45.0
OUTER_SECTOR_DEG: float = 360.0 / OUTER_SECTORS  # 22.5

# ---------------------------------------------------------------------------
# Geometric constants (named — no magic numbers in the compiler).
# All linear units are millimetres; angles are degrees.
# ---------------------------------------------------------------------------
INNER_HUB_RADIUS: float = 4.0
INNER_OUTER_RADIUS: float = 22.0  # outer radius of the inner ring
OUTER_RING_RADIUS: float = 38.0  # outer radius of the outer ring

MEDALLION_HEIGHT: float = 4.0  # surface_z for white fields
FIELD_LOWER_DEPTH: float = 0.6  # black fields are this much lower

SYMBOL_SIDE_S_INNER: float = 6.0  # canonical S for inner-ring symbols
SYMBOL_SIDE_S_OUTER: float = 3.5  # canonical S for outer-ring symbols
SYMBOL_HEIGHT: float = 0.8  # raised-symbol height above its (black) field
SYMBOL_CUT_DEPTH: float = 0.6  # white-symbol cut depth into surface

DIVIDER_WIDTH_DEG: float = 0.6  # angular width of dividers
DIVIDER_HEIGHT: float = 0.4  # raised-rib height above black fields
DIVIDER_DEPTH: float = 0.3  # engraved-groove depth into white fields

# Top of the medallion's plain (white) surface.
SURFACE_Z: float = MEDALLION_HEIGHT
# Top of a black (lowered) field.
BLACK_FIELD_Z: float = MEDALLION_HEIGHT - FIELD_LOWER_DEPTH
# Bottom of the medallion.
BASE_Z: float = 0.0


# ---------------------------------------------------------------------------
# Enums.
# ---------------------------------------------------------------------------
class Polarity(enum.Enum):
    BLACK = "BLACK"
    WHITE = "WHITE"


class Aspect(enum.Enum):
    I = "I"  # noqa: E741  (matches socionics letter; intentional)
    S = "S"
    L = "L"
    E = "E"


class SymbolKind(enum.Enum):
    SQUARE = "SQUARE"
    CIRCLE = "CIRCLE"
    TRIANGLE = "TRIANGLE"
    ETHICS = "ETHICS"


# Maps the second Russian letter of the label to the aspect/symbol kind.
_LETTER_TO_ASPECT = {"И": Aspect.I, "С": Aspect.S, "Л": Aspect.L, "Э": Aspect.E}
_ASPECT_TO_SYMBOL = {
    Aspect.I: SymbolKind.TRIANGLE,
    Aspect.S: SymbolKind.CIRCLE,
    Aspect.L: SymbolKind.SQUARE,
    Aspect.E: SymbolKind.ETHICS,
}

# Inner ring clockwise from 12:00 (issue #1 AC3).
INNER_LABELS_CLOCKWISE: Tuple[str, ...] = (
    "ЧИ",
    "ЧС",
    "ЧЛ",
    "ЧЭ",
    "БИ",
    "БС",
    "БЛ",
    "БЭ",
)

# Outer mapping (issue #1 AC4). Each inner has two outer cells of opposite
# polarity. The first child is the left half (CCW side), the second is the
# right half (CW side), in plan coordinates (CCW = positive degrees).
OUTER_MAPPING: dict[str, Tuple[str, str]] = {
    "ЧИ": ("БЛ", "БЭ"),
    "ЧС": ("БЛ", "БЭ"),
    "ЧЛ": ("БИ", "БС"),
    "ЧЭ": ("БИ", "БС"),
    "БИ": ("ЧЛ", "ЧЭ"),
    "БС": ("ЧЛ", "ЧЭ"),
    "БЛ": ("ЧИ", "ЧС"),
    "БЭ": ("ЧИ", "ЧС"),
}


# ---------------------------------------------------------------------------
# Spec dataclasses.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CellSpec:
    cell_id: str  # unique, positional (e.g. 'inner:00', 'outer:13')
    function_code: str  # Cyrillic 2-letter label (not unique in outer ring)
    ring: str  # 'inner' | 'outer'
    polarity: Polarity
    aspect: Aspect
    start_angle_deg: float
    end_angle_deg: float
    center_angle_deg: float
    span_deg: float
    inner_radius: float
    outer_radius: float
    # Outer cells point at their parent inner cell's cell_id; inner cells
    # point at themselves (parent_cell_id == cell_id) for uniform indexing.
    parent_cell_id: str


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    cell_id: str
    kind: SymbolKind
    polarity: Polarity
    center_angle_deg: float
    center_radius: float
    size_S: float


@dataclass(frozen=True, slots=True)
class BoundarySpec:
    """A single radial boundary between two adjacent cells.

    The compiler decides treatment (raised rib, engraved groove, or both)
    based on the polarities of the adjacent cells.
    """

    boundary_id: str
    ring: str  # 'inner' | 'outer'
    cell_a_id: str
    cell_b_id: str
    polarity_a: Polarity
    polarity_b: Polarity
    start_angle_deg: float
    end_angle_deg: float
    center_angle_deg: float
    span_deg: float
    inner_radius: float
    outer_radius: float


@dataclass(frozen=True, slots=True)
class Plan:
    inner_cells: Tuple[CellSpec, ...]
    outer_cells: Tuple[CellSpec, ...]
    symbols: Tuple[SymbolSpec, ...]
    boundaries: Tuple[BoundarySpec, ...]


# ---------------------------------------------------------------------------
# Construction.
# ---------------------------------------------------------------------------
def _polarity_of_code(code: str) -> Polarity:
    return Polarity.BLACK if code[0] == "Ч" else Polarity.WHITE


def _aspect_of_code(code: str) -> Aspect:
    return _LETTER_TO_ASPECT[code[1]]


def _symbol_kind_of_code(code: str) -> SymbolKind:
    return _ASPECT_TO_SYMBOL[_aspect_of_code(code)]


def _inner_center_angle(index: int) -> float:
    """Inner cell ``index`` (0..7) centered clockwise from 12:00.

    In math convention (CCW from +x), 12:00 is 90°. Going clockwise means
    angle decreases: index 0 at 90°, index 1 at 90° - 45° = 45°, etc.

    Angles are returned in the unwrapped range (-180, 180]. The convention
    is to NOT modulo to [0, 360), so that cells which straddle 0° (the
    ЧЛ-БЛ axis) remain a contiguous [start, end] interval with end > start.
    """
    raw = 90.0 - index * INNER_SECTOR_DEG
    while raw <= -180.0:
        raw += 360.0
    while raw > 180.0:
        raw -= 360.0
    return raw


def _inner_span(index: int) -> Tuple[float, float]:
    """Return ``(start_deg, end_deg)`` for inner cell ``index``.

    Always ``end > start``.
    """
    center = _inner_center_angle(index)
    start = center - INNER_SECTOR_DEG / 2.0
    end = center + INNER_SECTOR_DEG / 2.0
    return (start, end)


def _inner_cell_id(index: int) -> str:
    return f"inner:{index:02d}"


def _outer_cell_id(index: int) -> str:
    return f"outer:{index:02d}"


def _boundary_id(ring: str, index: int) -> str:
    return f"{ring}-boundary:{index:02d}"


def build_plan() -> Plan:
    """Construct the canonical socionics medallion plan.

    Deterministic: identical output for identical inputs. No filesystem,
    no globals, no randomness.
    """
    # Inner cells, in clockwise order, get sequential cell_ids inner:00..07.
    inner_cells: list[CellSpec] = []
    for i, code in enumerate(INNER_LABELS_CLOCKWISE):
        start, end = _inner_span(i)
        center = _inner_center_angle(i)
        cell_id = _inner_cell_id(i)
        inner_cells.append(
            CellSpec(
                cell_id=cell_id,
                function_code=code,
                ring="inner",
                polarity=_polarity_of_code(code),
                aspect=_aspect_of_code(code),
                start_angle_deg=start,
                end_angle_deg=end,
                center_angle_deg=center,
                span_deg=INNER_SECTOR_DEG,
                inner_radius=INNER_HUB_RADIUS,
                outer_radius=INNER_OUTER_RADIUS,
                parent_cell_id=cell_id,
            )
        )

    # Outer cells: two per inner. Build the raw list first, then sort by
    # start angle and assign deterministic outer:NN cell_ids.
    raw_outer: list[dict] = []
    for parent in inner_cells:
        left_code, right_code = OUTER_MAPPING[parent.function_code]
        mid = (parent.start_angle_deg + parent.end_angle_deg) / 2.0
        halves = (
            (left_code, parent.start_angle_deg, mid),
            (right_code, mid, parent.end_angle_deg),
        )
        for code, ostart, oend in halves:
            raw_outer.append(
                dict(
                    function_code=code,
                    parent_cell_id=parent.cell_id,
                    start=ostart,
                    end=oend,
                )
            )

    raw_outer.sort(key=lambda r: r["start"])
    outer_cells: list[CellSpec] = []
    for idx, r in enumerate(raw_outer):
        ostart = float(r["start"])
        oend = float(r["end"])
        outer_cells.append(
            CellSpec(
                cell_id=_outer_cell_id(idx),
                function_code=str(r["function_code"]),
                ring="outer",
                polarity=_polarity_of_code(str(r["function_code"])),
                aspect=_aspect_of_code(str(r["function_code"])),
                start_angle_deg=ostart,
                end_angle_deg=oend,
                center_angle_deg=(ostart + oend) / 2.0,
                span_deg=oend - ostart,
                inner_radius=INNER_OUTER_RADIUS,
                outer_radius=OUTER_RING_RADIUS,
                parent_cell_id=str(r["parent_cell_id"]),
            )
        )

    # Symbols — one per cell, 24 total.
    symbols: list[SymbolSpec] = []
    for c in inner_cells:
        symbols.append(
            SymbolSpec(
                cell_id=c.cell_id,
                kind=_symbol_kind_of_code(c.function_code),
                polarity=c.polarity,
                center_angle_deg=c.center_angle_deg,
                center_radius=(INNER_HUB_RADIUS + INNER_OUTER_RADIUS) / 2.0,
                size_S=SYMBOL_SIDE_S_INNER,
            )
        )
    for c in outer_cells:
        symbols.append(
            SymbolSpec(
                cell_id=c.cell_id,
                kind=_symbol_kind_of_code(c.function_code),
                polarity=c.polarity,
                center_angle_deg=c.center_angle_deg,
                center_radius=(INNER_OUTER_RADIUS + OUTER_RING_RADIUS) / 2.0,
                size_S=SYMBOL_SIDE_S_OUTER,
            )
        )

    # Boundaries — between adjacent cells in each ring. We emit one
    # BoundarySpec per inter-cell edge, recorded at the shared edge angle.
    boundaries: list[BoundarySpec] = []
    half_w = DIVIDER_WIDTH_DEG / 2.0

    # Inner ring: 8 boundaries, in clockwise (inner_cells) order.
    for i in range(INNER_SECTORS):
        a = inner_cells[i]
        b = inner_cells[(i + 1) % INNER_SECTORS]
        # Inner cells are ordered clockwise (descending centers). The shared
        # edge between cell i and cell i+1 is cell i's start_angle_deg (which
        # equals cell (i+1)'s end_angle_deg in CCW). Use unwrapped angles.
        edge = a.start_angle_deg
        bstart = edge - half_w
        bend = edge + half_w
        boundaries.append(
            BoundarySpec(
                boundary_id=_boundary_id("inner", i),
                ring="inner",
                cell_a_id=a.cell_id,
                cell_b_id=b.cell_id,
                polarity_a=a.polarity,
                polarity_b=b.polarity,
                start_angle_deg=bstart,
                end_angle_deg=bend,
                center_angle_deg=edge,
                span_deg=DIVIDER_WIDTH_DEG,
                inner_radius=INNER_HUB_RADIUS,
                outer_radius=INNER_OUTER_RADIUS,
            )
        )

    # Outer ring: 16 boundaries, in CCW order by start_angle_deg.
    for i in range(OUTER_SECTORS):
        a = outer_cells[i]
        b = outer_cells[(i + 1) % OUTER_SECTORS]
        edge = a.end_angle_deg
        bstart = edge - half_w
        bend = edge + half_w
        boundaries.append(
            BoundarySpec(
                boundary_id=_boundary_id("outer", i),
                ring="outer",
                cell_a_id=a.cell_id,
                cell_b_id=b.cell_id,
                polarity_a=a.polarity,
                polarity_b=b.polarity,
                start_angle_deg=bstart,
                end_angle_deg=bend,
                center_angle_deg=edge,
                span_deg=DIVIDER_WIDTH_DEG,
                inner_radius=INNER_OUTER_RADIUS,
                outer_radius=OUTER_RING_RADIUS,
            )
        )

    return Plan(
        inner_cells=tuple(inner_cells),
        outer_cells=tuple(outer_cells),
        symbols=tuple(symbols),
        boundaries=tuple(boundaries),
    )
