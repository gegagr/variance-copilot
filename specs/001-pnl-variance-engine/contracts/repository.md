# Contract: Repository interface

The engine depends only on this abstract interface (Principle VI — Source-Agnostic Data).
Block 1 ships exactly one implementation, `FixtureRepository`. Block 2 adds CSV and
Supabase implementations behind the **same** signature; the engine must not change.

## Interface

```python
# data/repository.py
from abc import ABC, abstractmethod
from engine.models import Transaction

class Repository(ABC):
    """Read-only source of transaction-level data for the engine."""

    @abstractmethod
    def get_transactions(self) -> list[Transaction]:
        """Return ALL transactions across all scenarios and periods.

        Contract guarantees:
        - Every returned object is a validated `Transaction`.
        - Each transaction is tagged with `scenario` (prior_year|current_year|budget)
          and `period` (1..12). The engine slices by scenario/period itself.
        - The method is read-only and side-effect-free.
        - Determinism: the caller (engine) applies the canonical sort, so the repository
          MAY return any order, but MUST return a stable set for identical sources.
        - No network or external dependency is permitted in Block 1.
        """
        ...
```

## FixtureRepository (Block 1 implementation)

```python
# data/fixture_repository.py
class FixtureRepository(Repository):
    def __init__(self, sample_dir: Path): ...
    def get_transactions(self) -> list[Transaction]:
        # Reads sample/transactions_prior_year.csv,
        #       sample/transactions_current_year.csv,
        #       sample/transactions_budget.csv
        # Parses amounts to Decimal, validates each row into Transaction, returns the union.
```

## Rules

- The engine NEVER imports `FixtureRepository` or any concrete repo — only the `Repository`
  ABC type, and only at the shell boundary (`shell/pipeline.py` wires the concrete repo).
- The repository returns **domain models, not DataFrames** — backends with very different
  shapes (CSV, Supabase) must satisfy one stable contract.
- Adding a backend in Block 2 means subclassing `Repository`; no engine change is allowed.

## Contract tests (Block 1)

- `FixtureRepository.get_transactions()` returns only valid `Transaction` objects.
- Calling it twice yields the same set (stable source).
- The engine, given a `Repository` test double returning a fixed list, produces the
  expected `PnLResult` — proving the engine depends on the ABC, not the impl.
