"""The Repository contract the engine depends on (Constitution Principle VI).

The engine imports ONLY this abstract interface — never a concrete implementation.
Block 2 adds CSV/Supabase repositories behind this same signature without any change
to the engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.models import Transaction


class Repository(ABC):
    """Read-only source of transaction-level data."""

    @abstractmethod
    def get_transactions(self) -> list[Transaction]:
        """Return ALL transactions across all scenarios and periods.

        Each transaction is tagged with its scenario and period; the engine slices
        by scenario/period itself. Must be read-only and side-effect-free. The caller
        applies the canonical sort, so any stable order may be returned.
        """
        raise NotImplementedError
