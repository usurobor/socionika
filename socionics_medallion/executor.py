"""Executor protocol + StubExecutor (CadQuery-free) + CadQueryExecutor.

CadQuery may only be imported lazily inside CadQueryExecutor methods.
A module-level `import cadquery` is forbidden and verified by tests.
"""

from __future__ import annotations


class NotYetImplemented(Exception):
    """Raised by CadQueryExecutor for ops not in IMPLEMENTED_OPS."""


class StubExecutor:  # pragma: no cover - stub for Phase 1
    def execute(self, ops):
        raise NotImplementedError("StubExecutor not yet implemented")


class CadQueryExecutor:  # pragma: no cover - stub for Phase 1
    IMPLEMENTED_OPS: frozenset = frozenset()

    def execute(self, ops):
        raise NotImplementedError("CadQueryExecutor not yet implemented")
