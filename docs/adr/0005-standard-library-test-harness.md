# Standard Library Test Harness (`run_tests.py`) for Regression-Free Refactoring

## Context
The repository contained no automated tests verifying workspace persistence, atomic file operations, task status handling, undo operations, or search engine queries. Refactoring the 1270-line monolithic script risked introducing silent behavioral regressions.

## Decision
We decided to implement a targeted test harness using only Python's standard library (`unittest`), located at the root in `run_tests.py`:
- The test suite executes against isolated temporary directories (`tempfile.TemporaryDirectory`).
- Tests cover core domain operations (project creation, task pinning, atomic saves, undo stack, search indexing, and order invariants).
- Tests must pass against the baseline monolith before any file extraction, and continue to pass after modularization into `core_models.py`.

## Rationale & Trade-offs
A self-contained `run_tests.py` using the standard library complies strictly with the project policy forbidding heavy external test frameworks (like pytest). It establishes an objective regression safety net, enabling fearless refactoring while guaranteeing 100% functional preservation without adding runtime dependencies.
