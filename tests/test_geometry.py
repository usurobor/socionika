"""Tests for socionics_medallion.geometry — pure 2D symbol profiles.

These tests enumerate the operator's AC4 acceptance list (2026-05-21).
"""

from __future__ import annotations

import math
import os
import subprocess
import unittest

from socionics_medallion.geometry import (
    Profile,
    circle_profile,
    ethics_profile,
    local_right_vector_for_center_angle,
    local_top_vector_for_center_angle,
    square_profile,
    triangle_profile,
)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _polygon_area(vertices: tuple[tuple[float, float], ...]) -> float:
    """Signed area via shoelace; absolute value gives the polygon's area."""
    n = len(vertices)
    s = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def _bbox(vertices: tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    return (min(xs), min(ys), max(xs), max(ys))


class TestGeometryImportPurity(unittest.TestCase):
    def test_no_cadquery_after_import(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.geometry; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


# ---------------------------------------------------------------------------
# Square profile (AC4).
# ---------------------------------------------------------------------------
class TestSquareProfile(unittest.TestCase):
    def setUp(self) -> None:
        self.S = 6.0
        self.profile = square_profile(self.S)

    def test_returns_profile(self) -> None:
        self.assertIsInstance(self.profile, Profile)

    def test_bounding_box_width(self) -> None:
        xmin, _, xmax, _ = _bbox(self.profile.vertices)
        self.assertAlmostEqual(xmax - xmin, self.S, places=9)

    def test_bounding_box_height(self) -> None:
        _, ymin, _, ymax = _bbox(self.profile.vertices)
        self.assertAlmostEqual(ymax - ymin, self.S, places=9)

    def test_area_equals_S_squared(self) -> None:
        area = _polygon_area(self.profile.vertices)
        self.assertAlmostEqual(area, self.S * self.S, places=6)

    def test_centered_at_origin(self) -> None:
        xmin, ymin, xmax, ymax = _bbox(self.profile.vertices)
        self.assertAlmostEqual((xmin + xmax) / 2.0, 0.0, places=9)
        self.assertAlmostEqual((ymin + ymax) / 2.0, 0.0, places=9)


# ---------------------------------------------------------------------------
# Circle profile (AC4).
# ---------------------------------------------------------------------------
class TestCircleProfile(unittest.TestCase):
    def setUp(self) -> None:
        self.S = 6.0
        self.profile = circle_profile(self.S, segments=256)

    def test_returns_profile(self) -> None:
        self.assertIsInstance(self.profile, Profile)

    def test_inscribed_in_S_box(self) -> None:
        xmin, ymin, xmax, ymax = _bbox(self.profile.vertices)
        self.assertAlmostEqual(xmax - xmin, self.S, places=3)
        self.assertAlmostEqual(ymax - ymin, self.S, places=3)

    def test_every_vertex_radius_is_half_S(self) -> None:
        r = self.S / 2.0
        for x, y in self.profile.vertices:
            d = math.hypot(x, y)
            self.assertAlmostEqual(d, r, places=6)

    def test_diameter_equals_S(self) -> None:
        xmin, _, xmax, _ = _bbox(self.profile.vertices)
        self.assertAlmostEqual(xmax - xmin, self.S, places=3)


# ---------------------------------------------------------------------------
# Triangle profile (AC4).
# ---------------------------------------------------------------------------
class TestTriangleProfile(unittest.TestCase):
    def setUp(self) -> None:
        self.S = 6.0
        self.profile = triangle_profile(self.S)

    def test_returns_profile(self) -> None:
        self.assertIsInstance(self.profile, Profile)

    def test_three_vertices(self) -> None:
        self.assertEqual(len(self.profile.vertices), 3)

    def test_every_vertex_radius_is_half_S(self) -> None:
        r = self.S / 2.0
        for x, y in self.profile.vertices:
            d = math.hypot(x, y)
            self.assertAlmostEqual(d, r, places=9)

    def test_circumradius_is_half_S(self) -> None:
        radii = [math.hypot(x, y) for x, y in self.profile.vertices]
        self.assertAlmostEqual(max(radii), self.S / 2.0, places=9)

    def test_apex_aligned_with_local_top(self) -> None:
        # Apex is the vertex with the maximum y-coordinate; that vertex should
        # lie on the positive y-axis (local +Y = local top).
        apex = max(self.profile.vertices, key=lambda v: v[1])
        self.assertAlmostEqual(apex[0], 0.0, places=9)
        self.assertGreater(apex[1], 0.0)


# ---------------------------------------------------------------------------
# Ethics profile (AC4) — exact 3/4 square (upper-right quadrant removed).
# ---------------------------------------------------------------------------
class TestEthicsProfile(unittest.TestCase):
    def setUp(self) -> None:
        self.S = 6.0
        self.profile = ethics_profile(self.S)

    def test_returns_profile(self) -> None:
        self.assertIsInstance(self.profile, Profile)

    def test_bounding_box_dimensions(self) -> None:
        xmin, ymin, xmax, ymax = _bbox(self.profile.vertices)
        self.assertAlmostEqual(xmax - xmin, self.S, places=9)
        self.assertAlmostEqual(ymax - ymin, self.S, places=9)

    def test_area_is_three_quarter_S_squared(self) -> None:
        area = _polygon_area(self.profile.vertices)
        self.assertAlmostEqual(area, 0.75 * self.S * self.S, places=6)

    def test_upper_right_quadrant_is_removed(self) -> None:
        # The point (S/4, S/4) sits firmly inside the upper-right quadrant
        # of the symbol's bounding box (whose center is the origin). After
        # removing the upper-right quadrant, that point must be OUTSIDE the
        # ethics polygon.
        self.assertFalse(_point_in_polygon((self.S / 4.0, self.S / 4.0), self.profile.vertices))
        # A point in the lower-left quadrant MUST be inside.
        self.assertTrue(_point_in_polygon((-self.S / 4.0, -self.S / 4.0), self.profile.vertices))

    def test_centered_bounding_box(self) -> None:
        xmin, ymin, xmax, ymax = _bbox(self.profile.vertices)
        self.assertAlmostEqual((xmin + xmax) / 2.0, 0.0, places=9)
        self.assertAlmostEqual((ymin + ymax) / 2.0, 0.0, places=9)


def _point_in_polygon(p: tuple[float, float], vertices: tuple[tuple[float, float], ...]) -> bool:
    """Standard ray-casting point-in-polygon test."""
    x, y = p
    inside = False
    n = len(vertices)
    j = n - 1
    for i in range(n):
        xi, yi = vertices[i]
        xj, yj = vertices[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
        ):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Orientation vectors (AC5).
# ---------------------------------------------------------------------------
class TestOrientationVectors(unittest.TestCase):
    def test_top_vector_points_to_center_at_12_oclock(self) -> None:
        v = local_top_vector_for_center_angle(90.0)
        # A cell at 12:00 sits at (0, +r); its top should point to (0, -1)
        # in world coordinates.
        self.assertAlmostEqual(v[0], 0.0, places=9)
        self.assertAlmostEqual(v[1], -1.0, places=9)

    def test_top_vector_points_to_center_at_3_oclock(self) -> None:
        v = local_top_vector_for_center_angle(0.0)
        self.assertAlmostEqual(v[0], -1.0, places=9)
        self.assertAlmostEqual(v[1], 0.0, places=9)

    def test_top_vector_is_unit(self) -> None:
        for angle in (0.0, 30.0, 60.0, 90.0, -45.0, 180.0):
            v = local_top_vector_for_center_angle(angle)
            self.assertAlmostEqual(math.hypot(v[0], v[1]), 1.0, places=9)

    def test_right_vector_perpendicular_to_top(self) -> None:
        for angle in (0.0, 30.0, 60.0, 90.0, -45.0, 180.0):
            t = local_top_vector_for_center_angle(angle)
            r = local_right_vector_for_center_angle(angle)
            dot = t[0] * r[0] + t[1] * r[1]
            self.assertAlmostEqual(dot, 0.0, places=9)

    def test_right_handed_frame(self) -> None:
        """Rotating local_right by +90° (CCW) must equal local_top.

        For (rx, ry) rotated +90° → (-ry, rx). Assert that equals (tx, ty).
        """
        for angle in (0.0, 30.0, 60.0, 90.0, -45.0, 180.0):
            t = local_top_vector_for_center_angle(angle)
            r = local_right_vector_for_center_angle(angle)
            rotated_right = (-r[1], r[0])
            self.assertAlmostEqual(rotated_right[0], t[0], places=9)
            self.assertAlmostEqual(rotated_right[1], t[1], places=9)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
