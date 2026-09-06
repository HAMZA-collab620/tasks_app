"""
Dar Tasks - Accessible Task and Project Management Application.
Streamlined presentation adapter layer utilizing wxPython native Win32 controls.
Delegates all domain persistence and invariants to core_models and dialogs.
"""

from pathlib import Path
import sys
import wx

from core_models import (
    DAILY_FILENAME,
    DAILY_TEMPLATE_FILENAME,
    BackupManager,
    ProjectModel,
    ProjectWorkspace,
    SearchEngine,
    SettingsManager,
    Translator,
    get_base_dir,
    get_project_display_name,
    open_file_in_editor,
)
from dialogs import GlobalSearchDialog, ProjectManagerDialog, SettingsDialog


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using wxPython native Win32 clipboard."""
    if wx.TheClipboard.Open():
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Flush()
            return True
        finally:
            wx.TheClipboard.Close()
    return False


class TaskProjectPanel(wx.Panel):
    """Panel representing a single project tab with native accessible controls."""

    def __init__(self, parent, filename: str | Path, settings=None):
        super().__init__(parent)
        self.filename = Path(filename)
        self.settings = settings
        self.translator = Translator(self.settings)
        self.model = ProjectModel(self.filename, self.settings, get_base_dir())
        self.visible_indices: list[int] = []

        sizer = wx.BoxSizer(wx.VERTICAL)
        frow = wx.BoxSizer(wx.HORIZONTAL)
        frow.Add(
            wx.StaticText(self, label=f"&{self.translator._('filter')}"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.search_input = wx.TextCtrl(self)
        self.search_input.SetName("Filter")
        self.search_input.Bind(
            wx.EVT_TEXT, lambda e: self.update_display(self.search_input.GetValue())
        )
        frow.Add(self.search_input, 1, wx.EXPAND)
        sizer.Add(frow, 0, wx.EXPAND | wx.ALL, 5)

        sizer.Add(
            wx.StaticText(self, label=f"&{self.translator._('tasks')}"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        self.task_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.task_list.SetName("Tasks")
        self.task_list.Bind(
            wx.EVT_LISTBOX_DCLICK, lambda e: self.dispatch_command("archive")
        )
        self.task_list.Bind(
            wx.EVT_KEY_DOWN,
            lambda e: (
                self.dispatch_command("archive")
                if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
                else e.Skip()
            ),
        )
        self.task_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        sizer.Add(self.task_list, 1, wx.EXPAND | wx.ALL, 5)

        arow = wx.BoxSizer(wx.HORIZONTAL)
        arow.Add(
            wx.StaticText(self, label=f"&{self.translator._('add')}"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.new_task_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.new_task_input.SetName("Add Task")
        self.new_task_input.Bind(wx.EVT_TEXT_ENTER, self.on_add_task)
        arow.Add(self.new_task_input, 1, wx.EXPAND)
        sizer.Add(arow, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        if self.model.load_tasks():
            self.update_display()
        self.setup_auto_save()

    def on_add_task(self, event=None):
        if self.model.add_task(self.new_task_input.GetValue().strip()):
            self.new_task_input.Clear()
            self.update_display(self.search_input.GetValue())

    def update_display(self, filter_text: str = ""):
        self.task_list.Clear()
        entries = self.model.get_filtered_task_entries(filter_text)
        self.visible_indices = [idx for idx, _ in entries]
        self.task_list.Set([t for _, t in entries])
        self.Layout()

    def _confirm(self, msg_key: str, setting_key: str, default_val: bool) -> bool:
        if self.settings and not self.settings.get("behavior", setting_key, default_val):
            return True
        return (
            wx.MessageBox(
                self.translator._(msg_key),
                self.translator._("settings"),
                wx.YES_NO | wx.ICON_QUESTION,
            )
            == wx.YES
        )

    def _adjust_selection_after_removal(self, sel: int):
        new_sel = min(sel, self.task_list.GetCount() - 1)
        if new_sel >= 0:
            self.task_list.SetSelection(new_sel)

    def _handle_archive_command(self, m_idx: int, sel: int):
        if self._confirm("confirm_archive", "confirm_on_archive", False):
            if self.model.archive_task(m_idx):
                self.update_display(self.search_input.GetValue())
                self._adjust_selection_after_removal(sel)

    def _handle_delete_command(self, m_idx: int, sel: int):
        if self._confirm("confirm_delete", "confirm_on_delete", True):
            if self.model.delete_task(m_idx):
                self.update_display(self.search_input.GetValue())
                self._adjust_selection_after_removal(sel)

    def _handle_edit_command(self, m_idx: int, sel: int, task_text: str):
        prompt = self.translator._("edit_task")
        dlg = wx.TextEntryDialog(self, prompt, prompt, task_text)
        if dlg.ShowModal() == wx.ID_OK and self.model.edit_task(
            m_idx, dlg.GetValue().strip()
        ):
            self.update_display(self.search_input.GetValue())
            self.task_list.SetSelection(sel)
        dlg.Destroy()

    def _handle_pin_command(self, m_idx: int, sel: int):
        task = self.model.tasks[m_idx]
        if self.model.toggle_pin(m_idx):
            self.update_display(self.search_input.GetValue())
            try:
                new_idx = self.model.tasks.index(task)
                if new_idx in self.visible_indices:
                    self.task_list.SetSelection(self.visible_indices.index(new_idx))
            except (ValueError, IndexError):
                self.task_list.SetSelection(sel)

    def _handle_move_command(self, m_idx: int, sel: int, direction: int):
        if 0 <= sel + direction < len(self.visible_indices):
            if self.model.move_task(m_idx, direction):
                self.update_display(self.search_input.GetValue())
                tgt = m_idx + direction
                if tgt in self.visible_indices:
                    self.task_list.SetSelection(self.visible_indices.index(tgt))

    def _handle_undo_command(self):
        if self.model.undo():
            self.update_display(self.search_input.GetValue())

    def dispatch_command(self, cmd: str):
        if cmd == "add":
            return self.on_add_task()
        if cmd == "undo":
            return self._handle_undo_command()
        if cmd == "open_notepad":
            return open_file_in_editor(self.filename)

        sel = self.task_list.GetSelection()
        if sel == wx.NOT_FOUND or sel >= len(self.visible_indices):
            return
        m_idx, task_text = self.visible_indices[sel], self.task_list.GetString(sel)

        handlers = {
            "archive": lambda: self._handle_archive_command(m_idx, sel),
            "complete": lambda: self._handle_archive_command(m_idx, sel),
            "delete": lambda: self._handle_delete_command(m_idx, sel),
            "edit": lambda: self._handle_edit_command(m_idx, sel, task_text),
            "copy": lambda: copy_to_clipboard(task_text),
            "pin": lambda: self._handle_pin_command(m_idx, sel),
            "move_up": lambda: self._handle_move_command(m_idx, sel, -1),
            "move_down": lambda: self._handle_move_command(m_idx, sel, 1),
        }
        handler = handlers.get(cmd)
        if handler:
            handler()
        self.task_list.SetFocus()

    def on_context_menu(self, event):
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            item = self.task_list.HitTest(self.task_list.ScreenToClient(pos))
            if item != wx.NOT_FOUND:
                self.task_list.SetSelection(item)
        if self.task_list.GetSelection() != wx.NOT_FOUND:
            menu = wx.Menu()
            for lbl, cmd in [
                (self.translator._("Mark Complete (Ctrl+M)"), "complete"),
                (self.translator._("Pin ⭐"), "pin"),
                (self.translator._("Edit (F2)"), "edit"),
                (self.translator._("Copy (Ctrl+C)"), "copy"),
                (self.translator._("Delete (Del)"), "delete"),
                (self.translator._("Open in Notepad (F4)"), "open_notepad"),
            ]:
                mi = menu.Append(wx.ID_ANY, lbl)
                self.Bind(wx.EVT_MENU, lambda e, c=cmd: self.dispatch_command(c), mi)
            self.PopupMenu(menu)
            menu.Destroy()

    def setup_auto_save(self):
        interval = (
            self.settings.get("behavior", "auto_save_interval", 2)
            if self.settings
            else 2
        )
        self.timer = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER,
            lambda e: (
                self.model.save_tasks_atomic()
                if self.model.has_unsaved_changes
                else None
            ),
            self.timer,
        )
        self.Bind(
            wx.EVT_WINDOW_DESTROY,
            lambda e: self.timer.Stop() if e.GetEventObject() is self else e.Skip(),
        )
        self.timer.Start(interval * 1000)


class MainFrame(wx.Frame):
    """Main window coordinating project tabs, shortcuts, and global toolbar."""

    def __init__(self):
        super().__init__(None, title="Dar Tasks", size=(800, 600))
        self.base_dir = get_base_dir()
        self.projects_dir, self.backups_dir = (
            self.base_dir / "projects",
            self.base_dir / "backups",
        )
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self.workspace = ProjectWorkspace(self.projects_dir)
        self.search_engine = SearchEngine(self.workspace)
        self.settings = SettingsManager(self.base_dir)
        self.translator = Translator(self.settings)
        self.backup_mgr = BackupManager(
            self.base_dir, self.projects_dir, self.backups_dir, self.settings
        )
        self.backup_mgr.setup_daily_tasks()

        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tools = [
            (
                "proj_mgr",
                "P",
                lambda e: self._show_dialog(ProjectManagerDialog, self.workspace),
            ),
            (
                "search",
                "S",
                lambda e: self._show_dialog(
                    GlobalSearchDialog, self.search_engine, self.settings
                ),
            ),
            ("open_notepad", "N", lambda e: self.on_open_active_project_in_notepad()),
            ("harvest", "H", lambda e: self.on_harvest()),
            ("open_arch", "O", lambda e: self.on_open_archive()),
            ("settings", "T", lambda e: self.on_settings()),
        ]
        for key, mnem, handler in tools:
            btn = wx.Button(self.panel, label=f"&{self.translator._(key)}")
            btn.SetToolTip(f"{self.translator._(key)} (Alt+{mnem})")
            btn.Bind(wx.EVT_BUTTON, handler)
            self.toolbar_sizer.Add(btn, 0, wx.ALL, 3)
        sizer.Add(self.toolbar_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.notebook = wx.Notebook(self.panel)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.panel.SetSizer(sizer)

        self.setup_accelerators()
        self.load_all_projects()

        self.Bind(wx.EVT_ACTIVATE, self.on_activate)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Show()

    def _show_dialog(self, dlg_cls, *args):
        dlg = dlg_cls(self, *args)
        res = dlg.ShowModal()
        dlg.Destroy()
        return res

    def on_activate(self, event):
        if event.GetActive():
            if self.backup_mgr.check_and_rollover_daily_tasks():
                self.reload_daily_tab()
            for i in range(self.notebook.GetPageCount()):
                page = self.notebook.GetPage(i)
                if isinstance(page, TaskProjectPanel) and page.model.reload_if_modified():
                    page.update_display(page.search_input.GetValue())
        event.Skip()

    def reload_daily_tab(self):
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if (
                isinstance(page, TaskProjectPanel)
                and page.filename.name == DAILY_FILENAME
            ):
                page.model.load_tasks()
                page.update_display(page.search_input.GetValue())

    def on_open_active_project_in_notepad(self):
        page = self.notebook.GetCurrentPage()
        if isinstance(page, TaskProjectPanel):
            open_file_in_editor(page.filename)

    def open_or_select_project(self, filename: str):
        target = self.workspace.get_project_path(filename).resolve()
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if isinstance(page, TaskProjectPanel) and page.filename.resolve() == target:
                self.notebook.SetSelection(i)
                return
        path = self.workspace.get_project_path(filename)
        if path.exists():
            self.notebook.AddPage(
                TaskProjectPanel(self.notebook, path, self.settings),
                get_project_display_name(filename, self.translator),
            )
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)

    def on_project_renamed(self, old_fn: str, new_fn: str):
        old_p = self.workspace.get_project_path(old_fn).resolve()
        new_p = self.workspace.get_project_path(new_fn)
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if isinstance(page, TaskProjectPanel) and page.filename.resolve() == old_p:
                page.filename, page.model.filename = new_p, new_p
                self.notebook.SetPageText(
                    i, get_project_display_name(new_fn, self.translator)
                )
                break

    def on_project_deleted(self, filename: str):
        p_path = self.workspace.get_project_path(filename).resolve()
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if isinstance(page, TaskProjectPanel) and page.filename.resolve() == p_path:
                page.model.has_unsaved_changes = False
                page.timer.Stop()
                self.notebook.DeletePage(i)
                break

    def load_all_projects(self):
        for proj in self.workspace.list_projects():
            if proj["filename"] != DAILY_TEMPLATE_FILENAME:
                self.notebook.AddPage(
                    TaskProjectPanel(self.notebook, proj["path"], self.settings),
                    get_project_display_name(proj["filename"], self.translator),
                )

    def setup_accelerators(self):
        accels = [
            (wx.ACCEL_CTRL, wx.WXK_UP, 1001),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, 1002),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, 1003),
            (wx.ACCEL_NORMAL, wx.WXK_F2, 1004),
            (wx.ACCEL_CTRL, ord("Z"), 1005),
            (wx.ACCEL_CTRL, ord("M"), 1009),
            (wx.ACCEL_CTRL, wx.WXK_TAB, 1006),
            (wx.ACCEL_CTRL, ord("C"), 1007),
            (wx.ACCEL_CTRL, ord("F"), 1008),
            (wx.ACCEL_NORMAL, wx.WXK_F4, 1010),
        ]
        cmd_map = {
            1001: "move_up",
            1002: "move_down",
            1003: "delete",
            1004: "edit",
            1005: "undo",
            1009: "complete",
            1007: "copy",
        }
        for uid, cmd in cmd_map.items():
            self.Bind(
                wx.EVT_MENU, lambda e, c=cmd: self.dispatch_to_active_tab(c), id=uid
            )
        self.Bind(wx.EVT_MENU, lambda e: self.next_tab(), id=1006)
        self.Bind(
            wx.EVT_MENU,
            lambda e: self._show_dialog(
                GlobalSearchDialog, self.search_engine, self.settings
            ),
            id=1008,
        )
        self.Bind(
            wx.EVT_MENU, lambda e: self.on_open_active_project_in_notepad(), id=1010
        )

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
        if self.notebook.GetPageCount() > 0:
            self.select_tab(
                (self.notebook.GetSelection() + 1) % self.notebook.GetPageCount()
            )

    def on_harvest(self):
        done = ProjectModel.get_today_harvest(self.base_dir, self.settings)
        wx.MessageBox(
            "\n".join(done) if done else self.translator._("no_harvest"),
            self.translator._("arch_title"),
            wx.OK,
        )

    def on_open_archive(self):
        arch = ProjectModel.get_archive_path(self.base_dir, self.settings)
        if arch.exists():
            open_file_in_editor(arch)
        else:
            wx.MessageBox(self.translator._("no_arch"), "Info", wx.OK)

    def on_settings(self):
        if self._show_dialog(SettingsDialog, self.settings) == wx.ID_OK:
            self.translator.setup_translations()

    def on_close(self, event):
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if isinstance(page, TaskProjectPanel) and page.model.has_unsaved_changes:
                page.model.save_tasks_atomic()
        event.Skip()


if __name__ == "__main__":
    app = wx.App()
    instance_checker = wx.SingleInstanceChecker(f"DarTasks-{wx.GetUserId()}")
    if instance_checker.IsAnotherRunning():
        wx.MessageBox(
            "An instance of Dar Tasks is already running.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        sys.exit(0)
    MainFrame()
    app.MainLoop()
