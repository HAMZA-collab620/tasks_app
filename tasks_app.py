"""
Dar Tasks - Accessible Task and Project Management Application.
Streamlined presentation adapter layer utilizing wxPython native Win32 controls.
Delegates all domain persistence and invariants to core_models and dialogs.
"""

from pathlib import Path
import subprocess
import sys
import wx

try:
    import pyperclip
except ImportError:
    pyperclip = None

from core_models import (
    DAILY_FILENAME,
    DAILY_TEMPLATE_FILENAME,
    DEFAULT_ARCHIVE_NAME,
    BackupManager,
    ProjectModel,
    ProjectWorkspace,
    SearchEngine,
    SettingsManager,
    Task,
    Translator,
    get_base_dir,
    get_project_display_name,
)
from dialogs import (
    GlobalSearchDialog,
    ProjectManagerDialog,
    SettingsDialog,
)

# ==========================================
# Presentation Constants & Styling
# ==========================================
BG_COLOR = wx.Colour(30, 30, 30)
FG_COLOR = wx.Colour(240, 240, 240)
ACCENT_COLOR = wx.Colour(45, 45, 45)
FONT_SIZE = 14


# ==========================================
# Task Project Panel (Single Tab Presentation)
# ==========================================
class TaskProjectPanel(wx.Panel):
    """Panel representing a single project tab with native accessible controls."""

    def __init__(self, parent, filename, settings=None):
        super().__init__(parent)
        self.filename = str(filename)
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

    def on_add_task(self, event=None):
        new_title = self.new_task_input.GetValue().strip()
        if self.model.add_task(new_title):
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
        self.task_list.Set([entry_text for _, entry_text in entries])
        self.Layout()

    def _handle_archive(self, sel, task_text):
        if self._confirm("Archive task?", "confirm_on_archive", False) and self.model.archive_task(task_text):
            self.update_display(self.search_input.GetValue())
            new_sel = min(sel, self.task_list.GetCount() - 1)
            if new_sel >= 0:
                self.task_list.SetSelection(new_sel)
            self.task_list.SetFocus()

    def _handle_delete(self, sel, task_text):
        if self._confirm("Delete task?", "confirm_on_delete", True) and self.model.delete_task(task_text):
            self.update_display(self.search_input.GetValue())
            new_sel = min(sel, self.task_list.GetCount() - 1)
            if new_sel >= 0:
                self.task_list.SetSelection(new_sel)
            self.task_list.SetFocus()

    def _handle_edit(self, sel, task_text):
        dlg = wx.TextEntryDialog(self, "Edit task:", "Edit", task_text)
        if dlg.ShowModal() == wx.ID_OK and self.model.edit_task(task_text, dlg.GetValue().strip()):
            self.update_display(self.search_input.GetValue())
            self.task_list.SetSelection(sel)
        dlg.Destroy()
        self.task_list.SetFocus()

    def _handle_copy(self, task_text):
        if pyperclip:
            pyperclip.copy(task_text)
        self.task_list.SetFocus()

    def _handle_pin(self, sel, task_text):
        if self.model.toggle_pin(task_text):
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
        task_text = self.task_list.GetString(sel)

        handlers = {
            "archive": lambda: self._handle_archive(sel, task_text),
            "complete": lambda: self._handle_archive(sel, task_text),
            "delete": lambda: self._handle_delete(sel, task_text),
            "edit": lambda: self._handle_edit(sel, task_text),
            "copy": lambda: self._handle_copy(task_text),
            "pin": lambda: self._handle_pin(sel, task_text),
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

    def archive_task(self, task_text):
        idx = self.task_list.FindString(task_text)
        if idx != wx.NOT_FOUND:
            self.task_list.SetSelection(idx)
            self.dispatch_command("archive")

    def delete_task_final(self, task_text):
        idx = self.task_list.FindString(task_text)
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
# Main Application Frame
# ==========================================
class MainFrame(wx.Frame):
    """Main window coordinating project tabs, shortcuts, and global toolbar."""

    def __init__(self):
        super().__init__(None, title="Dar Tasks", size=(800, 600))
        self.base_dir = get_base_dir()
        self.projects_dir = self.base_dir / "projects"
        self.backups_dir = self.base_dir / "backups"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

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

    def open_or_select_project(self, filename: str):
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if getattr(page, "filename", "").endswith(filename):
                self.notebook.SetSelection(i)
                return
        path = self.workspace.get_project_path(filename)
        if path.exists():
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
        done = ProjectModel.get_today_harvest(self.base_dir, self.settings)
        message = "\n".join(done) if done else self.translator._("no_harvest")
        wx.MessageBox(message, self.translator._("arch_title"), wx.OK)

    def on_open_archive(self):
        arch_setting = self.settings.get("backup", "archive_location") if self.settings else ""
        arch = Path(arch_setting) if arch_setting else self.base_dir / DEFAULT_ARCHIVE_NAME
        if arch.exists():
            if sys.platform == "win32":
                import os
                os.startfile(str(arch))
            else:
                subprocess.Popen(["xdg-open", str(arch)])
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
