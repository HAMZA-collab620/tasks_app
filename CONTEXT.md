# Dar Tasks

Lightweight, accessible local task and project management desktop application built with Python and wxPython.

## Language

### Core Domain

**Project**:
A named collection of tasks persisted as a UTF-8 text file on disk within the projects workspace directory managed via `pathlib.Path`.
_Avoid_: Workspace file, project folder, document.

**Task**:
A domain entity (`@dataclass`) encapsulating task text, completion state, and pinned status (`⭐`), strictly decoupled from raw string storage formatting.
_Avoid_: Todo, entry, record, note, raw string line.

### Architecture & Deep Modules

**ProjectWorkspace**:
The deep module managing physical project paths (`Path`), ordering (`.project_order.txt`), deletion, and workspace disk invariants using `pathlib.Path`.
_Avoid_: File manager, workspace helper, folder controller.

**ProjectModel**:
The deep module managing in-memory `Task` objects for a single active project, atomic disk persistence, undo history, and harvest archiving.
_Avoid_: Task manager, state container, model handler.

**SearchEngine**:
The query module providing a unified seam for querying tasks across a single project or the entire workspace.
_Avoid_: Search helper, searcher, filter logic.

**Localization (gettext)**:
The standard internationalization infrastructure (`gettext`) providing global string translation (`_`) via standard locale catalogs, replacing hardcoded dictionary lookups.
_Avoid_: Custom translator class, TRANSLATIONS dictionary.

**GUI Adapter**:
The lightweight presentation controls (`MainFrame`, `ProjectManagerDialog`, `GlobalSearchDialog`) in `tasks_app.py` and `dialogs.py` that connect user interactions to deep module seams.
_Avoid_: UI component, view model, service.
