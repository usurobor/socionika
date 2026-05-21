"""Tests for StubExecutor and the CLI's stub path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from socionics_medallion.compiler import compile_medallion
from socionics_medallion.executor import StubExecutor
from socionics_medallion.plan import build_plan


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestStubExecutorBasic(unittest.TestCase):
    def test_stub_does_not_require_cadquery(self) -> None:
        # Run in subprocess to keep sys.modules clean.
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; "
                "from socionics_medallion.executor import StubExecutor; "
                "from socionics_medallion.compiler import compile_medallion; "
                "from socionics_medallion.plan import build_plan; "
                "StubExecutor().execute(compile_medallion(build_plan())); "
                "assert 'cadquery' not in sys.modules",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, msg=result.stdout + "\n" + result.stderr
        )

    def test_stub_emits_dict_with_counts(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        result = StubExecutor().execute(ops)
        self.assertIn("counts", result)
        self.assertEqual(result["counts"]["Prism"], 24)
        self.assertEqual(result["counts"]["LowerField"], 12)
        self.assertEqual(result["counts"]["RaisedSymbol"], 12)
        self.assertEqual(result["counts"]["CutSymbol"], 12)

    def test_stub_emits_full_op_stream(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        result = StubExecutor().execute(ops)
        self.assertEqual(len(result["ops"]), len(ops))


class TestStubExecutorDeterminism(unittest.TestCase):
    def test_two_executions_match(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        a = StubExecutor().execute(ops)
        b = StubExecutor().execute(ops)
        self.assertEqual(
            json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
        )


class TestCLIStubPath(unittest.TestCase):
    def test_cli_compile_stub_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "stream.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socionics_medallion.cli",
                    "compile",
                    "--plan",
                    "canonical",
                    "--executor",
                    "stub",
                    "--out",
                    out_path,
                ],
                cwd=_repo_root(),
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode, 0, msg=result.stdout + "\n" + result.stderr
            )
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIn("ops", payload)
            self.assertIn("counts", payload)
            self.assertEqual(payload["counts"]["Prism"], 24)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
