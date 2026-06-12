"""Pure 2D symbol-geometry helpers.

This module MUST NOT import ``cadquery`` (or any CAD toolchain). It exposes
profile helpers used by the compiler / executor when materializing symbol
geometry per issue #3 §AC4.

Local frame convention
----------------------
Every profile is expressed in the **local symbol frame**: the symbol's
"top" (apex) points along the local +Y axis, the symbol is centered at the
origin, and ``S`` is the canonical edge length.

Profiles are CAD-agnostic — they are returned as :class:`Profile` records
containing an ordered list of 2D vertices forming a closed polyline. The
executor decides how to turn that polyline into a CadQuery feature.

Symbol shapes (operator's AC4 list, verbatim properties)
--------------------------------------------------------
* **square**: bounding box ``S × S``; area ``S²``.
* **circle**: radius ``S/2``; diameter ``S``; inscribed in the ``S × S`` box.
* **triangle**: equilateral; every vertex at distance ``S/2`` from the
  centroid; apex aligned with local ``+Y``.
* **ethics**: exact 3/4 square — bounding box ``S × S``, area ``3/4 · S²``,
  upper-right local quadrant removed.

World-frame placement (AC5)
---------------------------
A medallion cell sits at world angle ``θ`` on a positive radius. The
symbol's local ``+Y`` (its "top") must point **toward the medallion
center**, i.e. radially inward. The corresponding world vector is
``(-cos θ, -sin θ)``. The perpendicular ``local_right`` is chosen so the
frame is right-handed: rotating ``local_right`` by +90° (CCW) yields
``local_top``. Solving gives ``local_right = (-sin θ, cos θ)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True, slots=True)
class Profile:
    """A closed planar polyline in a symbol's local frame.

    Vertices are listed in CCW order so the interior is on the left of each
    edge. The polyline is implicitly closed (last vertex connects to first).
    """

    vertices: Tuple[Tuple[float, float], ...]

    def bounding_box(self) -> Tuple[float, float, float, float]:
        """Return ``(xmin, ymin, xmax, ymax)`` of the profile's vertices."""
        if not self.vertices:
            raise ValueError("empty profile has no bounding box")
        xs = tuple(v[0] for v in self.vertices)
        ys = tuple(v[1] for v in self.vertices)
        return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# Profile constructors.
# ---------------------------------------------------------------------------
def square_profile(S: float) -> Profile:  # noqa: N803 — operator naming
    """Return the canonical square profile (``S × S``, centered at origin)."""
    if S <= 0.0:
        raise ValueError("S must be positive")
    h = S / 2.0
    return Profile(
        vertices=(
            (-h, -h),
            (h, -h),
            (h, h),
            (-h, h),
        )
    )


def circle_profile(S: float, segments: int = 64) -> Profile:  # noqa: N803
    """Return a polygonal approximation of the canonical circle profile.

    Inscribed in the same ``S × S`` bounding box as :func:`square_profile`
    (radius ``S/2``). ``segments`` controls the polygonal resolution.
    """
    if S <= 0.0:
        raise ValueError("S must be positive")
    if segments < 3:
        raise ValueError("segments must be >= 3")
    r = S / 2.0
    verts: list[Tuple[float, float]] = []
    for i in range(segments):
        t = 2.0 * math.pi * i / segments
        verts.append((r * math.cos(t), r * math.sin(t)))
    return Profile(vertices=tuple(verts))


def triangle_profile(S: float) -> Profile:  # noqa: N803
    """Return the canonical equilateral triangle profile.

    Every vertex is at distance ``S / 2`` from the origin (circumradius);
    the apex aligns with local ``+Y`` (``local_top_vector``). Vertices are
    listed CCW starting at the apex.
    """
    if S <= 0.0:
        raise ValueError("S must be positive")
    r = S / 2.0
    # Apex on +Y; other two at ±120°.
    angles_deg = (90.0, 210.0, 330.0)
    verts = tuple(
        (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
        for a in angles_deg
    )
    return Profile(vertices=verts)


def ethics_profile(S: float) -> Profile:  # noqa: N803
    """Return the canonical "ethics" profile — an exact 3/4 square.

    The bounding box is ``S × S``; the upper-right local quadrant is
    removed, leaving an L-shape of area ``3/4 · S²``. Vertices are listed
    CCW starting at the lower-left corner.
    """
    if S <= 0.0:
        raise ValueError("S must be positive")
    h = S / 2.0
    return Profile(
        vertices=(
            (-h, -h),
            (h, -h),
            (h, 0.0),
            (0.0, 0.0),
            (0.0, h),
            (-h, h),
        )
    )


# ---------------------------------------------------------------------------
# Orientation helpers (AC5).
# ---------------------------------------------------------------------------
def local_top_vector_for_center_angle(center_angle_deg: float) -> Tuple[float, float]:
    """Unit vector pointing from a symbol's cell-center toward the medallion center.

    A medallion cell at world angle ``θ`` sits at ``(r cos θ, r sin θ)``;
    the inward direction is ``(-cos θ, -sin θ)``.
    """
    t = math.radians(center_angle_deg)
    return (-math.cos(t), -math.sin(t))


def local_right_vector_for_center_angle(center_angle_deg: float) -> Tuple[float, float]:
    """Unit vector forming a right-handed frame with :func:`local_top_vector_for_center_angle`.

    Rotating ``local_right`` by +90° (CCW) produces ``local_top``. With
    ``local_top = (-cos θ, -sin θ)`` that gives ``local_right = (-sin θ, cos θ)``.
    """
    t = math.radians(center_angle_deg)
    return (-math.sin(t), math.cos(t))


def place_profile_in_world(
    profile: Profile,
    center_xy: Tuple[float, float],
    center_angle_deg: float,
) -> Tuple[Tuple[float, float], ...]:
    """Transform a local-frame profile to world coordinates.

    The local ``+Y`` axis is rotated to align with the world inward vector
    (``local_top_vector_for_center_angle``); the result is translated so
    the local origin sits at ``center_xy``.
    """
    # Build the local→world rotation: local_x → local_right_world,
    # local_y → local_top_world.
    rx, ry = local_right_vector_for_center_angle(center_angle_deg)
    tx, ty = local_top_vector_for_center_angle(center_angle_deg)
    cx, cy = center_xy
    out: list[Tuple[float, float]] = []
    for x, y in profile.vertices:
        wx = cx + x * rx + y * tx
        wy = cy + x * ry + y * ty
        out.append((wx, wy))
    return tuple(out)
