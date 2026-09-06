# Flat Co-located Modular Architecture

## Context
Following the decision to modularize `tasks_app.py` within Python, we evaluated whether to construct hierarchical package directories (`core/`, `ui/`) or organize modules as flat, co-located sibling files directly in the repository root.

## Decision
We decided to adopt a flat, co-located modular architecture in the repository root:
- `core_models.py`: Pure Python business logic, task models, workspace persistence invariants, and search engine (strictly independent of `wxPython`).
- `dialogs.py`: Auxiliary GUI presentation dialogs (`ProjectManagerDialog`, `GlobalSearchDialog`).
- `tasks_app.py`: Main window frame (`MainFrame`), application bootstrap, keyboard accelerators, and system integration.

## Rationale & Trade-offs
A flat structure eliminates import path friction and aligns with the project policy favoring flat layouts and avoiding deep directory nesting. Placing `core_models.py` directly in the root with zero GUI imports ensures strict domain isolation and allows headless unit testing, while maintaining a single, flat distribution layout for simple PyInstaller builds.
