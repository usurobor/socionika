"""Tests for CadQueryExecutor.

These tests are skipped when CadQuery isn't installed, except for the
import-laziness test which is always run.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import unittest

from socionics_medallion.compiler import compile_medallion
from socionics_medallion.executor import (
    CadQueryExecutor,
    NotYetImplemented,
)
from socionics_medallion.ir import (
    CutSymbol,
    EngravedDivider,
    LowerField,
    Prism,
    RaisedDivider,
    RaisedSymbol,
    SymbolKind,
)
from socionics_medallion.plan import build_plan


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cadquery_available() -> bool:
    return importlib.util.find_spec("cadquery") is not None


class TestExecutorLazyCadQueryImport(unittest.TestCase):
    """Importing socionics_medallion.executor must not load cadquery."""

    def test_module_level_import_does_not_load_cadquery(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; import socionics_medallion.executor; "
                "assert 'cadquery' not in sys.modules, sorted(sys.modules)",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )


class TestImplementedOpsDeclaration(unittest.TestCase):
    def test_implemented_ops_is_set(self) -> None:
        self.assertIsInstance(CadQueryExecutor.IMPLEMENTED_OPS, frozenset)

    def test_prism_is_implemented(self) -> None:
        self.assertIn(Prism, CadQueryExecutor.IMPLEMENTED_OPS)


@unittest.skipUnless(_cadquery_available(), "cadquery not installed")
class TestCadQueryExecutorWithCadQuery(unittest.TestCase):
    """Slow path: only runs in the CadQuery-enabled CI job."""

    def test_prism_smoke(self) -> None:
        op = Prism(
            center=(0.0, 0.0),
            inner_radius=0.0,
            outer_radius=10.0,
            start_angle_deg=0.0,
            end_angle_deg=45.0,
            z0=0.0,
            z1=2.5,
        )
        executor = CadQueryExecutor()
        result = executor.execute([op])
        self.assertIsNotNone(result.solid)

    def test_not_yet_implemented_for_other_ops(self) -> None:
        op = RaisedSymbol(
            symbol_kind=SymbolKind.TRIANGLE,
            center_angle_deg=90.0,
            center_radius=20.0,
            size_S=8.0,
            height=1.0,
            base_z=2.0,
        )
        executor = CadQueryExecutor()
        with self.assertRaises(NotYetImplemented):
            executor.execute([op])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
