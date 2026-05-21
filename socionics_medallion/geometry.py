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

This is a Phase-1 stub: the public functions raise :class:`NotImplementedError`
so the failing tests can drive Phase-2 implementation.
"""

from __future__ import annotations

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


def square_profile(S: float) -> Profile:  # noqa: N803 — operator naming
    """Return the canonical square profile (``S × S``, centered at origin)."""
    raise NotImplementedError("square_profile is not implemented yet")


def circle_profile(S: float, segments: int = 64) -> Profile:  # noqa: N803
    """Return a polygonal approximation of the canonical circle profile.

    The circle is inscribed in the same ``S × S`` bounding box as
    :func:`square_profile`. ``segments`` controls the polygonal resolution.
    """
    raise NotImplementedError("circle_profile is not implemented yet")


def triangle_profile(S: float) -> Profile:  # noqa: N803
    """Return the canonical equilateral triangle profile.

    Every vertex is at distance ``S / 2`` from the origin (circumradius);
    the apex aligns with local ``+Y`` (``local_top_vector``).
    """
    raise NotImplementedError("triangle_profile is not implemented yet")


def ethics_profile(S: float) -> Profile:  # noqa: N803
    """Return the canonical "ethics" profile — an exact 3/4 square.

    The bounding box is ``S × S``; the upper-right local quadrant is removed,
    leaving an L-shape that is an exact 3/4 of the corresponding square.
    """
    raise NotImplementedError("ethics_profile is not implemented yet")


def local_top_vector_for_center_angle(center_angle_deg: float) -> Tuple[float, float]:
    """Unit vector pointing from the symbol's cell-center toward the medallion center.

    The symbol's cell sits at world angle ``center_angle_deg`` on a positive
    radius. The vector from that cell back to the medallion's origin points
    along ``-r̂``; in Cartesian terms that is ``(-cos(θ), -sin(θ))``.
    """
    raise NotImplementedError("local_top_vector_for_center_angle is not implemented yet")


def local_right_vector_for_center_angle(center_angle_deg: float) -> Tuple[float, float]:
    """Unit vector perpendicular to :func:`local_top_vector_for_center_angle`.

    Right-handed: rotating ``local_right`` by +90° (CCW) gives ``local_top``.
    Equivalently, ``local_right = (sin(θ), -cos(θ))`` — the negative of the
    angular (CCW) direction at angle ``θ``.

    Wait — for the right-handed convention where ``+90° CCW`` on
    ``local_right`` produces ``local_top``, and ``local_top = (-cos(θ),
    -sin(θ))``, we need ``local_right = (-sin(θ), cos(θ))``. The
    implementation will validate this against the AC4 orientation tests.
    """
    raise NotImplementedError("local_right_vector_for_center_angle is not implemented yet")
