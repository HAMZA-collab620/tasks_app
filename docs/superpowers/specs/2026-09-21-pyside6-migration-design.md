# Dar Tasks - PySide6 Migration Design Specification

- **Date:** 2026-09-21
- **Status:** Approved (Brainstorming Complete)
- **Target Application:** `apps/tasks_app` (Dar Tasks)
- **Author:** Nafie & Kamal Yaser

---

## 1. Context & Motivation

Dar Tasks is a lightweight, accessible desktop application for managing tasks and projects locally using plain UTF-8 text files. Its domain model and storage persistence are strictly separated in `core_models.py` and guarded by a comprehensive suite of 37 headless unit tests.

The legacy presentation layer was constructed with `wxPython`. This specification defines the complete in-place architectural migration of the presentation layer to **PySide6 (Qt 6)**, providing:
1. First-class NVDA and screen-reader accessibility via standard Qt Win32 accessible interfaces.
2. Robust single-instance management with window raise-and-activate via `QLocalServer`/`QLocalSocket`.
3. Native responsive UI widgets without intermediate visual artifacts.
4. Clean code invariants with a strict <= 20 lines per function policy.
5. Zero regressions in domain persistence, search, backups, daily rollover, or external Notepad synchronization.

---

## 2. Core Architectural Decisions

### 2.1 In-Place Migration Strategy
- **Decision:** Replace `wxPython` directly across `tasks_app.py`, `dialogs.py`, `requirements.txt`, and `tasks_app.spec`.
- **Rationale:** Avoids repository clutter, keeps the directory structure strictly flat, and eliminates transitional dead code. The domain logic in `core_models.py` requires zero changes.

### 2.2 Single-Instance & Foreground Activation
- **Decision:** Use `QLocalServer` and `QLocalSocket` keyed to the user environment: `f"DarTasksSingleInstance-{getpass.getuser()}"`.
- **Behavior:**
  - Upon startup, a client `QLocalSocket` attempts to connect to the named server.
  - If a connection succeeds, an activation token is sent (`b"ACTIVATE"`), and the second instance exits cleanly (`sys.exit(0)`).
  - The running primary instance receives `newConnection`, reads the token, and brings `MainWindow` to the foreground via:
    ```python
    self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
    self.showNormal()
    self.raise_()
    self.activateWindow()
    ```
  - If connection fails, the process removes any stale socket file and starts `QLocalServer.listen()`.

### 2.3 External Notepad Synchronization (`st_mtime`)
- **Decision:** Intercept `QEvent.Type.ActivationChange` in `MainWindow.changeEvent(event)`.
- **Behavior:**
  - When `self.isActiveWindow()` becomes true:
    1. Call `backup_mgr.check_and_rollover_daily_tasks()`.
    2. Iterate over all open project tabs in `QTabWidget` and invoke `page.model.reload_if_modified()`.
    3. If modified externally by Notepad, refresh `QListWidget` while preserving the filter query and item selection.
  - The `F4` shortcut opens the active project file directly via `open_file_in_editor(page.filename)`.

### 2.4 Screen Reader Accessibility (NVDA / WCAG 2.1 AA)
- **Decision:** Explicit accessible properties and deterministic navigation on every widget:
  - `setAccessibleName(self.translator._(...))` on every input, list, button, spin box, and combo box.
  - `setAccessibleDescription(...)` for contextual hints where appropriate.
  - Keyboard Mnemonics: Labels configured with `&` and linked via `label.setBuddy(target_widget)`.
  - Deterministic `QWidget.setTabOrder(...)` across all panels and dialogs.
  - Selection stability: Item deletions and archives automatically adjust the selection index to prevent focus loss.

---

## 3. Component Architecture & Widget Mapping

### 3.1 Domain Model (`core_models.py`)
- **Status:** Unmodified (100% preserved).
- Houses `Task`, `ProjectModel`, `ProjectWorkspace`, `SearchEngine`, `SettingsManager`, `BackupManager`, `Translator`, and `open_file_in_editor`.

### 3.2 Presentation Layer (`tasks_app.py`)
- **Focal Classes:**
  1. `MainWindow(QMainWindow)`:
     - Hosts toolbar (`QPushButton`s with mnemonics: Projects `Alt+P`, Search `Alt+S`, Notepad `Alt+N`, Harvest `Alt+H`, Archive `Alt+O`, Settings `Alt+T`).
     - Hosts central `QTabWidget` managing project tabs.
     - Houses global `QShortcut` bindings (`Ctrl+Up`, `Ctrl+Down`, `Del`, `F2`, `Ctrl+Z`, `Ctrl+M`, `Ctrl+Tab`, `Ctrl+C`, `Ctrl+F`, `F4`, `Ctrl+1..9`).
     - Handles `closeEvent` to ensure atomic saves across all modified tabs.
  2. `TaskProjectWidget(QWidget)` (replaces `TaskProjectPanel`):
     - Filter row: `QLabel` (`&Filter`) + `QLineEdit` (`search_input`).
     - Tasks row: `QLabel` (`&Tasks`) + `QListWidget` (`task_list`).
     - Add task row: `QLabel` (`&Add`) + `QLineEdit` (`new_task_input`).
     - Auto-save: `QTimer` invoking `model.save_tasks_atomic()` every `interval` seconds when dirty.
     - Context Menu: `customContextMenuRequested` showing Complete, Pin, Edit, Copy, Delete, Notepad.
     - Clipboard: Native `QGuiApplication.clipboard().setText()`.

### 3.3 Modal Dialogs (`dialogs.py`)
- **Focal Classes:**
  1. `GlobalSearchDialog(QDialog)`:
     - `QLineEdit` for real-time search queries (length >= 2).
     - `QListWidget` for results with Enter / double-click navigation to tab.
     - Direct "Open in Notepad" button.
  2. `ProjectManagerDialog(QDialog)`:
     - `QListWidget` displaying pinned `⭐` status and `(daily)` suffix.
     - Action buttons: New (`QInputDialog.getText`), Open, Pin, Move Up, Move Down, Rename (`QInputDialog.getText`), Notepad, Delete (`QMessageBox.question`), Close.
     - Parent notifications on rename/deletion to update open tabs.
  3. `SettingsDialog(QDialog)`:
     - `QCheckBox` for `confirm_on_archive` and `confirm_on_delete`.
     - `QSpinBox` for `auto_save_interval` (1-60s).
     - `QComboBox` for language selection (`English`, `العربية`).
     - Buttons: Reset Defaults (with confirmation), Save, Cancel.

---

## 4. Dependencies & Packaging

### 4.1 Requirements (`requirements.txt`)
```text
PySide6>=6.5.0
send2trash>=1.8.0
```

### 4.2 PyInstaller Specification (`tasks_app.spec`)
- Target: `tasks_app.py`.
- Datas: `[('locales', 'locales')]`.
- Excludes:
  - Standard libraries: `['tkinter', 'unittest', 'pydoc', 'sqlite3']`.
  - Unused Qt modules: `['PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf', 'PySide6.QtOpenGL', 'PySide6.QtTest', 'PySide6.QtSpatialAudio']`.
- Options: `console=False`, `upx=True`, standalone single executable.

---

## 5. Quality Assurance & Verification Plan

1. **Unit Test Continuity:**
   - Execute `python run_tests.py`.
   - Ensure all 37 domain tests pass with zero errors.
2. **GUI Smoke & Integration Tests:**
   - Add headless PySide6 smoke tests using `pytest` or `unittest` with `os.environ["QT_QPA_PLATFORM"] = "offscreen"`.
   - Verify `MainWindow`, `GlobalSearchDialog`, `ProjectManagerDialog`, and `SettingsDialog` instantiate cleanly.
3. **Clean Code Verification:**
   - Function length audit: No function exceeding 20 lines.
   - Zero occurrences of `import wx` across all Python source files.
4. **Manual & Screen Reader Verification:**
   - Verify keyboard shortcuts (`Ctrl+M`, `Del`, `F2`, `F4`, `Ctrl+Z`, `Ctrl+Tab`, `Ctrl+1..9`).
   - Verify external file edits in Notepad trigger automatic reload upon Dar Tasks window activation.
   - Verify second instance launch smoothly raises existing window without error dialog.
