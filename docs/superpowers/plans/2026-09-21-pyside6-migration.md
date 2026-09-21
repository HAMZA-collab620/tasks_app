# Dar Tasks - PySide6 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the desktop task manager Dar Tasks presentation layer from `wxPython` to `PySide6` (Qt 6) with first-class NVDA screen-reader accessibility, single-instance activation via `QLocalServer`, and external Notepad synchronization, while strictly adhering to `clean-code-guard` imperatives.

**Architecture:** In-place replacement of presentation adapters (`tasks_app.py`, `dialogs.py`) connecting directly to the untouched domain engine (`core_models.py`). User controls map to native Qt 6 widgets with explicit accessible properties, mnemonics, and window-level shortcuts.

**Tech Stack:** Python 3.12+, PySide6 6.11.2+, send2trash, unittest (headless offscreen Qt).

**Spec:** [2026-09-21-pyside6-migration-design.md](file:///e:/GitHub/my%20workflows/apps/tasks_app/docs/superpowers/specs/2026-09-21-pyside6-migration-design.md)

## Global Constraints

- Domain logic in `core_models.py` must remain 100% intact and untouched.
- Clean Code Imperative: Every function must not exceed 20 lines (target <= 20 LoC, single responsibility).
- Clean Code Imperative: Maximum 4 parameters per function/method.
- Clean Code Imperative: Specific exceptions only; zero broad catch-all error swallowing.
- Clean Code Imperative: Intent-revealing names; ban `data`, `item`, `temp`, `obj`, `value` without qualification.
- Accessibility: Every interactive control must have `setAccessibleName()` with gettext `_()` translations and logical tab ordering.
- Zero `wx` imports across all Python source files upon completion.
- All existing 37 unit tests in `run_tests.py` must continue passing 100%.

---

### Task 1: Update Dependencies (`requirements.txt`)

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: Nothing
- Produces: Clean dependency specification referencing `PySide6` instead of `wxPython`.

- [ ] **Step 1: Write updated requirements.txt**
Update `requirements.txt` to:
```text
PySide6>=6.5.0
send2trash>=1.8.0
```

- [ ] **Step 2: Verify PySide6 environment availability**
Run: `python -c "import PySide6; from PySide6 import QtWidgets, QtCore, QtGui; print('PySide6 is ready')"`
Expected: Output `PySide6 is ready` with returncode 0.

- [ ] **Step 3: Commit**
```bash
git add requirements.txt
git commit -m "chore: update dependencies from wxPython to PySide6"
```

---

### Task 2: Implement Modal Dialogs in PySide6 (`dialogs.py`)

**Files:**
- Modify: `dialogs.py`
- Test: `run_tests.py`

**Interfaces:**
- Consumes: `core_models.py` (`ProjectWorkspace`, `SearchEngine`, `SettingsManager`, `Translator`, `get_project_display_name`, `open_file_in_editor`).
- Produces:
  - `GlobalSearchDialog(parent, search_engine, settings)`: Modal search query adapter.
  - `ProjectManagerDialog(parent, workspace)`: Modal project order, pinning, and deletion manager.
  - `SettingsDialog(parent, settings_manager)`: Modal application configuration editor.

- [ ] **Step 1: Write unit test for dialogs in offscreen mode**
Add test case in `run_tests.py` verifying dialog instantiation and accessible names:
```python
class TestPySide6Dialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_settings_dialog_instantiation(self):
        from dialogs import SettingsDialog
        from core_models import SettingsManager
        with tempfile.TemporaryDirectory() as tmp:
            mgr = SettingsManager(Path(tmp))
            dlg = SettingsDialog(None, mgr)
            self.assertIsNotNone(dlg)
            self.assertTrue(len(dlg.accessibleName()) > 0)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python run_tests.py`
Expected: FAIL due to wx import in `dialogs.py`.

- [ ] **Step 3: Implement PySide6 dialogs in `dialogs.py`**
Implement `GlobalSearchDialog`, `ProjectManagerDialog`, and `SettingsDialog` with:
- `QDialog` base class.
- Explicit `setAccessibleName()` on all fields and buttons.
- Labels with mnemonics (`&`) linked via `setBuddy()`.
- Layouts using `QVBoxLayout` and `QHBoxLayout`.
- Functions strictly under 20 lines.

- [ ] **Step 4: Run test to verify it passes**
Run: `python run_tests.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add dialogs.py run_tests.py
git commit -m "feat(dialogs): migrate presentation dialogs to PySide6 with full accessibility"
```

---

### Task 3: Implement Main Application in PySide6 (`tasks_app.py`)

**Files:**
- Modify: `tasks_app.py`
- Test: `run_tests.py`

**Interfaces:**
- Consumes: `core_models.py`, `dialogs.py`.
- Produces:
  - `copy_to_clipboard(text: str) -> bool`: Clipboard utility using `QGuiApplication.clipboard()`.
  - `TaskProjectWidget(QWidget)`: Project tab presenter with filter, task list, add task input, auto-save timer, and context menu.
  - `MainWindow(QMainWindow)`: Root frame hosting `QTabWidget`, toolbar buttons with mnemonics, global `QShortcut`s, and `QLocalServer` activation.

- [ ] **Step 1: Write unit test for MainWindow in offscreen mode**
Add test case in `run_tests.py`:
```python
class TestPySide6MainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_main_window_instantiation(self):
        from tasks_app import MainWindow
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertGreater(win.notebook.count(), 0)
        win.close()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python run_tests.py`
Expected: FAIL due to wx imports in `tasks_app.py`.

- [ ] **Step 3: Implement PySide6 `tasks_app.py`**
Implement `copy_to_clipboard`, `TaskProjectWidget`, and `MainWindow`:
- Replace `wx.ListBox` with `QListWidget`.
- Replace `wx.TextCtrl` with `QLineEdit`.
- Replace `wx.Notebook` with `QTabWidget`.
- Replace `wx.Timer` with `QTimer`.
- Setup window-level shortcuts with `QShortcut` (`Ctrl+Up/Down`, `Del`, `F2`, `Ctrl+Z`, `Ctrl+M`, `Ctrl+C`, `Ctrl+F`, `F4`, `Ctrl+Tab`, `Ctrl+1..9`).
- Setup single instance via `QLocalServer` / `QLocalSocket`.
- Handle `ActivationChange` in `changeEvent` for Notepad `st_mtime` sync and daily rollover.
- Enforce function length <= 20 lines throughout.

- [ ] **Step 4: Run test to verify it passes**
Run: `python run_tests.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add tasks_app.py run_tests.py
git commit -m "feat(app): migrate main window and task project panel to PySide6"
```

---

### Task 4: Expand Headless Integration and Clean-Code Guard Verification (`run_tests.py`)

**Files:**
- Modify: `run_tests.py`

**Interfaces:**
- Consumes: `core_models.py`, `dialogs.py`, `tasks_app.py`.
- Produces: Complete automated test suite verifying 100% of domain rules, zero wx references, and GUI widget event handling.

- [ ] **Step 1: Add comprehensive GUI headless tests**
Add test methods for:
- Task list selection and command dispatch (`complete`, `pin`, `delete`, `undo`).
- Project tab switching and shortcut mapping.
- Zero `wx` import static assertion across all `.py` files in `apps/tasks_app`.
- Function length verification test asserting no function in `tasks_app.py` or `dialogs.py` exceeds 20 lines.

- [ ] **Step 2: Run test suite**
Run: `python run_tests.py`
Expected: All tests (37 original domain tests + GUI integration tests) PASS in < 1.5 seconds.

- [ ] **Step 3: Commit**
```bash
git add run_tests.py
git commit -m "test: add PySide6 headless integration tests and clean code guards"
```

---

### Task 5: Update PyInstaller Specification (`tasks_app.spec`)

**Files:**
- Modify: `tasks_app.spec`

**Interfaces:**
- Consumes: `tasks_app.py`, `locales/`.
- Produces: Optimized standalone executable build configuration excluding unused Qt modules.

- [ ] **Step 1: Edit tasks_app.spec**
Configure `Analysis` with:
```python
excludes = [
    'tkinter', 'unittest', 'pydoc', 'sqlite3',
    'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick',
    'PySide6.QtPdf', 'PySide6.QtOpenGL', 'PySide6.QtTest',
    'PySide6.QtSpatialAudio'
]
datas = [('locales', 'locales')]
```

- [ ] **Step 2: Verify spec file syntax**
Run: `python -c "import ast; ast.parse(open('tasks_app.spec', encoding='utf-8').read()); print('tasks_app.spec syntax OK')"`
Expected: Output `tasks_app.spec syntax OK`.

- [ ] **Step 3: Commit**
```bash
git add tasks_app.spec
git commit -m "build: update PyInstaller spec for PySide6 standalone packaging"
```

---

### Task 6: Documentation and Project State Update

**Files:**
- Modify: `README.md`
- Modify: `project_state.md`
- Modify: `CHANGELOG.md`
- Modify: `task.md`

**Interfaces:**
- Consumes: Completed migration changes.
- Produces: Updated documentation reflecting PySide6 architecture, developer info, and clean git history.

- [ ] **Step 1: Update README.md and project_state.md**
Reflect PySide6, accessibility features, QLocalServer single instance, keyboard shortcuts, and clean code guard metrics.

- [ ] **Step 2: Update CHANGELOG.md and task.md**
Add dated entry for PySide6 migration.

- [ ] **Step 3: Commit**
```bash
git add README.md project_state.md CHANGELOG.md task.md
git commit -m "docs: document PySide6 migration and clean code guard verification"
```
