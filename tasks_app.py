"""
Dar Tasks - Lightweight, accessible task and project management application.
Consolidated, clean architecture with deep domain modules and native wxPython controls.
"""

import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wx

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import send2trash
except ImportError:
    send2trash = None

# ==========================================
# Constants & Colors
# ==========================================
BG_COLOR = wx.Colour(30, 30, 30)
FG_COLOR = wx.Colour(240, 240, 240)
ACCENT_COLOR = wx.Colour(45, 45, 45)
FONT_SIZE = 14

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
# Utility Functions
# ==========================================
def sanitize_project_name(name):
    """Sanitize project names by allowing only alphanumeric and safe separators."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()


def get_base_dir():
    """Get the application root directory."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))



def extract_filename_from_entry(entry):
    """Extract filename from a project order entry (handling pinned '⭐ ' prefix)."""
    return entry[2:] if entry.startswith("⭐ ") else entry


def get_project_display_name(filename, translator=None):
    """Return user-friendly display name for project."""
    if filename == DAILY_FILENAME:
        return translator._("daily_tab") if translator else "Daily Tasks"
    return filename[:-4] if filename.endswith(".txt") else filename


# ==========================================
# Deep Module: ProjectWorkspace
# ==========================================
class ProjectWorkspace:
    """Deep module managing project files, ordering, and workspace disk invariants."""

    def __init__(self, projects_dir):
        self.projects_dir = str(projects_dir)
        os.makedirs(self.projects_dir, exist_ok=True)

    def get_order_file_path(self):
        return os.path.join(self.projects_dir, PROJECT_ORDER_FILENAME)

    def get_project_path(self, filename):
        return os.path.join(self.projects_dir, filename)

    def load_order(self):
        path = self.get_order_file_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return [line.strip() for line in f if line.strip()]
        except OSError as e:
            sys.stderr.write(f"Failed to load project order: {e}\n")
            return []

    def save_order(self, order_entries):
        path = self.get_order_file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                for entry in order_entries:
                    f.write(entry + "\n")
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to save project order: {e}\n")
            return False

    def ensure_order(self):
        try:
            files = [
                f
                for f in os.listdir(self.projects_dir)
                if f.endswith(".txt") and f not in (DAILY_TEMPLATE_FILENAME, PROJECT_ORDER_FILENAME)
            ]
        except OSError:
            return []
        files_set = set(files)
        saved = self.load_order()
        ordered, seen = [], set()
        for entry in saved:
            fname = extract_filename_from_entry(entry)
            if fname in files_set and fname not in seen:
                ordered.append(entry)
                seen.add(fname)
        for fname in sorted(files, key=lambda f: (f != "daily.txt", f.lower())):
            if fname not in seen:
                ordered.append(fname)
                seen.add(fname)
        if ordered and not os.path.exists(self.get_order_file_path()):
            self.save_order(ordered)
        return ordered

    def list_projects(self):
        order = self.ensure_order()
        projects = []
        for r in order:
            fn = extract_filename_from_entry(r)
            if fn == DAILY_TEMPLATE_FILENAME:
                continue
            projects.append(
                {
                    "filename": fn,
                    "display": "Daily Tasks" if fn == DAILY_FILENAME else fn[:-4],
                    "readonly": fn == DAILY_FILENAME,
                    "pinned": r.startswith("⭐ "),
                    "entry": r,
                    "path": self.get_project_path(fn),
                }
            )
        return projects

    def create_project(self, name):
        clean_name = sanitize_project_name(name)
        if not clean_name:
            return None
        fn = f"{clean_name}.txt"
        path = self.get_project_path(fn)
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8"):
                    pass
                order = self.ensure_order()
                if fn not in [extract_filename_from_entry(r) for r in order]:
                    order.append(fn)
                    self.save_order(order)
                return fn
            except Exception:
                return None
        return fn

    def delete_project(self, filename):
        if filename == DAILY_FILENAME:
            return False
        path = self.get_project_path(filename)
        deleted = False
        if send2trash:
            try:
                send2trash.send2trash(path)
                deleted = True
            except Exception:
                pass
        if not deleted and os.path.exists(path):
            try:
                os.remove(path)
                deleted = True
            except Exception:
                return False
        order = [r for r in self.ensure_order() if extract_filename_from_entry(r) != filename]
        self.save_order(order)
        return True

    def rename_project(self, old_filename, new_name):
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
        if not os.path.exists(new_path) and os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                order = [
                    (f"⭐ {new_fn}" if r.startswith("⭐ ") else new_fn)
                    if extract_filename_from_entry(r) == old_filename
                    else r
                    for r in self.ensure_order()
                ]
                self.save_order(order)
                return new_fn
            except Exception:
                return None
        return None

    def toggle_pin(self, filename):
        if filename == DAILY_FILENAME:
            return False
        order = self.ensure_order()
        new_order = [
            (
                f"⭐ {extract_filename_from_entry(r)}"
                if not r.startswith("⭐ ")
                else extract_filename_from_entry(r)
            )
            if extract_filename_from_entry(r) == filename
            else r
            for r in order
        ]
        self.save_order(new_order)
        return True

    def move_project(self, index, direction):
        order = self.ensure_order()
        target = index + direction
        if 0 <= index < len(order) and 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.save_order(order)
            return True
        return False


# Compatibility functions delegating to ProjectWorkspace
def load_project_order(projects_dir):
    return ProjectWorkspace(projects_dir).load_order()


def save_project_order(projects_dir, order_entries):
    ProjectWorkspace(projects_dir).save_order(order_entries)


def get_project_order(projects_dir):
    return ProjectWorkspace(projects_dir).ensure_order()


def ensure_project_order(projects_dir):
    """Backward-compatible alias for get_project_order."""
    return get_project_order(projects_dir)


# ==========================================
# Deep Module: SearchEngine
# ==========================================
class SearchEngine:
    """Deep module for searching tasks across workspace projects."""

    def __init__(self, workspace):
        self.workspace = workspace

    def search(self, query, case_sensitive=False, project_filename=None):
        query = query.strip()
        if len(query) < 2:
            return []

        results = []
        projects = self.workspace.list_projects()
        if project_filename:
            projects = [p for p in projects if p["filename"] == project_filename]

        for p in projects:
            path = p["path"]
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        task = line.strip()
                        if not task:
                            continue
                        match = query in task if case_sensitive else query.lower() in task.lower()
                        if match:
                            results.append(
                                {
                                    "project": p["display"],
                                    "filename": p["filename"],
                                    "task": task,
                                    "formatted": f"[{p['display']}] {task}",
                                }
                            )
            except Exception:
                pass
        return results


# ==========================================
# Translator & Settings
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

    def _(self, key):
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
        self.app_dir = app_dir
        self.settings_file = os.path.join(app_dir, ".app_settings.json")
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self._deep_merge(self.settings, json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                sys.stderr.write(f"Failed to load settings: {e}\n")

    def save(self):
        tempname = None
        try:
            dir_name = os.path.dirname(self.settings_file)
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(self.settings, tf, indent=2, ensure_ascii=False)
                tempname = tf.name
            os.replace(tempname, self.settings_file)
        except OSError as e:
            sys.stderr.write(f"Failed to save settings: {e}\n")
            if tempname and os.path.exists(tempname):
                try:
                    os.remove(tempname)
                except OSError:
                    pass

    def get(self, section, key, default=None):
        return self.settings.get(section, {}).get(key, default)

    def set(self, section, key, value):
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value

    def reset_to_defaults(self):
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.save()

    def _deep_merge(self, target, source):
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self._deep_merge(target[k], v)
            else:
                target[k] = v


# ==========================================
# Core Project Model
# ==========================================
class ProjectModel:
    """Manages tasks for a single project with atomic file operations."""

    def __init__(self, filename, settings=None, base_dir=None):
        self.filename = filename
        self.settings = settings
        self.base_dir = base_dir or get_base_dir()
        self.archive_file = (
            self.settings.get("backup", "archive_location") if self.settings else ""
        ) or os.path.join(self.base_dir, DEFAULT_ARCHIVE_NAME)
        self.trash_file = os.path.join(self.base_dir, DEFAULT_TRASH_NAME)
        self.all_tasks, self.pinned_tasks, self.undo_stack = [], [], []
        self.has_unsaved_changes = False
        self.load_success = False

    def load_tasks(self):
        if not os.path.exists(self.filename):
            self.load_success = True
            return True
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            self.pinned_tasks = [line for line in lines if line.startswith("⭐")]
            self.all_tasks = [line for line in lines if not line.startswith("⭐")]
            self.load_success = True
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to load tasks from {self.filename}: {e}\n")
            return False

    def save_tasks_atomic(self):
        if not self.load_success:
            return False
        dir_name = os.path.dirname(self.filename) or "."
        tempname = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                for task_line in self.pinned_tasks + self.all_tasks:
                    tf.write(task_line + "\n")
                tempname = tf.name
            os.replace(tempname, self.filename)
            self.has_unsaved_changes = False
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to save tasks to {self.filename}: {e}\n")
            if tempname and os.path.exists(tempname):
                try:
                    os.remove(tempname)
                except OSError:
                    pass
            return False

    def get_filtered_task_entries(self, filter_text=""):
        tasks = self.pinned_tasks + self.all_tasks
        if not filter_text:
            return list(enumerate(tasks))
        sensitive = self.settings.get("search", "case_sensitive", False) if self.settings else False
        return [
            (idx, t)
            for idx, t in enumerate(tasks)
            if (filter_text in t if sensitive else filter_text.lower() in t.lower())
        ]

    def add_task(self, txt):
        txt = txt.strip()
        if txt.startswith("⭐"):
            txt = txt[1:].strip()
        if txt:
            self.all_tasks.append(txt)
            self.has_unsaved_changes = True
            return True
        return False

    def _remove(self, txt):
        if txt in self.pinned_tasks:
            self.pinned_tasks.remove(txt)
            return True
        if txt in self.all_tasks:
            self.all_tasks.remove(txt)
            return True
        return False

    def archive_task(self, txt):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.archive_file, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {txt}\n")
            self._remove(txt)
            self.undo_stack.append(("archive", txt))
            self.has_unsaved_changes = True
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to archive task: {e}\n")
            return False

    def delete_task(self, txt):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.trash_file, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {txt}\n")
            self._remove(txt)
            self.undo_stack.append(("delete", txt))
            self.has_unsaved_changes = True
            return True
        except OSError as e:
            sys.stderr.write(f"Failed to delete task: {e}\n")
            return False

    def undo(self):
        if not self.undo_stack:
            return False
        tag, txt = self.undo_stack.pop()
        if txt.startswith("⭐"):
            self.pinned_tasks.append(txt)
        else:
            self.all_tasks.append(txt)
        self.has_unsaved_changes = True
        return True

    def toggle_pin(self, txt):
        if txt.startswith("⭐"):
            new = txt[1:].strip()
            if txt in self.pinned_tasks:
                self.pinned_tasks.remove(txt)
                self.all_tasks.append(new)
                self.has_unsaved_changes = True
                return True
        else:
            new = "⭐ " + txt
            if txt in self.all_tasks:
                self.all_tasks.remove(txt)
                self.pinned_tasks.append(new)
                self.has_unsaved_changes = True
                return True
        return False

    def edit_task(self, old, new):
        new = new.strip()
        if new.startswith("⭐"):
            new = new[1:].strip()
        if not new:
            return False
        if old in self.pinned_tasks:
            self.pinned_tasks[self.pinned_tasks.index(old)] = f"⭐ {new}"
            self.has_unsaved_changes = True
            return True
        if old in self.all_tasks:
            self.all_tasks[self.all_tasks.index(old)] = new
            self.has_unsaved_changes = True
            return True
        return False

    def move_task(self, idx, direction):
        if idx < len(self.pinned_tasks):
            target_list = self.pinned_tasks
            list_idx = idx
        else:
            target_list = self.all_tasks
            list_idx = idx - len(self.pinned_tasks)

        if not (0 <= list_idx + direction < len(target_list)):
            return False

        target_list[list_idx], target_list[list_idx + direction] = (
            target_list[list_idx + direction],
            target_list[list_idx],
        )
        self.has_unsaved_changes = True
        return True


# ==========================================
# Backup Manager
# ==========================================
class BackupManager:
    """Manages project backups and daily task rotation."""

    def __init__(self, base_dir, projects_dir, backups_dir, settings_manager):
        self.base_dir = base_dir
        self.projects_dir = projects_dir
        self.backups_dir = backups_dir
        self.settings = settings_manager

    def create_snapshot(self, reason="manual"):
        date_str = datetime.date.today().isoformat()
        dest_dir = os.path.join(self.backups_dir, date_str)
        os.makedirs(dest_dir, exist_ok=True)
        try:
            for fn in os.listdir(self.projects_dir):
                if fn.endswith(".txt"):
                    shutil.copy2(os.path.join(self.projects_dir, fn), os.path.join(dest_dir, fn))
            return True
        except Exception:
            return False

    def cleanup_old_backups(self):
        days = self.settings.get("backup", "backup_retention_days", 30)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        if not os.path.exists(self.backups_dir):
            return
        for d in os.listdir(self.backups_dir):
            path = os.path.join(self.backups_dir, d)
            if os.path.isdir(path):
                try:
                    if datetime.datetime.fromisoformat(d) < cutoff:
                        shutil.rmtree(path, ignore_errors=True)
                except ValueError:
                    pass

    def setup_daily_tasks(self):
        daily_path = os.path.join(self.projects_dir, DAILY_FILENAME)
        template_path = os.path.join(self.projects_dir, DAILY_TEMPLATE_FILENAME)
        archive_path = os.path.join(self.base_dir, "أرشيف_المهام_اليومية.txt")

        if not os.path.exists(daily_path):
            if os.path.exists(template_path):
                shutil.copyfile(template_path, daily_path)
            else:
                with open(daily_path, "w", encoding="utf-8"):
                    pass
            return

        last_mod = datetime.date.fromtimestamp(os.path.getmtime(daily_path))
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
                if os.path.exists(template_path):
                    shutil.copyfile(template_path, daily_path)
                else:
                    with open(daily_path, "w", encoding="utf-8"):
                        pass
            except OSError as e:
                sys.stderr.write(f"Failed to reset daily tasks: {e}\n")


# ==========================================
# Task Project Panel
# ==========================================
class TaskProjectPanel(wx.Panel):
    """Panel representing a single project's tasks with native accessible controls."""

    def __init__(self, parent, filename, settings=None):
        super().__init__(parent)
        self.filename = filename
        self.settings = settings
        self.base_dir = get_base_dir()
        self.model = ProjectModel(self.filename, self.settings, self.base_dir)
        self.visible_indices = []

        sizer = wx.BoxSizer(wx.VERTICAL)

        filter_box = wx.BoxSizer(wx.HORIZONTAL)
        filter_label = wx.StaticText(self, label="&Filter:")
        self.search_input = wx.TextCtrl(self)
        self.search_input.Bind(wx.EVT_TEXT, self.on_search)
        filter_box.Add(filter_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        filter_box.Add(self.search_input, 1, wx.EXPAND)
        sizer.Add(filter_box, 0, wx.EXPAND | wx.ALL, 5)

        tasks_label = wx.StaticText(self, label="&Tasks:")
        self.task_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.task_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.dispatch_command("archive"))
        self.task_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        sizer.Add(tasks_label, 0, wx.LEFT | wx.TOP, 5)
        sizer.Add(self.task_list, 1, wx.EXPAND | wx.ALL, 5)

        add_box = wx.BoxSizer(wx.HORIZONTAL)
        add_label = wx.StaticText(self, label="&Add:")
        self.new_task_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.new_task_input.Bind(wx.EVT_TEXT_ENTER, self.on_add_task)
        add_box.Add(add_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        add_box.Add(self.new_task_input, 1, wx.EXPAND)
        sizer.Add(add_box, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

        if self.model.load_tasks():
            self.update_display()
        self.setup_auto_save()

    @property
    def all_tasks(self):
        return self.model.all_tasks

    @property
    def pinned_tasks(self):
        return self.model.pinned_tasks

    @property
    def archive_file(self):
        return self.model.archive_file

    @property
    def trash_file(self):
        return self.model.trash_file

    def on_add_task(self, event=None):
        txt = self.new_task_input.GetValue().strip()
        if self.model.add_task(txt):
            self.new_task_input.Clear()
            self.update_display(self.search_input.GetValue())

    def on_search(self, event=None):
        self.update_display(self.search_input.GetValue())

    def update_display(self, filter_text=""):
        self.task_list.Clear()
        entries = self.model.get_filtered_task_entries(filter_text)
        lim = self.settings.get("search", "lazy_load_threshold", 100) if self.settings else 100
        if len(entries) > lim and not filter_text:
            entries = entries[:lim]
        self.visible_indices = [idx for idx, _ in entries]
        self.task_list.Set([t for _, t in entries])
        self.Layout()

    def _handle_archive(self, sel, txt):
        if self._confirm("Archive task?", "confirm_on_archive", False) and self.model.archive_task(txt):
            self.update_display(self.search_input.GetValue())
            new_sel = min(sel, self.task_list.GetCount() - 1)
            if new_sel >= 0:
                self.task_list.SetSelection(new_sel)
            self.task_list.SetFocus()

    def _handle_delete(self, sel, txt):
        if self._confirm("Delete task?", "confirm_on_delete", True) and self.model.delete_task(txt):
            self.update_display(self.search_input.GetValue())
            new_sel = min(sel, self.task_list.GetCount() - 1)
            if new_sel >= 0:
                self.task_list.SetSelection(new_sel)
            self.task_list.SetFocus()

    def _handle_edit(self, sel, txt):
        dlg = wx.TextEntryDialog(self, "Edit task:", "Edit", txt)
        if dlg.ShowModal() == wx.ID_OK and self.model.edit_task(txt, dlg.GetValue().strip()):
            self.update_display(self.search_input.GetValue())
            self.task_list.SetSelection(sel)
        dlg.Destroy()
        self.task_list.SetFocus()

    def _handle_copy(self, txt):
        if pyperclip:
            pyperclip.copy(txt)
        self.task_list.SetFocus()

    def _handle_pin(self, sel, txt):
        if self.model.toggle_pin(txt):
            self.update_display(self.search_input.GetValue())
            self.task_list.SetSelection(sel)
        self.task_list.SetFocus()

    def _handle_move(self, sel, direction):
        if 0 <= sel + direction < len(self.visible_indices):
            model_idx = self.visible_indices[sel]
            if self.model.move_task(model_idx, direction):
                self.update_display(self.search_input.GetValue())
                target_idx = model_idx + direction
                if target_idx in self.visible_indices:
                    self.task_list.SetSelection(self.visible_indices.index(target_idx))
        self.task_list.SetFocus()

    def dispatch_command(self, cmd):
        if cmd == "add":
            self.on_add_task()
            return
        if cmd == "undo":
            if self.model.undo():
                self.update_display(self.search_input.GetValue())
            return

        sel = self.task_list.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        txt = self.task_list.GetString(sel)

        handlers = {
            "archive": lambda: self._handle_archive(sel, txt),
            "complete": lambda: self._handle_archive(sel, txt),
            "delete": lambda: self._handle_delete(sel, txt),
            "edit": lambda: self._handle_edit(sel, txt),
            "copy": lambda: self._handle_copy(txt),
            "pin": lambda: self._handle_pin(sel, txt),
            "move_up": lambda: self._handle_move(sel, -1),
            "move_down": lambda: self._handle_move(sel, 1),
        }
        action = handlers.get(cmd)
        if action:
            action()

    def _confirm(self, msg, key, default):
        if self.settings and not self.settings.get("behavior", key, default):
            return True
        return wx.MessageBox(msg, "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES

    def archive_task(self, txt):
        idx = self.task_list.FindString(txt)
        if idx != wx.NOT_FOUND:
            self.task_list.SetSelection(idx)
            self.dispatch_command("archive")

    def delete_task_final(self, txt):
        idx = self.task_list.FindString(txt)
        if idx != wx.NOT_FOUND:
            self.task_list.SetSelection(idx)
            self.dispatch_command("delete")

    def undo(self):
        self.dispatch_command("undo")

    def on_context_menu(self, event):
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            item = self.task_list.HitTest(self.task_list.ScreenToClient(pos))
            if item != wx.NOT_FOUND:
                self.task_list.SetSelection(item)
        if self.task_list.GetSelection() != wx.NOT_FOUND:
            menu = wx.Menu()
            for lbl, cmd in [
                ("Mark Complete (Ctrl+M)", "complete"),
                ("Pin ⭐", "pin"),
                ("Edit (F2)", "edit"),
                ("Copy (Ctrl+C)", "copy"),
                ("Delete (Del)", "delete"),
            ]:
                mi = menu.Append(wx.ID_ANY, lbl)
                self.Bind(wx.EVT_MENU, lambda e, c=cmd: self.dispatch_command(c), mi)
            self.PopupMenu(menu)
            menu.Destroy()

    def setup_auto_save(self):
        interval = self.settings.get("behavior", "auto_save_interval", 2) if self.settings else 2
        self.timer = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER,
            lambda e: self.model.save_tasks_atomic() if self.model.has_unsaved_changes else None,
            self.timer,
        )
        self.Bind(
            wx.EVT_WINDOW_DESTROY,
            lambda e: self.timer.Stop() if e.GetEventObject() is self else e.Skip(),
        )
        self.timer.Start(interval * 1000)


# ==========================================
# Dialogs (Global Search, Project Manager, Settings)
# ==========================================
class GlobalSearchDialog(wx.Dialog):
    """Accessible UI adapter over the SearchEngine deep module."""

    def __init__(self, parent, projects_dir_or_search_engine, settings=None):
        super().__init__(parent, title="Global Search", size=(600, 420))
        self.parent = parent
        self.settings = settings

        if isinstance(projects_dir_or_search_engine, SearchEngine):
            self.search_engine = projects_dir_or_search_engine
        elif isinstance(projects_dir_or_search_engine, ProjectWorkspace):
            self.search_engine = SearchEngine(projects_dir_or_search_engine)
        else:
            self.search_engine = SearchEngine(ProjectWorkspace(projects_dir_or_search_engine))

        self.last_results = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        search_box = wx.BoxSizer(wx.HORIZONTAL)
        search_box.Add(wx.StaticText(panel, label="&Search:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.search_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search)
        search_box.Add(self.search_ctrl, 1, wx.EXPAND)
        sizer.Add(search_box, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Results:"), 0, wx.LEFT, 10)
        self.results_list = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_open_task)
        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 10)

        close_btn = wx.Button(panel, wx.ID_CANCEL, label="&Close")
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)

    def on_search(self, event=None):
        q = self.search_ctrl.GetValue().strip()
        self.results_list.Clear()
        if len(q) < 2:
            self.last_results = []
            return
        case_sensitive = self.settings.get("search", "case_sensitive", False) if self.settings else False
        self.last_results = self.search_engine.search(q, case_sensitive=case_sensitive)
        self.results_list.Set([r["formatted"] for r in self.last_results])

    def on_open_task(self, event=None):
        sel = self.results_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.last_results):
            result = self.last_results[sel]
            filename = result["filename"]
            self.parent.open_or_select_project(filename)
            self.EndModal(wx.ID_OK)


class ProjectManagerDialog(wx.Dialog):
    """Accessible UI adapter over the ProjectWorkspace deep module."""

    def __init__(self, parent, projects_dir_or_workspace):
        super().__init__(parent, title="Project Manager", size=(650, 420))
        self.parent = parent
        if isinstance(projects_dir_or_workspace, ProjectWorkspace):
            self.workspace = projects_dir_or_workspace
        else:
            self.workspace = ProjectWorkspace(projects_dir_or_workspace)

        self.projects = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(panel, label="&Projects:"), 0, wx.ALL, 5)

        self.project_list = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.project_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.on_open())
        sizer.Add(self.project_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in [
            ("&New", self.on_new),
            ("&Open", self.on_open),
            ("&Pin ⭐", self.on_pin),
            ("Move &Up", lambda e: self.on_move(-1)),
            ("Move &Down", lambda e: self.on_move(1)),
            ("&Rename", self.on_rename),
            ("&Delete", self.on_delete),
            ("&Close", lambda e: self.EndModal(wx.ID_CANCEL)),
        ]:
            btn = wx.Button(panel, label=label)
            btn.Bind(wx.EVT_BUTTON, handler)
            btn_sizer.Add(btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.refresh_list()

    def refresh_list(self):
        self.projects = self.workspace.list_projects()
        self.project_list.Set(
            [f"{'⭐ ' if p['pinned'] else ''}{p['display']}{' (daily)' if p['readonly'] else ''}" for p in self.projects]
        )

    def on_new(self, event=None):
        dlg = wx.TextEntryDialog(self, "Project name:", "New Project")
        if dlg.ShowModal() == wx.ID_OK:
            created = self.workspace.create_project(dlg.GetValue())
            if created:
                self.refresh_list()
        dlg.Destroy()

    def on_open(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.projects):
            p = self.projects[sel]
            self.parent.open_or_select_project(p["filename"])
            self.EndModal(wx.ID_OK)

    def on_pin(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and not self.projects[sel]["readonly"]:
            self.workspace.toggle_pin(self.projects[sel]["filename"])
            self.refresh_list()
            self.project_list.SetSelection(sel)

    def on_move(self, direction):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        if self.workspace.move_project(sel, direction):
            self.refresh_list()
            self.project_list.SetSelection(sel + direction)

    def on_rename(self, event=None):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND or self.projects[sel]["readonly"]:
            return
        p = self.projects[sel]
        dlg = wx.TextEntryDialog(self, "New project name:", "Rename Project", p["display"])
        if dlg.ShowModal() == wx.ID_OK:
            renamed = self.workspace.rename_project(p["filename"], dlg.GetValue())
            if renamed:
                self.refresh_list()
        dlg.Destroy()

    def on_delete(self, event=None):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND or self.projects[sel]["readonly"]:
            return
        p = self.projects[sel]
        if wx.MessageBox(f"Delete project '{p['display']}'?", "Confirm Delete", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            if self.workspace.delete_project(p["filename"]):
                self.refresh_list()


class SettingsDialog(wx.Dialog):
    """Accessible dialog for managing settings."""

    def __init__(self, parent, settings_manager):
        super().__init__(parent, title="Settings", size=(480, 360))
        self.settings = settings_manager

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.confirm_archive_cb = wx.CheckBox(panel, label="Confirm on &archive")
        self.confirm_delete_cb = wx.CheckBox(panel, label="Confirm on &delete")
        self.confirm_archive_cb.SetValue(self.settings.get("behavior", "confirm_on_archive", False))
        self.confirm_delete_cb.SetValue(self.settings.get("behavior", "confirm_on_delete", True))
        sizer.Add(self.confirm_archive_cb, 0, wx.ALL, 8)
        sizer.Add(self.confirm_delete_cb, 0, wx.ALL, 8)

        spin_box = wx.BoxSizer(wx.HORIZONTAL)
        spin_box.Add(wx.StaticText(panel, label="Auto-save interval (&seconds):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.auto_save_spin = wx.SpinCtrl(
            panel, min=1, max=60, initial=self.settings.get("behavior", "auto_save_interval", 2)
        )
        spin_box.Add(self.auto_save_spin, 0)
        sizer.Add(spin_box, 0, wx.ALL, 8)

        lang_box = wx.BoxSizer(wx.HORIZONTAL)
        lang_box.Add(wx.StaticText(panel, label="&Language:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.lang_choice = wx.Choice(panel, choices=["English", "العربية"])
        self.lang_choice.SetSelection(1 if self.settings.get("general", "language", "en") == "ar" else 0)
        lang_box.Add(self.lang_choice, 1, wx.EXPAND)
        sizer.Add(lang_box, 0, wx.EXPAND | wx.ALL, 8)

        sizer.AddStretchSpacer()
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        reset_btn = wx.Button(panel, label="&Reset Defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        save_btn = wx.Button(panel, wx.ID_OK, label="&Save")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancel")
        btn_sizer.Add(reset_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(cancel_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(sizer)

    def on_save(self, event=None):
        self.settings.set("behavior", "confirm_on_archive", self.confirm_archive_cb.GetValue())
        self.settings.set("behavior", "confirm_on_delete", self.confirm_delete_cb.GetValue())
        self.settings.set("behavior", "auto_save_interval", self.auto_save_spin.GetValue())
        self.settings.set("general", "language", "ar" if self.lang_choice.GetSelection() == 1 else "en")
        self.settings.save()
        self.EndModal(wx.ID_OK)

    def on_reset(self, event=None):
        if wx.MessageBox("Reset settings to default?", "Confirm Reset", wx.YES_NO) == wx.YES:
            self.settings.reset_to_defaults()
            self.confirm_archive_cb.SetValue(self.settings.get("behavior", "confirm_on_archive", False))
            self.confirm_delete_cb.SetValue(self.settings.get("behavior", "confirm_on_delete", True))
            self.auto_save_spin.SetValue(self.settings.get("behavior", "auto_save_interval", 2))
            self.lang_choice.SetSelection(1 if self.settings.get("general", "language", "en") == "ar" else 0)


# ==========================================
# Main Application Frame
# ==========================================
class MainFrame(wx.Frame):
    """Main window coordinating project tabs, shortcuts, and global toolbar."""

    def __init__(self):
        super().__init__(None, title="Dar Tasks", size=(800, 600))
        self.base_dir = get_base_dir()
        self.projects_dir = os.path.join(self.base_dir, "projects")
        self.backups_dir = os.path.join(self.base_dir, "backups")
        os.makedirs(self.projects_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

        self.workspace = ProjectWorkspace(self.projects_dir)
        self.search_engine = SearchEngine(self.workspace)
        self.settings = SettingsManager(self.base_dir)
        self.translator = Translator(self.settings)
        self.backup_mgr = BackupManager(self.base_dir, self.projects_dir, self.backups_dir, self.settings)
        self.backup_mgr.setup_daily_tasks()

        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for key, mnemonic, handler in [
            ("proj_mgr", "P", lambda e: self.on_project_manager()),
            ("search", "S", lambda e: self.on_global_search()),
            ("harvest", "H", lambda e: self.on_harvest()),
            ("open_arch", "O", lambda e: self.on_open_archive()),
            ("settings", "T", lambda e: self.on_settings()),
        ]:
            btn = wx.Button(self.panel, label=f"&{self.translator._(key)}")
            btn.SetToolTip(f"{self.translator._(key)} (Alt+{mnemonic})")
            btn.Bind(wx.EVT_BUTTON, handler)
            self.toolbar_sizer.Add(btn, 0, wx.ALL, 3)
        sizer.Add(self.toolbar_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.notebook = wx.Notebook(self.panel)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.panel.SetSizer(sizer)

        self.setup_accelerators()
        self.load_all_projects()

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Show()

    def open_or_select_project(self, filename):
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if getattr(page, "filename", "").endswith(filename):
                self.notebook.SetSelection(i)
                return
        path = self.workspace.get_project_path(filename)
        if os.path.exists(path):
            title = get_project_display_name(filename, self.translator)
            self.notebook.AddPage(TaskProjectPanel(self.notebook, path, self.settings), title)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)

    def load_all_projects(self):
        projects = self.workspace.list_projects()
        for p in projects:
            if p["filename"] == DAILY_TEMPLATE_FILENAME:
                continue
            title = get_project_display_name(p["filename"], self.translator)
            self.notebook.AddPage(TaskProjectPanel(self.notebook, p["path"], self.settings), title)

    def setup_accelerators(self):
        shortcuts = [
            (wx.ACCEL_CTRL, wx.WXK_UP, 1001, "move_up"),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, 1002, "move_down"),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, 1003, "delete"),
            (wx.ACCEL_NORMAL, wx.WXK_F2, 1004, "edit"),
            (wx.ACCEL_CTRL, ord("Z"), 1005, "undo"),
            (wx.ACCEL_CTRL, ord("M"), 1009, "complete"),
            (wx.ACCEL_CTRL, wx.WXK_TAB, 1006, "next_tab"),
            (wx.ACCEL_CTRL, ord("C"), 1007, "copy"),
            (wx.ACCEL_CTRL, ord("F"), 1008, "search"),
        ]
        accels = []
        for flags, key, uid, cmd in shortcuts:
            accels.append((flags, key, uid))
            if cmd == "next_tab":
                self.Bind(wx.EVT_MENU, lambda e: self.next_tab(), id=uid)
            elif cmd == "search":
                self.Bind(wx.EVT_MENU, lambda e: self.on_global_search(), id=uid)
            else:
                self.Bind(wx.EVT_MENU, lambda e, c=cmd: self.dispatch_to_active_tab(c), id=uid)
        for i in range(1, 10):
            uid = 1100 + i
            accels.append((wx.ACCEL_CTRL, ord(str(i)), uid))
            self.Bind(wx.EVT_MENU, lambda e, idx=i - 1: self.select_tab(idx), id=uid)
        self.SetAcceleratorTable(wx.AcceleratorTable(accels))

    def dispatch_to_active_tab(self, cmd):
        page = self.notebook.GetCurrentPage()
        if isinstance(page, TaskProjectPanel):
            page.dispatch_command(cmd)

    def select_tab(self, index):
        if 0 <= index < self.notebook.GetPageCount():
            self.notebook.SetSelection(index)
            wx.CallAfter(self.notebook.GetCurrentPage().task_list.SetFocus)

    def next_tab(self):
        cnt = self.notebook.GetPageCount()
        if cnt > 0:
            self.select_tab((self.notebook.GetSelection() + 1) % cnt)

    def on_project_manager(self):
        dlg = ProjectManagerDialog(self, self.workspace)
        dlg.ShowModal()
        dlg.Destroy()

    def on_global_search(self):
        dlg = GlobalSearchDialog(self, self.search_engine, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_harvest(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        arch = self.settings.get("backup", "archive_location") or os.path.join(self.base_dir, DEFAULT_ARCHIVE_NAME)
        done = []
        if os.path.exists(arch):
            with open(arch, "r", encoding="utf-8", errors="replace") as f:
                done = [line for line in f if line.startswith(f"[{today}")]
        wx.MessageBox("".join(done) if done else self.translator._("no_harvest"), self.translator._("arch_title"), wx.OK)

    def on_open_archive(self):
        arch = self.settings.get("backup", "archive_location") or os.path.join(self.base_dir, DEFAULT_ARCHIVE_NAME)
        if os.path.exists(arch):
            if sys.platform == "win32":
                os.startfile(arch)
            else:
                subprocess.Popen(["xdg-open", arch])
        else:
            wx.MessageBox(self.translator._("no_arch"), "Info", wx.OK)

    def on_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.translator.setup_translations()
        dlg.Destroy()

    def on_close(self, event):
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if isinstance(page, TaskProjectPanel) and page.model.has_unsaved_changes:
                page.model.save_tasks_atomic()
        event.Skip()


# ==========================================
# Application Entry Point
# ==========================================
if __name__ == "__main__":
    app = wx.App()
    name = f"DarTasks-{wx.GetUserId()}"
    instance_checker = wx.SingleInstanceChecker(name)
    if instance_checker.IsAnotherRunning():
        wx.MessageBox(
            "An instance of Dar Tasks is already running.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        sys.exit(0)

    MainFrame()
    app.MainLoop()
