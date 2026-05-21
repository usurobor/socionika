"""Pure-Python plan/spec for the socionics medallion.

This module MUST NOT import cadquery (or any CAD toolchain). It is consumed
read-only by the compiler.

Layout (issue #1 AC3, AC4):
    Inner clockwise from 12:00: ЧИ, ЧС, ЧЛ, ЧЭ, БИ, БС, БЛ, БЭ
    Polarity: Ч* are BLACK; Б* are WHITE.
    Aspect: *И = TRIANGLE, *С = CIRCLE, *Л = SQUARE, *Э = ETHICS.
    Each inner cell has two outer half-sized cells of opposite polarity per
    the AC4 mapping table.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
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
    cell_id: str
    label: str  # the Cyrillic 2-letter label, e.g. "ЧИ"
    ring: str  # "inner" | "outer"
    polarity: Polarity
    aspect: Aspect
    start_angle_deg: float
    end_angle_deg: float
    center_angle_deg: float
    inner_radius: float
    outer_radius: float
    # Outer cells point at their parent inner cell's label; inner cells point
    # at themselves (parent_label == label) for uniform indexing.
    parent_label: str


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    cell_id: str
    kind: SymbolKind
    polarity: Polarity
    center_angle_deg: float
    center_radius: float
    size_S: float


@dataclass(frozen=True, slots=True)
class DividerSpec:
    """A single radial divider between two adjacent cells.

    The compiler decides treatment based on `polarity_a`/`polarity_b`.
    """

    start_angle_deg: float
    end_angle_deg: float
    inner_radius: float
    outer_radius: float
    polarity_a: Polarity
    polarity_b: Polarity
    ring: str  # "inner" | "outer"


@dataclass(frozen=True, slots=True)
class Plan:
    inner_cells: Tuple[CellSpec, ...]
    outer_cells: Tuple[CellSpec, ...]
    symbols: Tuple[SymbolSpec, ...]
    dividers: Tuple[DividerSpec, ...]


# ---------------------------------------------------------------------------
# Construction.
# ---------------------------------------------------------------------------
def _polarity_of_label(label: str) -> Polarity:
    return Polarity.BLACK if label[0] == "Ч" else Polarity.WHITE


def _aspect_of_label(label: str) -> Aspect:
    return _LETTER_TO_ASPECT[label[1]]


def _symbol_kind_of_label(label: str) -> SymbolKind:
    return _ASPECT_TO_SYMBOL[_aspect_of_label(label)]


def _inner_center_angle(index: int) -> float:
    """Inner cell `index` (0..7) centered clockwise from 12:00.

    In math convention (CCW from +x), 12:00 is 90°. Going clockwise means
    angle decreases: index 0 at 90°, index 1 at 90° - 45° = 45°, etc.

    Angles are returned in the unwrapped range (-180, 180]. The convention
    is to NOT modulo to [0, 360), so that cells which straddle 0° (the
    ЧЛ-БЛ axis) remain a contiguous [start, end] interval with end > start.
    """
    raw = 90.0 - index * INNER_SECTOR_DEG
    # Normalise to (-180, 180].
    while raw <= -180.0:
        raw += 360.0
    while raw > 180.0:
        raw -= 360.0
    return raw


def _inner_span(index: int) -> Tuple[float, float]:
    """Return (start_deg, end_deg) for inner cell `index`. `end > start` always."""
    center = _inner_center_angle(index)
    start = center - INNER_SECTOR_DEG / 2.0
    end = center + INNER_SECTOR_DEG / 2.0
    return (start, end)


def build_plan() -> Plan:
    """Construct the canonical socionics medallion plan.

    Deterministic: identical output for identical inputs. No filesystem,
    no globals, no randomness.
    """
    inner_cells: list[CellSpec] = []
    for i, label in enumerate(INNER_LABELS_CLOCKWISE):
        start, end = _inner_span(i)
        center = _inner_center_angle(i)
        inner_cells.append(
            CellSpec(
                # Inner cell_id is just the Cyrillic label so that symbols
                # in either ring can be indexed by their cell's natural key.
                cell_id=label,
                label=label,
                ring="inner",
                polarity=_polarity_of_label(label),
                aspect=_aspect_of_label(label),
                start_angle_deg=start,
                end_angle_deg=end,
                center_angle_deg=center,
                inner_radius=INNER_HUB_RADIUS,
                outer_radius=INNER_OUTER_RADIUS,
                parent_label=label,
            )
        )

    outer_cells: list[CellSpec] = []
    # For each inner cell, emit two outer cells: left half (CCW side, lower
    # angles relative to the parent center in math convention) and right
    # half (CW side). Per OUTER_MAPPING, the first child label is the
    # left-half occupant.
    for parent in inner_cells:
        left_label, right_label = OUTER_MAPPING[parent.label]
        mid = (parent.start_angle_deg + parent.end_angle_deg) / 2.0
        halves = (
            (left_label, parent.start_angle_deg, mid, "L"),
            (right_label, mid, parent.end_angle_deg, "R"),
        )
        for label, ostart, oend, side in halves:
            outer_cells.append(
                CellSpec(
                    cell_id=f"outer:{parent.label}:{side}",
                    label=label,
                    ring="outer",
                    polarity=_polarity_of_label(label),
                    aspect=_aspect_of_label(label),
                    start_angle_deg=ostart,
                    end_angle_deg=oend,
                    center_angle_deg=(ostart + oend) / 2.0,
                    inner_radius=INNER_OUTER_RADIUS,
                    outer_radius=OUTER_RING_RADIUS,
                    parent_label=parent.label,
                )
            )

    # Symbols — one per cell, 24 total.
    symbols: list[SymbolSpec] = []
    for c in inner_cells:
        symbols.append(
            SymbolSpec(
                cell_id=c.cell_id,
                kind=_symbol_kind_of_label(c.label),
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
                kind=_symbol_kind_of_label(c.label),
                polarity=c.polarity,
                center_angle_deg=c.center_angle_deg,
                center_radius=(INNER_OUTER_RADIUS + OUTER_RING_RADIUS) / 2.0,
                size_S=SYMBOL_SIDE_S_OUTER,
            )
        )

    # Dividers — between adjacent cells in each ring. We emit one divider
    # per inter-cell boundary, recorded at the shared edge angle.
    dividers: list[DividerSpec] = []
    # Inner ring: 8 boundaries.
    for i in range(INNER_SECTORS):
        a = inner_cells[i]
        b = inner_cells[(i + 1) % INNER_SECTORS]
        edge = a.end_angle_deg  # shared edge
        half_w = DIVIDER_WIDTH_DEG / 2.0
        dividers.append(
            DividerSpec(
                start_angle_deg=(edge - half_w) % 360.0,
                end_angle_deg=(edge + half_w) % 360.0,
                inner_radius=INNER_HUB_RADIUS,
                outer_radius=INNER_OUTER_RADIUS,
                polarity_a=a.polarity,
                polarity_b=b.polarity,
                ring="inner",
            )
        )
    # Outer ring: 16 boundaries. To get deterministic adjacency order we
    # sort outer cells by start_angle_deg.
    outer_sorted = sorted(outer_cells, key=lambda c: c.start_angle_deg)
    for i in range(OUTER_SECTORS):
        a = outer_sorted[i]
        b = outer_sorted[(i + 1) % OUTER_SECTORS]
        edge = a.end_angle_deg
        half_w = DIVIDER_WIDTH_DEG / 2.0
        dividers.append(
            DividerSpec(
                start_angle_deg=(edge - half_w) % 360.0,
                end_angle_deg=(edge + half_w) % 360.0,
                inner_radius=INNER_OUTER_RADIUS,
                outer_radius=OUTER_RING_RADIUS,
                polarity_a=a.polarity,
                polarity_b=b.polarity,
                ring="outer",
            )
        )

    return Plan(
        inner_cells=tuple(inner_cells),
        outer_cells=tuple(outer_cells),
        symbols=tuple(symbols),
        dividers=tuple(dividers),
    )
