"""
Dar Tasks - Headless Core Domain Layer.
Encapsulates domain entities, persistence invariants, search, settings, and backup rotation.
Strictly decoupled from wxPython and any GUI presentation frameworks.
"""

from dataclasses import dataclass
import copy
import datetime
import json
from pathlib import Path
import shutil
import sys
import tempfile

try:
    import send2trash
except ImportError:
    send2trash = None

# ==========================================
# Domain Constants
# ==========================================
DEFAULT_ARCHIVE_NAME = "أرشيف_المهام.txt"
DEFAULT_TRASH_NAME = "trash.txt"
DAILY_FILENAME = "daily.txt"
DAILY_TEMPLATE_FILENAME = "daily_template.txt"
PROJECT_ORDER_FILENAME = ".project_order.txt"

TRANSLATIONS = {
    "en": {
        "proj_mgr": "Project Manager",
        "search": "Global Search",
        "harvest": "Today's Harvest",
        "open_arch": "Open Archive",
        "settings": "Settings",
        "daily_tab": "Daily Tasks",
        "no_harvest": "No harvest for today yet!",
        "arch_title": "Today's Achievements",
        "no_arch": "Archive file does not exist yet.",
        "new_proj": "New project name:",
    },
    "ar": {
        "proj_mgr": "مدير المشاريع",
        "search": "البحث الشامل",
        "harvest": "حصاد اليوم",
        "open_arch": "فتح الأرشيف",
        "settings": "الإعدادات",
        "daily_tab": "مهام اليوم",
        "no_harvest": "لا يوجد حصاد لليوم بعد!",
        "arch_title": "إنجازات اليوم",
        "no_arch": "ملف الأرشيف غير موجود بعد.",
        "new_proj": "اسم المشروع الجديد:",
    },
}


# ==========================================
# Domain Entities
# ==========================================
@dataclass
class Task:
    """Domain entity representing a single task item."""

    title: str
    is_pinned: bool = False

    @classmethod
    def from_line(cls, line: str) -> "Task":
        clean = line.strip()
        is_pinned = clean.startswith("⭐")
        if is_pinned:
            title = clean[1:].strip()
            if title.startswith(" "):
                title = title.strip()
        else:
            title = clean
        return cls(title=title, is_pinned=is_pinned)

    def to_line(self) -> str:
        return f"⭐ {self.title}" if self.is_pinned else self.title

    @property
    def display_text(self) -> str:
        return self.to_line()


# ==========================================
# Utility Functions
# ==========================================
def sanitize_project_name(name: str) -> str:
    """Sanitize project names by allowing only alphanumeric and safe separators."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()


def get_base_dir() -> Path:
    """Get the application root directory as a pathlib.Path."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def extract_filename_from_entry(entry: str) -> str:
    """Extract filename from a project order entry (handling pinned '⭐ ' prefix)."""
    return entry[2:] if entry.startswith("⭐ ") else entry


def get_project_display_name(filename: str, translator=None) -> str:
    """Return user-friendly display name for project."""
    if filename == DAILY_FILENAME:
        return translator._("daily_tab") if translator else "Daily Tasks"
    return filename[:-4] if filename.endswith(".txt") else filename


# ==========================================
# Settings & Internationalization
# ==========================================
class Translator:
    """Provides internationalization support."""

    def __init__(self, settings=None):
        self.settings = settings
        self.lang = "en"
        self.setup_translations()

    def setup_translations(self):
        if self.settings:
            self.lang = self.settings.get("general", "language", "en")

    def _(self, key: str) -> str:
        return TRANSLATIONS.get(self.lang, {}).get(key, TRANSLATIONS["en"].get(key, key))


class SettingsManager:
    """Manages application settings with JSON persistence."""

    DEFAULT_SETTINGS = {
        "behavior": {
            "confirm_on_archive": False,
            "confirm_on_delete": True,
            "auto_save_interval": 2,
        },
        "backup": {
            "backup_retention_days": 30,
            "archive_location": "",
        },
        "appearance": {
            "theme": "dark",
        },
        "search": {
            "lazy_load_threshold": 100,
            "case_sensitive": False,
        },
        "general": {
            "language": "en",
        },
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
                sys.stderr.write(f"Failed to load settings from {self.settings_file}: {e}\n")

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
            sys.stderr.write(f"Failed to save settings: {e}\n")
            if temp_path:
                temp_path.unlink(missing_ok=True)

    def get(self, section: str, key: str, default=None):
        return self.settings.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value

    def reset_to_defaults(self):
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.save()

    def _deep_merge(self, target: dict, source: dict):
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
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
        path = self.get_order_file_path()
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return [line.strip() for line in f if line.strip()]
        except OSError as e:
            sys.stderr.write(f"Failed to load project order: {e}\n")
            return []

    def save_order(self, order_entries: list[str]) -> bool:
        path = self.get_order_file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                for entry in order_entries:
                    f.write(entry + "\n")
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to save project order: {e}\n")
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
            sys.stderr.write(f"Failed to read project files in {self.projects_dir}: {e}\n")
            return []
        files_set = set(files)
        saved = self.load_order()
        ordered, seen = [], set()
        for entry in saved:
            fname = extract_filename_from_entry(entry)
            if fname in files_set and fname not in seen:
                ordered.append(entry)
                seen.add(fname)
        for fname in sorted(files, key=lambda f: (f != DAILY_FILENAME, f.lower())):
            if fname not in seen:
                ordered.append(fname)
                seen.add(fname)
        if ordered and not self.get_order_file_path().exists():
            self.save_order(ordered)
        return ordered

    def list_projects(self) -> list[dict]:
        order = self.ensure_order()
        projects = []
        for entry in order:
            fn = extract_filename_from_entry(entry)
            if fn == DAILY_TEMPLATE_FILENAME:
                continue
            projects.append(
                {
                    "filename": fn,
                    "display": "Daily Tasks" if fn == DAILY_FILENAME else fn[:-4],
                    "readonly": fn == DAILY_FILENAME,
                    "pinned": entry.startswith("⭐ "),
                    "entry": entry,
                    "path": str(self.get_project_path(fn)),
                }
            )
        return projects

    def create_project(self, name: str) -> str | None:
        clean_name = sanitize_project_name(name)
        if not clean_name:
            return None
        fn = f"{clean_name}.txt"
        path = self.get_project_path(fn)
        if not path.exists():
            try:
                with open(path, "w", encoding="utf-8"):
                    pass
                order = self.ensure_order()
                if fn not in [extract_filename_from_entry(e) for e in order]:
                    order.append(fn)
                    self.save_order(order)
                return fn
            except OSError as e:
                sys.stderr.write(f"Failed to create project {fn}: {e}\n")
                return None
        return fn

    def delete_project(self, filename: str) -> bool:
        if filename == DAILY_FILENAME:
            return False
        path = self.get_project_path(filename)
        deleted = False
        if send2trash:
            try:
                send2trash.send2trash(str(path))
                deleted = True
            except OSError as e:
                sys.stderr.write(f"send2trash failed for {path}, falling back to unlink: {e}\n")
            except Exception as e:
                sys.stderr.write(f"Unexpected error in send2trash for {path}: {e}\n")
        if not deleted and path.exists():
            try:
                path.unlink()
                deleted = True
            except OSError as e:
                sys.stderr.write(f"Failed to delete project file {path}: {e}\n")
                return False
        order = [e for e in self.ensure_order() if extract_filename_from_entry(e) != filename]
        self.save_order(order)
        return True

    def rename_project(self, old_filename: str, new_name: str) -> str | None:
        if old_filename == DAILY_FILENAME:
            return None
        clean_name = sanitize_project_name(new_name)
        if not clean_name:
            return None
        new_fn = f"{clean_name}.txt"
        if new_fn == old_filename:
            return old_filename
        old_path = self.get_project_path(old_filename)
        new_path = self.get_project_path(new_fn)
        if not new_path.exists() and old_path.exists():
            try:
                old_path.rename(new_path)
                order = [
                    (f"⭐ {new_fn}" if e.startswith("⭐ ") else new_fn)
                    if extract_filename_from_entry(e) == old_filename
                    else e
                    for e in self.ensure_order()
                ]
                self.save_order(order)
                return new_fn
            except OSError as e:
                sys.stderr.write(f"Failed to rename project {old_filename} -> {new_fn}: {e}\n")
                return None
        return None

    def toggle_pin(self, filename: str) -> bool:
        if filename == DAILY_FILENAME:
            return False
        order = self.ensure_order()
        new_order = [
            (
                f"⭐ {extract_filename_from_entry(e)}"
                if not e.startswith("⭐ ")
                else extract_filename_from_entry(e)
            )
            if extract_filename_from_entry(e) == filename
            else e
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

    def reorder_project(self, index: int, direction: int) -> bool:
        """Alias for move_project fulfilling ADR-0004 specification."""
        return self.move_project(index, direction)


# ==========================================
# Deep Module: SearchEngine
# ==========================================
class SearchEngine:
    """Deep module for querying tasks across workspace projects."""

    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace

    def search(
        self, query: str, case_sensitive: bool = False, project_filename: str | None = None
    ) -> list[dict]:
        clean_query = query.strip()
        if len(clean_query) < 2:
            return []

        results = []
        projects = self.workspace.list_projects()
        if project_filename:
            projects = [p for p in projects if p["filename"] == project_filename]

        for project_info in projects:
            path = Path(project_info["path"])
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        raw_task = line.strip()
                        if not raw_task:
                            continue
                        match = (
                            clean_query in raw_task
                            if case_sensitive
                            else clean_query.lower() in raw_task.lower()
                        )
                        if match:
                            results.append(
                                {
                                    "project": project_info["display"],
                                    "filename": project_info["filename"],
                                    "task": raw_task,
                                    "formatted": f"[{project_info['display']}] {raw_task}",
                                }
                            )
            except OSError as e:
                sys.stderr.write(f"Failed to search in project file {path}: {e}\n")
        return results


# ==========================================
# Deep Module: ProjectModel
# ==========================================
class ProjectModel:
    """Manages tasks for a single project with atomic file operations and undo history."""

    def __init__(self, filename, settings=None, base_dir=None):
        self.filename = Path(filename)
        self.settings = settings
        self.base_dir = Path(base_dir) if base_dir else get_base_dir()

        archive_setting = self.settings.get("backup", "archive_location") if self.settings else ""
        self.archive_file = (
            Path(archive_setting) if archive_setting else self.base_dir / DEFAULT_ARCHIVE_NAME
        )
        self.trash_file = self.base_dir / DEFAULT_TRASH_NAME

        self.tasks: list[Task] = []
        self.undo_stack: list[tuple[str, str]] = []
        self.has_unsaved_changes = False
        self.load_success = False

    @property
    def pinned_tasks(self) -> list[str]:
        return [t.to_line() for t in self.tasks if t.is_pinned]

    @pinned_tasks.setter
    def pinned_tasks(self, lines: list[str]):
        new_pinned = [Task.from_line(l) for l in lines]
        for p in new_pinned:
            p.is_pinned = True
        self.tasks = new_pinned + [t for t in self.tasks if not t.is_pinned]

    @property
    def all_tasks(self) -> list[str]:
        return [t.title for t in self.tasks if not t.is_pinned]

    @all_tasks.setter
    def all_tasks(self, lines: list[str]):
        new_unpinned = [Task(title=l.strip(), is_pinned=False) for l in lines]
        self.tasks = [t for t in self.tasks if t.is_pinned] + new_unpinned

    def load_tasks(self) -> bool:
        if not self.filename.exists():
            self.load_success = True
            return True
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            loaded_pinned = [Task.from_line(l) for l in lines if l.startswith("⭐")]
            loaded_unpinned = [Task.from_line(l) for l in lines if not l.startswith("⭐")]
            self.tasks = loaded_pinned + loaded_unpinned
            self.load_success = True
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to load tasks from {self.filename}: {e}\n")
            return False

    def save_tasks_atomic(self) -> bool:
        if not self.load_success:
            return False
        dir_name = self.filename.parent
        dir_name.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=str(dir_name), delete=False, encoding="utf-8"
            ) as tf:
                for task in self.tasks:
                    tf.write(task.to_line() + "\n")
                temp_path = Path(tf.name)
            temp_path.replace(self.filename)
            self.has_unsaved_changes = False
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to save tasks to {self.filename}: {e}\n")
            if temp_path:
                temp_path.unlink(missing_ok=True)
            return False

    def get_filtered_task_entries(self, filter_text: str = "") -> list[tuple[int, str]]:
        task_strings = [t.to_line() for t in self.tasks]
        if not filter_text:
            return list(enumerate(task_strings))
        sensitive = (
            self.settings.get("search", "case_sensitive", False) if self.settings else False
        )
        return [
            (idx, t)
            for idx, t in enumerate(task_strings)
            if (filter_text in t if sensitive else filter_text.lower() in t.lower())
        ]

    def add_task(self, task_title: str) -> bool:
        clean_title = task_title.strip()
        if clean_title.startswith("⭐"):
            clean_title = clean_title[1:].strip()
        if clean_title:
            self.tasks.append(Task(title=clean_title, is_pinned=False))
            self.has_unsaved_changes = True
            return True
        return False

    def _find_task_index(self, task_text: str) -> int:
        clean = task_text.strip()
        is_pinned = clean.startswith("⭐")
        title = clean[1:].strip() if is_pinned else clean
        for idx, task in enumerate(self.tasks):
            if task.title == title and task.is_pinned == is_pinned:
                return idx
        for idx, task in enumerate(self.tasks):
            if task.title == title:
                return idx
        return -1

    def _record_task_action(self, task_text: str, target_file: Path, action_tag: str) -> bool:
        """Private helper unifying task extraction, timestamp recording, and undo logging."""
        idx = self._find_task_index(task_text)
        if idx == -1:
            return False
        task = self.tasks.pop(idx)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {task.to_line()}\n")
            self.undo_stack.append((action_tag, task.to_line()))
            self.has_unsaved_changes = True
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to {action_tag} task: {e}\n")
            self.tasks.insert(idx, task)
            return False

    def archive_task(self, task_text: str) -> bool:
        return self._record_task_action(task_text, self.archive_file, "archive")

    def delete_task(self, task_text: str) -> bool:
        return self._record_task_action(task_text, self.trash_file, "delete")

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        _, raw_line = self.undo_stack.pop()
        task = Task.from_line(raw_line)
        if task.is_pinned:
            pinned_count = sum(1 for t in self.tasks if t.is_pinned)
            self.tasks.insert(pinned_count, task)
        else:
            self.tasks.append(task)
        self.has_unsaved_changes = True
        return True

    def toggle_pin(self, task_text: str) -> bool:
        idx = self._find_task_index(task_text)
        if idx == -1:
            return False
        task = self.tasks[idx]
        task.is_pinned = not task.is_pinned
        self.tasks = [t for t in self.tasks if t.is_pinned] + [t for t in self.tasks if not t.is_pinned]
        self.has_unsaved_changes = True
        return True

    def edit_task(self, old_text: str, new_text: str) -> bool:
        idx = self._find_task_index(old_text)
        if idx == -1:
            return False
        clean_new = new_text.strip()
        if clean_new.startswith("⭐"):
            clean_new = clean_new[1:].strip()
        if not clean_new:
            return False
        self.tasks[idx].title = clean_new
        self.has_unsaved_changes = True
        return True

    def move_task(self, idx: int, direction: int) -> bool:
        if not (0 <= idx < len(self.tasks)):
            return False
        target = idx + direction
        if not (0 <= target < len(self.tasks)):
            return False
        if self.tasks[idx].is_pinned != self.tasks[target].is_pinned:
            return False
        self.tasks[idx], self.tasks[target] = self.tasks[target], self.tasks[idx]
        self.has_unsaved_changes = True
        return True

    @classmethod
    def get_today_harvest(cls, base_dir=None, settings=None) -> list[str]:
        """Query tasks archived today across the system."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        base = Path(base_dir) if base_dir else get_base_dir()
        arch_setting = settings.get("backup", "archive_location") if settings else ""
        arch_path = Path(arch_setting) if arch_setting else base / DEFAULT_ARCHIVE_NAME
        if not arch_path.exists():
            return []
        try:
            with open(arch_path, "r", encoding="utf-8", errors="replace") as f:
                return [line.strip() for line in f if line.startswith(f"[{today}")]
        except OSError as e:
            sys.stderr.write(f"Failed to read harvest archive {arch_path}: {e}\n")
            return []


# ==========================================
# Backup Manager
# ==========================================
class BackupManager:
    """Manages project backups and daily task rotation."""

    def __init__(self, base_dir, projects_dir, backups_dir, settings_manager):
        self.base_dir = Path(base_dir)
        self.projects_dir = Path(projects_dir)
        self.backups_dir = Path(backups_dir)
        self.settings = settings_manager

    def create_snapshot(self, reason: str = "manual") -> bool:
        date_str = datetime.date.today().isoformat()
        dest_dir = self.backups_dir / date_str
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            for f in self.projects_dir.iterdir():
                if f.is_file() and f.name.endswith(".txt"):
                    shutil.copy2(str(f), str(dest_dir / f.name))
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to create backup snapshot: {e}\n")
            return False

    def cleanup_old_backups(self):
        days = self.settings.get("backup", "backup_retention_days", 30) if self.settings else 30
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        if not self.backups_dir.exists():
            return
        for d in self.backups_dir.iterdir():
            if d.is_dir():
                try:
                    if datetime.datetime.fromisoformat(d.name) < cutoff:
                        shutil.rmtree(str(d), ignore_errors=True)
                except ValueError:
                    pass

    def setup_daily_tasks(self):
        daily_path = self.projects_dir / DAILY_FILENAME
        template_path = self.projects_dir / DAILY_TEMPLATE_FILENAME
        archive_path = self.base_dir / "أرشيف_المهام_اليومية.txt"

        if not daily_path.exists():
            if template_path.exists():
                shutil.copyfile(str(template_path), str(daily_path))
            else:
                with open(daily_path, "w", encoding="utf-8"):
                    pass
            return

        last_mod = datetime.date.fromtimestamp(daily_path.stat().st_mtime)
        if last_mod < datetime.date.today():
            try:
                with open(daily_path, "r", encoding="utf-8") as df:
                    content = df.read().strip()
                if content:
                    with open(archive_path, "a", encoding="utf-8") as af:
                        af.write(f"\n--- {last_mod.isoformat()} ---\n{content}\n")
            except OSError as e:
                sys.stderr.write(f"Failed to archive daily tasks: {e}\n")
                return

            try:
                if template_path.exists():
                    shutil.copyfile(str(template_path), str(daily_path))
                else:
                    with open(daily_path, "w", encoding="utf-8"):
                        pass
            except OSError as e:
                sys.stderr.write(f"Failed to reset daily tasks: {e}\n")
