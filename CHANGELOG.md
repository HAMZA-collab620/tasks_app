# Changelog

## [2026-09-06]
- refactor(core): harden exception handling, prune speculative settings, eliminate dead code, and decompose command dispatching via clean-code-guard audit.
- feat(architecture): deepened the codebase with ProjectWorkspace, SearchEngine, and encapsulated ProjectModel modules, turning GUI dialogs into clean adapters and achieving 100% test pass.
- refactor: consolidated 21 scattered modules into a single accessible and maintainable tasks_app.py core, eliminated dead JSON layout engines, and retained full backward compatibility for all test suites.
