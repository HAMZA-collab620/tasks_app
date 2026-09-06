# Changelog

## [2026-09-06]
- build(exe): compile standalone single-file windowed executable via PyInstaller with bundled gettext locales and excluded unused modules.
- refactor(i18n-dispatch): adopt standard GNU gettext with locales catalog, decompose dispatch_command into focused handlers, decouple list_projects presentation leakage, purge dead reorder_project, and expand test suite to 37 passing tests.
- refactor(compression): radically compress codebase by ~390 lines across dialogs, tasks_app, and core_models, eliminate UI boilerplate, unify open_file_in_editor, pass black and flake8 with zero warnings, and maintain 100% test suite passage (34 tests).
- refactor(minimalist): purge pyperclip for native clipboard, resolve screen-reader pin focus displacement bug, introduce direct Notepad integration (F4), unify synchronous atomic persistence, and expand test suite to 34 passing tests.
- test(guard): harden test suite with test-guard rules, eliminate dummy settings mock, adopt scenario-based naming, isolate subtests, seal edge-case gaps, and expand to 29 passing tests.

- fix(sync-i18n): resolve project rename/delete notebook desynchronization, implement index task disambiguation, adopt gettext ADR-0006 internationalization, strip dead code, enhance keyboard accessibility, and add requirements.txt with 25 passing tests.
- refactor(clean-code): remediate all 11 code review findings across core_models, dialogs, tasks_app, and run_tests; purify pathlib usage, unify archive/delete, and expand test coverage to 21 passing tests.
- refactor(architecture): decompose monolithic tasks_app into flat co-located deep modules (core_models.py, dialogs.py, tasks_app.py) with Task dataclass, pathlib, ADR records, and standard unittest suite.
- chore(cleanup): remove legacy dar_tasks facade package and transition to flat architecture.
- refactor(core): harden exception handling, prune speculative settings, eliminate dead code, and decompose command dispatching via clean-code-guard audit.
- feat(architecture): deepened the codebase with ProjectWorkspace, SearchEngine, and encapsulated ProjectModel modules, turning GUI dialogs into clean adapters and achieving 100% test pass.
- refactor: consolidated 21 scattered modules into a single accessible and maintainable tasks_app.py core, eliminated dead JSON layout engines, and retained full backward compatibility for all test suites.
