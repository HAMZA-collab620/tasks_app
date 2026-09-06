# Changelog

## [2026-09-06]
- refactor(clean-code): remediate all 11 code review findings across core_models, dialogs, tasks_app, and run_tests; purify pathlib usage, unify archive/delete, and expand test coverage to 21 passing tests.
- refactor(architecture): decompose monolithic tasks_app into flat co-located deep modules (core_models.py, dialogs.py, tasks_app.py) with Task dataclass, pathlib, ADR records, and standard unittest suite.
- chore(cleanup): remove legacy dar_tasks facade package and transition to flat architecture.
- refactor(core): harden exception handling, prune speculative settings, eliminate dead code, and decompose command dispatching via clean-code-guard audit.
- feat(architecture): deepened the codebase with ProjectWorkspace, SearchEngine, and encapsulated ProjectModel modules, turning GUI dialogs into clean adapters and achieving 100% test pass.
- refactor: consolidated 21 scattered modules into a single accessible and maintainable tasks_app.py core, eliminated dead JSON layout engines, and retained full backward compatibility for all test suites.
