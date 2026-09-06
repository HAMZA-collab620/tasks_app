"""
Dar Tasks - Headless Core Domain Layer.
Encapsulates domain entities, persistence invariants, search, settings, and backup rotation.
Strictly decoupled from wxPython and any GUI presentation frameworks.
"""

from dataclasses import dataclass
import copy
import datetime
import gettext
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

try:
    import send2trash
except ImportError:
    send2trash = None

# ==========================================
# Domain Constants & Translations
# ==========================================
DEFAULT_ARCHIVE_NAME = "أرشيف_المهام.txt"
DEFAULT_TRASH_NAME = "trash.txt"
DAILY_FILENAME = "daily.txt"
DAILY_TEMPLATE_FILENAME = "daily_template.txt"
DAILY_ARCHIVE_NAME = "أرشيف_المهام_اليومية.txt"
PROJECT_ORDER_FILENAME = ".project_order.txt"

ENGLISH_CATALOG_FALLBACK = {
    "proj_mgr": "Project Manager",
    "search": "Global Search",
    "harvest": "Today's Harvest",
    "open_arch": "Open Archive",
    "open_notepad": "Open in Notepad",
    "settings": "Settings",
    "daily_tab": "Daily Tasks",
    "no_harvest": "No harvest for today yet!",
    "arch_title": "Today's Achievements",
    "no_arch": "Archive file does not exist yet.",
    "new_proj": "New project name:",
    "edit_task": "Edit task:",
    "filter": "Filter:",
    "tasks": "Tasks:",
    "add": "Add:",
    "confirm_archive": "Archive task?",
    "confirm_delete": "Delete task?",
}


def log_error(msg: str):
    """Safely log error messages even in windowed GUI / PyInstaller environments."""
    if sys.stderr is not None:
        try:
            sys.stderr.write(f"{msg}\n")
        except OSError:
            pass


def open_file_in_editor(path: Path):
    """Open a text file in the system default editor (e.g. Notepad)."""
    if path.exists():
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(
                ["open" if sys.platform == "darwin" else "xdg-open", str(path)]
            )


@dataclass
class Task:
    """Domain entity representing a single task item."""

    title: str
    is_pinned: bool = False

    @classmethod
    def from_line(cls, line: str) -> "Task":
        clean = line.strip().replace("\r", "").replace("\n", "")
        pin = clean.startswith("⭐")
        return cls(clean[1:].strip() if pin else clean, pin)

    def to_line(self) -> str:
        return f"⭐ {self.title}" if self.is_pinned else self.title


def sanitize_project_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()


def sanitize_task_title(title: str) -> str:
    cleaned = " ".join(title.replace("\r", " ").replace("\n", " ").split())
    return cleaned[1:].strip() if cleaned.startswith("⭐") else cleaned


def get_base_dir() -> Path:
    return (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )


def extract_filename_from_entry(entry: str) -> str:
    return entry[2:] if entry.startswith("⭐ ") else entry


def get_project_display_name(filename: str, translator=None) -> str:
    if filename == DAILY_FILENAME:
        return translator._("Daily Tasks") if translator else "Daily Tasks"
    return filename[:-4] if filename.endswith(".txt") else filename


class Translator:
    """Standard GNU gettext internationalization support with fallback."""

    def __init__(self, settings=None, base_dir=None):
        self.settings = settings
        if base_dir:
            self.base_dir = Path(base_dir)
            self.locales_dir = self.base_dir / "locales"
        else:
            self.base_dir = get_base_dir()
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass and (Path(meipass) / "locales").exists():
                self.locales_dir = Path(meipass) / "locales"
            else:
                self.locales_dir = self.base_dir / "locales"
        self.lang = "en"
        self.translation = None
        self.setup_translations()

    def setup_translations(self):
        self.lang = (
            self.settings.get("general", "language", "en") if self.settings else "en"
        )
        try:
            self.translation = gettext.translation(
                "dar_tasks",
                localedir=str(self.locales_dir),
                languages=[self.lang],
                fallback=True,
            )
        except OSError:
            self.translation = gettext.NullTranslations()

    def _(self, message: str) -> str:
        if self.translation:
            res = self.translation.gettext(message)
            if res != message:
                return res
        return ENGLISH_CATALOG_FALLBACK.get(message, message)

    def gettext(self, message: str) -> str:
        return self._(message)


class SettingsManager:
    """Manages application settings with clean JSON persistence."""

    DEFAULT_SETTINGS = {
        "behavior": {
            "confirm_on_archive": False,
            "confirm_on_delete": True,
            "auto_save_interval": 2,
        },
        "backup": {"backup_retention_days": 30, "archive_location": ""},
        "appearance": {"theme": "dark"},
        "search": {"lazy_load_threshold": 100, "case_sensitive": False},
        "general": {"language": "en"},
    }

    def __init__(self, app_dir):
        self.app_dir = Path(app_dir)
        self.settings_file = self.app_dir / ".app_settings.json"
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self._deep_merge(self.settings, json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                log_error(f"Failed to load settings: {e}")

    def save(self):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=str(self.app_dir), delete=False, encoding="utf-8"
            ) as tf:
                json.dump(self.settings, tf, indent=2, ensure_ascii=False)
                temp_path = Path(tf.name)
            temp_path.replace(self.settings_file)
        except OSError as e:
            log_error(f"Failed to save settings: {e}")
            if temp_path:
                temp_path.unlink(missing_ok=True)

    def get(self, section: str, key: str, default=None):
        return self.settings.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        self.settings.setdefault(section, {})[key] = value

    def reset_to_defaults(self):
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.save()

    def _deep_merge(self, target: dict, source: dict):
        for k, v in source.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
                self._deep_merge(target[k], v)
            else:
                target[k] = v


# ==========================================
# Deep Module: ProjectWorkspace
# ==========================================
class ProjectWorkspace:
    """Deep module managing project files, ordering, and workspace disk invariants."""

    def __init__(self, projects_dir):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def get_order_file_path(self) -> Path:
        return self.projects_dir / PROJECT_ORDER_FILENAME

    def get_project_path(self, filename: str) -> Path:
        return self.projects_dir / filename

    def load_order(self) -> list[str]:
        p = self.get_order_file_path()
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return [line.strip() for line in f if line.strip()]
        except OSError as e:
            log_error(f"Failed to load project order: {e}")
            return []

    def save_order(self, order_entries: list[str]) -> bool:
        try:
            with open(self.get_order_file_path(), "w", encoding="utf-8") as f:
                f.writelines(f"{e}\n" for e in order_entries)
            return True
        except OSError as e:
            log_error(f"Failed to save project order: {e}")
            return False

    def ensure_order(self) -> list[str]:
        try:
            files = [
                f.name
                for f in self.projects_dir.iterdir()
                if f.is_file()
                and f.name.endswith(".txt")
                and f.name not in (DAILY_TEMPLATE_FILENAME, PROJECT_ORDER_FILENAME)
            ]
        except OSError as e:
            log_error(f"Failed to read project files: {e}")
            return []
        files_set, seen, ordered = set(files), set(), []
        for entry in self.load_order():
            fn = extract_filename_from_entry(entry)
            if fn in files_set and fn not in seen:
                ordered.append(entry)
                seen.add(fn)
        for fn in sorted(files, key=lambda f: (f != DAILY_FILENAME, f.lower())):
            if fn not in seen:
                ordered.append(fn)
                seen.add(fn)
        if ordered and not self.get_order_file_path().exists():
            self.save_order(ordered)
        return ordered

    def list_projects(self) -> list[dict]:
        projects = []
        for entry in self.ensure_order():
            fn = extract_filename_from_entry(entry)
            if fn == DAILY_TEMPLATE_FILENAME:
                continue
            projects.append(
                {
                    "filename": fn,
                    "readonly": fn == DAILY_FILENAME,
                    "pinned": entry.startswith("⭐ "),
                    "entry": entry,
                    "path": str(self.get_project_path(fn)),
                }
            )
        return projects

    def create_project(self, name: str) -> str | None:
        clean = sanitize_project_name(name)
        if not clean:
            return None
        fn = f"{clean}.txt"
        path = self.get_project_path(fn)
        if not path.exists():
            try:
                path.touch()
                order = self.ensure_order()
                if fn not in [extract_filename_from_entry(e) for e in order]:
                    order.append(fn)
                    self.save_order(order)
            except OSError as e:
                log_error(f"Failed to create project {fn}: {e}")
                return None
        return fn

    def delete_project(self, filename: str) -> bool:
        if filename == DAILY_FILENAME:
            return False
        path, deleted = self.get_project_path(filename), False
        if send2trash:
            try:
                send2trash.send2trash(str(path))
                deleted = True
            except (OSError, RuntimeError) as e:
                log_error(f"send2trash failed: {e}")
        if not deleted and path.exists():
            try:
                path.unlink()
            except OSError as e:
                log_error(f"Failed to unlink {path}: {e}")
                return False
        self.save_order(
            [
                e
                for e in self.ensure_order()
                if extract_filename_from_entry(e) != filename
            ]
        )
        return True

    def rename_project(self, old_filename: str, new_name: str) -> str | None:
        if old_filename == DAILY_FILENAME:
            return None
        clean = sanitize_project_name(new_name)
        if not clean:
            return None
        new_fn = f"{clean}.txt"
        if new_fn == old_filename:
            return old_filename
        old_path, new_path = self.get_project_path(old_filename), self.get_project_path(
            new_fn
        )
        if not new_path.exists() and old_path.exists():
            try:
                old_path.rename(new_path)
                order = [
                    (
                        (f"⭐ {new_fn}" if e.startswith("⭐ ") else new_fn)
                        if extract_filename_from_entry(e) == old_filename
                        else e
                    )
                    for e in self.ensure_order()
                ]
                self.save_order(order)
                return new_fn
            except OSError as e:
                log_error(f"Failed to rename {old_filename} -> {new_fn}: {e}")
        return None

    def toggle_pin(self, filename: str) -> bool:
        if filename == DAILY_FILENAME:
            return False
        order = self.ensure_order()
        new_order = [
            (
                (
                    extract_filename_from_entry(e)
                    if e.startswith("⭐ ")
                    else f"⭐ {extract_filename_from_entry(e)}"
                )
                if extract_filename_from_entry(e) == filename
                else e
            )
            for e in order
        ]
        self.save_order(new_order)
        return True

    def move_project(self, index: int, direction: int) -> bool:
        order = self.ensure_order()
        target = index + direction
        if 0 <= index < len(order) and 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.save_order(order)
            return True
        return False


class SearchEngine:
    """Deep module for querying tasks across workspace projects."""

    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace

    def search(
        self,
        query: str,
        case_sensitive: bool = False,
        project_filename: str | None = None,
    ) -> list[dict]:
        clean = query.strip()
        if len(clean) < 2:
            return []
        results = []
        projects = self.workspace.list_projects()
        if project_filename:
            projects = [p for p in projects if p["filename"] == project_filename]
        for p in projects:
            path = Path(p["path"])
            if not path.exists():
                continue
            display_name = get_project_display_name(p["filename"])
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        raw = line.strip()
                        if raw and (
                            clean in raw
                            if case_sensitive
                            else clean.lower() in raw.lower()
                        ):
                            results.append(
                                {
                                    "project": display_name,
                                    "filename": p["filename"],
                                    "task": raw,
                                    "formatted": f"[{display_name}] {raw}",
                                }
                            )
            except OSError as e:
                log_error(f"Search failed for {path}: {e}")
        return results


class ProjectModel:
    """Manages tasks for a single project with atomic file operations and undo history."""

    @classmethod
    def get_archive_path(cls, base_dir=None, settings=None) -> Path:
        base = Path(base_dir) if base_dir else get_base_dir()
        arch = settings.get("backup", "archive_location") if settings else ""
        return Path(arch) if arch else base / DEFAULT_ARCHIVE_NAME

    def __init__(self, filename, settings=None, base_dir=None):
        self.filename = Path(filename)
        self.settings = settings
        self.base_dir = Path(base_dir) if base_dir else get_base_dir()
        self.archive_file = self.get_archive_path(self.base_dir, self.settings)
        self.trash_file = self.base_dir / DEFAULT_TRASH_NAME
        self.tasks: list[Task] = []
        self.undo_stack: list[tuple[str, str]] = []
        self.has_unsaved_changes = False
        self.load_success = False
        self.last_mtime: float = 0.0

    def load_tasks(self) -> bool:
        if not self.filename.exists():
            self.load_success, self.last_mtime = True, 0.0
            return True
        try:
            self.last_mtime = self.filename.stat().st_mtime
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            self.tasks = [Task.from_line(line) for line in lines if line.startswith("⭐")] + [
                Task.from_line(line) for line in lines if not line.startswith("⭐")
            ]
            self.load_success, self.has_unsaved_changes = True, False
            return True
        except OSError as e:
            log_error(f"Failed to load {self.filename}: {e}")
            return False

    def is_modified_externally(self) -> bool:
        try:
            return (
                self.filename.exists()
                and self.filename.stat().st_mtime > self.last_mtime
            )
        except OSError:
            return False

    def reload_if_modified(self) -> bool:
        return (
            self.load_tasks()
            if (self.is_modified_externally() and not self.has_unsaved_changes)
            else False
        )

    def save_tasks_atomic(self) -> bool:
        if not self.load_success:
            return False
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=str(self.filename.parent), delete=False, encoding="utf-8"
            ) as tf:
                for t in self.tasks:
                    tf.write(f"{t.to_line()}\n")
                temp_path = Path(tf.name)
            temp_path.replace(self.filename)
            self.last_mtime = self.filename.stat().st_mtime
            self.has_unsaved_changes = False
            return True
        except OSError as e:
            log_error(f"Failed to save {self.filename}: {e}")
            if temp_path:
                temp_path.unlink(missing_ok=True)
            return False

    def get_filtered_task_entries(self, filter_text: str = "") -> list[tuple[int, str]]:
        strings = [t.to_line() for t in self.tasks]
        if not filter_text:
            return list(enumerate(strings))
        sens = (
            self.settings.get("search", "case_sensitive", False)
            if self.settings
            else False
        )
        return [
            (i, s)
            for i, s in enumerate(strings)
            if (filter_text in s if sens else filter_text.lower() in s.lower())
        ]

    def add_task(self, task_title: str) -> bool:
        clean = sanitize_task_title(task_title)
        if clean:
            self.tasks.append(Task(title=clean, is_pinned=False))
            self.has_unsaved_changes = True
            return True
        return False

    def _resolve_task_index(self, ref: str | int) -> int:
        if isinstance(ref, int):
            return ref if 0 <= ref < len(self.tasks) else -1
        clean = ref.strip()
        is_pin = clean.startswith("⭐")
        title = clean[1:].strip() if is_pin else clean
        for i, t in enumerate(self.tasks):
            if t.title == title and t.is_pinned == is_pin:
                return i
        for i, t in enumerate(self.tasks):
            if t.title == title:
                return i
        return -1

    def _record_task_action(self, ref: str | int, target: Path, tag: str) -> bool:
        idx = self._resolve_task_index(ref)
        if idx == -1:
            return False
        task = self.tasks.pop(idx)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {task.to_line()}\n")
            self.undo_stack.append((tag, task.to_line()))
            if not self.save_tasks_atomic():
                self.has_unsaved_changes = True
            return True
        except OSError as e:
            log_error(f"Failed {tag}: {e}")
            self.tasks.insert(idx, task)
            return False

    def archive_task(self, ref: str | int) -> bool:
        return self._record_task_action(ref, self.archive_file, "archive")

    def delete_task(self, ref: str | int) -> bool:
        return self._record_task_action(ref, self.trash_file, "delete")

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        _, raw = self.undo_stack.pop()
        task = Task.from_line(raw)
        if task.is_pinned:
            self.tasks.insert(sum(1 for t in self.tasks if t.is_pinned), task)
        else:
            self.tasks.append(task)
        self.has_unsaved_changes = True
        return True

    def toggle_pin(self, ref: str | int) -> bool:
        idx = self._resolve_task_index(ref)
        if idx == -1:
            return False
        self.tasks[idx].is_pinned = not self.tasks[idx].is_pinned
        self.tasks = [t for t in self.tasks if t.is_pinned] + [
            t for t in self.tasks if not t.is_pinned
        ]
        self.has_unsaved_changes = True
        return True

    def edit_task(self, ref: str | int, new_text: str) -> bool:
        idx, clean = self._resolve_task_index(ref), sanitize_task_title(new_text)
        if idx == -1 or not clean:
            return False
        self.tasks[idx].title = clean
        self.has_unsaved_changes = True
        return True

    def move_task(self, idx: int, direction: int) -> bool:
        target = idx + direction
        if (
            0 <= idx < len(self.tasks)
            and 0 <= target < len(self.tasks)
            and self.tasks[idx].is_pinned == self.tasks[target].is_pinned
        ):
            self.tasks[idx], self.tasks[target] = self.tasks[target], self.tasks[idx]
            self.has_unsaved_changes = True
            return True
        return False

    @classmethod
    def get_today_harvest(cls, base_dir=None, settings=None) -> list[str]:
        today, path = datetime.datetime.now().strftime(
            "%Y-%m-%d"
        ), cls.get_archive_path(base_dir, settings)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return [line.strip() for line in f if line.startswith(f"[{today}")]
        except OSError as e:
            log_error(f"Failed to read harvest: {e}")
            return []


class BackupManager:
    """Manages project backups and daily task rotation."""

    def __init__(self, base_dir, projects_dir, backups_dir, settings):
        self.base_dir, self.projects_dir, self.backups_dir, self.settings = (
            Path(base_dir),
            Path(projects_dir),
            Path(backups_dir),
            settings,
        )

    def create_snapshot(self, reason: str = "manual") -> bool:
        dest = self.backups_dir / datetime.date.today().isoformat()
        dest.mkdir(parents=True, exist_ok=True)
        try:
            for f in self.projects_dir.glob("*.txt"):
                shutil.copy2(str(f), str(dest / f.name))
            return True
        except OSError as e:
            log_error(f"Backup snapshot failed: {e}")
            return False

    def cleanup_old_backups(self):
        days = (
            self.settings.get("backup", "backup_retention_days", 30)
            if self.settings
            else 30
        )
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        if self.backups_dir.exists():
            for d in self.backups_dir.iterdir():
                if d.is_dir():
                    try:
                        if datetime.datetime.fromisoformat(d.name) < cutoff:
                            shutil.rmtree(str(d), ignore_errors=True)
                    except ValueError:
                        pass

    def check_and_rollover_daily_tasks(self) -> bool:
        daily = self.projects_dir / DAILY_FILENAME
        try:
            if (
                daily.exists()
                and datetime.date.fromtimestamp(daily.stat().st_mtime)
                < datetime.date.today()
            ):
                self.setup_daily_tasks()
                return True
        except OSError:
            pass
        return False

    def setup_daily_tasks(self):
        daily, tmpl, arch = (
            self.projects_dir / DAILY_FILENAME,
            self.projects_dir / DAILY_TEMPLATE_FILENAME,
            self.base_dir / DAILY_ARCHIVE_NAME,
        )
        if not daily.exists():
            shutil.copyfile(str(tmpl), str(daily)) if tmpl.exists() else daily.touch()
            return
        last_mod = datetime.date.fromtimestamp(daily.stat().st_mtime)
        if last_mod < datetime.date.today():
            try:
                content = daily.read_text(encoding="utf-8").strip()
                if content:
                    with open(arch, "a", encoding="utf-8") as af:
                        af.write(f"\n--- {last_mod.isoformat()} ---\n{content}\n")
                (
                    shutil.copyfile(str(tmpl), str(daily))
                    if tmpl.exists()
                    else daily.write_text("", encoding="utf-8")
                )
            except OSError as e:
                log_error(f"Daily tasks rollover error: {e}")
