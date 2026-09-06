# Direct Seam Facade Between Deep Domain Modules and GUI Adapters

## Context
We needed to define the communication pattern between the GUI adapters (`MainFrame`, `dialogs.py`) and the underlying domain entities (`ProjectModel`, `ProjectWorkspace`, `SearchEngine`). We evaluated event-driven PubSub and intermediate Presenter/Controller patterns against a direct deep module facade.

## Decision
We decided to adopt a Direct Seam Facade pattern:
- `ProjectModel` and `ProjectWorkspace` expose a concise, intention-revealing public interface for task operations (`add_task`, `archive_task`, `delete_task`, `toggle_pin`, `undo`, `move_task`) and project operations (`create_project`, `rename_project`, `delete_project`, `reorder_project`).
- GUI adapters call these methods directly and update their presentation controls (`wx.ListBox`, status bar) from the returned results.
- No intermediary controller layers or event bus abstractions are introduced.

## Rationale & Trade-offs
Direct facades provide maximum depth: substantial business logic (atomic file writes, undo tracking, archive formatting, prefix parsing) is encapsulated behind a minimal, highly testable interface. Introducing a Controller or PubSub architecture would add shallow pass-through boilerplate, failing the Deletion Test and violating KISS principles without providing architectural value for a local desktop tool.
