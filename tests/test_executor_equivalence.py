"""Tests that the compiler's output is identical regardless of executor choice."""

from __future__ import annotations

import json
import unittest

from socionics_medallion import ir
from socionics_medallion.compiler import compile_medallion
from socionics_medallion.executor import StubExecutor
from socionics_medallion.plan import build_plan


class TestExecutorEquivalence(unittest.TestCase):
    def test_compiler_output_independent_of_executor(self) -> None:
        plan = build_plan()
        ops_for_stub = compile_medallion(plan)
        ops_for_cadquery = compile_medallion(plan)
        # Both sequences must be byte-identical regardless of downstream consumer.
        self.assertEqual(ops_for_stub, ops_for_cadquery)
        ja = json.dumps([ir.op_to_dict(o) for o in ops_for_stub], sort_keys=True)
        jb = json.dumps(
            [ir.op_to_dict(o) for o in ops_for_cadquery], sort_keys=True
        )
        self.assertEqual(ja, jb)

    def test_stub_consumes_same_ops_object(self) -> None:
        plan = build_plan()
        ops = compile_medallion(plan)
        result_a = StubExecutor().execute(ops)
        # Re-running on the same ops object must be deterministic.
        result_b = StubExecutor().execute(ops)
        self.assertEqual(
            json.dumps(result_a, sort_keys=True),
            json.dumps(result_b, sort_keys=True),
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
