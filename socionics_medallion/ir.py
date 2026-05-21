"""Pure-data instruction IR for the medallion compiler.

This module MUST NOT import cadquery (or any CAD toolchain). Each CadOp is a
frozen, hashable, equality-comparable value type. Variants are discriminated
by their concrete dataclass type — and additionally tagged with an `op` field
in their dict serialization so the stub executor and golden file are stable.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, fields
from typing import Tuple


class SymbolKind(enum.Enum):
    SQUARE = "SQUARE"
    CIRCLE = "CIRCLE"
    TRIANGLE = "TRIANGLE"
    ETHICS = "ETHICS"


class CadOp:
    """Marker base class for the sealed set of instruction variants.

    Concrete variants subclass via dataclass inheritance with `slots=True`
    and `frozen=True`. Equality is structural via the dataclass machinery.
    """

    __slots__ = ()


# ---------------------------------------------------------------------------
# Sector geometry primitives.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Prism(CadOp):
    """A sector prism (the unit cell of the medallion).

    The sector is the planar wedge between two radii at the given inner/outer
    radius, swept from `start_angle_deg` to `end_angle_deg` (CCW), extruded
    from z=z0 up to z=z1.
    """

    center: Tuple[float, float]
    inner_radius: float
    outer_radius: float
    start_angle_deg: float
    end_angle_deg: float
    z0: float
    z1: float


@dataclass(frozen=True, slots=True)
class LowerField(CadOp):
    """Subtract a sector slab from a cell's top surface to create a lowered
    (black-polarity) field. The lowered field's top sits at
    `surface_z - depth`.
    """

    center: Tuple[float, float]
    inner_radius: float
    outer_radius: float
    start_angle_deg: float
    end_angle_deg: float
    surface_z: float
    depth: float


# ---------------------------------------------------------------------------
# Symbol geometry (black raised / white cut).
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RaisedSymbol(CadOp):
    """A black-polarity aspect symbol raised from its lowered field."""

    symbol_kind: SymbolKind
    center_angle_deg: float
    center_radius: float
    size_S: float
    height: float
    base_z: float


@dataclass(frozen=True, slots=True)
class CutSymbol(CadOp):
    """A white-polarity aspect symbol carved down into the surface."""

    symbol_kind: SymbolKind
    center_angle_deg: float
    center_radius: float
    size_S: float
    depth: float
    surface_z: float


# ---------------------------------------------------------------------------
# Divider geometry.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RaisedDivider(CadOp):
    """A rib protruding above a black-polarity field."""

    start_angle_deg: float
    end_angle_deg: float
    inner_radius: float
    outer_radius: float
    height: float
    base_z: float


@dataclass(frozen=True, slots=True)
class EngravedDivider(CadOp):
    """A groove cut into a white-polarity surface."""

    start_angle_deg: float
    end_angle_deg: float
    inner_radius: float
    outer_radius: float
    depth: float
    surface_z: float


# ---------------------------------------------------------------------------
# Op-name discriminator + dict serialization.
# ---------------------------------------------------------------------------
_OP_NAMES: dict[type, str] = {
    Prism: "prism",
    LowerField: "lower_field",
    RaisedSymbol: "raised_symbol",
    CutSymbol: "cut_symbol",
    RaisedDivider: "raised_divider",
    EngravedDivider: "engraved_divider",
}

ALL_OP_TYPES: tuple[type, ...] = tuple(_OP_NAMES.keys())


def op_name(op: CadOp) -> str:
    """Return the stable discriminator string for an op instance."""
    try:
        return _OP_NAMES[type(op)]
    except KeyError as exc:  # pragma: no cover - defensive
        raise TypeError(f"Unknown CadOp variant: {type(op).__name__}") from exc


def _coerce(value: object) -> object:
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, tuple):
        return [_coerce(v) for v in value]
    return value


def op_to_dict(op: CadOp) -> dict:
    """Serialize a CadOp to a JSON-friendly dict.

    Keys: `op` (discriminator) + every dataclass field in declaration order.
    Enums are serialized by `name`; tuples become lists.
    """
    out: dict = {"op": op_name(op)}
    for f in fields(op):  # type: ignore[arg-type]
        out[f.name] = _coerce(getattr(op, f.name))
    return out
