# Dataclass Task Model and Pathlib Migration

## Context
Tasks and projects were previously handled as raw string primitives with manual prefix parsing (`⭐ `) and legacy `os.path` manipulations scattered throughout `ProjectModel` and `ProjectWorkspace`.

## Decision
We decided to adopt structured dataclasses (`Task`) and standard `pathlib.Path` APIs in `core_models.py`:
- `Task`: A domain entity encapsulating `title`, `is_pinned`, and `is_completed` with clean serialization to/from raw text file lines.
- `pathlib.Path`: Replaces all `os.path` and string path manipulations across workspace persistence and atomic file operations.

## Rationale & Trade-offs
Encapsulating task state in a dataclass eliminates fragile string slicing (`task[2:]`) and decouples the in-memory representation from on-disk persistence formatting. Adopting `pathlib.Path` aligns the core engine with modern Python standards and our explicit architecture policy without altering the user-facing disk format or breaking compatibility with existing user project files.
