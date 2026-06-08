import pyperclip
import wx

from dar_tasks.constants import BG_COLOR, FONT_SIZE
from dar_tasks.utils import get_base_dir
from dar_tasks.project_model import ProjectModel
from dar_tasks.widgets import LabeledTextCtrl, TaskListBox


class TaskProjectPanel(wx.Panel):
    """Panel representing a single project with Command Router and reusable widgets."""

    def __init__(self, parent, filename, settings=None):
        super().__init__(parent)
        self.filename, self.settings = filename, settings
        self.model = ProjectModel(self.filename, self.settings, get_base_dir())
        self.init_ui()
        if self.model.load_tasks():
            self.update_display()
        self.setup_auto_save()
        self.task_list.SetFocus()

    # Property Proxies for Test Compatibility and Clarity
    @property
    def task_list(self):
        return self.task_list_component.list_box

    @property
    def search_input(self):
        return self.search_component.control

    @property
    def new_task_input(self):
        return self.add_component.control

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

    def init_ui(self):
        self.SetBackgroundColour(BG_COLOR)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.search_component = LabeledTextCtrl(
            self, "&Filter:", tooltip="Filter (Alt+F)", handler=self.on_search
        )
        sizer.Add(self.search_component, 0, wx.EXPAND)
        self.task_list_component = TaskListBox(self, "&Tasks:", tooltip="Tasks (Alt+T)")
        self.task_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.dispatch_command("archive"))
        self.task_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        sizer.Add(self.task_list_component, 1, wx.EXPAND | wx.ALL, 5)
        self.add_component = LabeledTextCtrl(
            self, "&Add:", tooltip="Add (Alt+A)", handler=self.on_add_task, style=wx.TE_PROCESS_ENTER
        )
        sizer.Add(self.add_component, 0, wx.EXPAND)
        self.SetSizer(sizer)
        self.update_font_size(FONT_SIZE)

    def dispatch_command(self, cmd, *args):
        """Central router for all operations."""
        if cmd == "add":
            t = self.new_task_input.GetValue().strip()
            if self.model.add_task(t):
                self.new_task_input.Clear()
                self.update_display(self.search_input.GetValue())
        elif cmd == "search":
            self.update_display(self.search_input.GetValue())
        elif cmd == "undo":
            if self.model.undo():
                self.update_display(self.search_input.GetValue())

        sel = self.task_list.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        txt = self.task_list.GetString(sel)

        if cmd == "archive" or cmd == "complete":
            if self._confirm("Archive?", "confirm_on_archive", False) and self.model.archive_task(txt):
                self.update_display(self.search_input.GetValue())
                # Select the same index (which is now the next task) or the last one
                new_sel = min(sel, self.task_list.GetCount() - 1)
                if new_sel >= 0:
                    self.task_list.SetSelection(new_sel)
                self.task_list.SetFocus()
        elif cmd == "delete":
            if self._confirm("Delete?", "confirm_on_delete", True) and self.model.delete_task(txt):
                self.update_display(self.search_input.GetValue())
                new_sel = min(sel, self.task_list.GetCount() - 1)
                if new_sel >= 0:
                    self.task_list.SetSelection(new_sel)
                self.task_list.SetFocus()
        elif cmd == "edit":
            dlg = wx.TextEntryDialog(self, "Edit:", "Edit", txt)
            if dlg.ShowModal() == wx.ID_OK and self.model.edit_task(txt, dlg.GetValue().strip()):
                self.update_display(self.search_input.GetValue())
                self.task_list.SetSelection(sel)
            self.task_list.SetFocus()
            dlg.Destroy()
        elif cmd == "copy":
            pyperclip.copy(txt)
            self.task_list.SetFocus()
        elif cmd == "pin":
            if self.model.toggle_pin(txt):
                self.update_display(self.search_input.GetValue())
                # Re-find the task or stay at selection
                self.task_list.SetSelection(sel)
            self.task_list.SetFocus()
        elif cmd == "move_up":
            if sel > 0 and self.model.move_task(sel, -1):
                self.update_display(self.search_input.GetValue())
                self.task_list.SetSelection(sel - 1)
            self.task_list.SetFocus()
        elif cmd == "move_down":
            if sel < self.task_list.GetCount() - 1 and self.model.move_task(sel, 1):
                self.update_display(self.search_input.GetValue())
                self.task_list.SetSelection(sel + 1)
            self.task_list.SetFocus()

    def _confirm(self, msg, key, default):
        if not (self.settings.get("behavior", key, default) if self.settings else default):
            return True
        return wx.MessageBox(msg, "Confirm", wx.YES_NO) == wx.YES

    # Compatibility Wrappers for Tests
    def archive_task(self, txt):
        self._set_sel_and_run(txt, "archive")

    def delete_task_final(self, txt):
        self._set_sel_and_run(txt, "delete")

    def undo(self):
        self.dispatch_command("undo")

    def move_up(self):
        self.dispatch_command("move_up")

    def move_down(self):
        self.dispatch_command("move_down")

    def on_search(self, e):
        self.dispatch_command("search")

    def on_add_task(self, e):
        self.dispatch_command("add")

    def _set_sel_and_run(self, txt, cmd):
        idx = self.task_list.FindString(txt)
        if idx != wx.NOT_FOUND:
            self.task_list.SetSelection(idx)
            self.dispatch_command(cmd)

    def on_context_menu(self, event):
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            item = self.task_list.HitTest(self.task_list.ScreenToClient(pos))
            if item != wx.NOT_FOUND:
                self.task_list.SetSelection(item)
        if self.task_list.GetSelection() != wx.NOT_FOUND:
            menu = wx.Menu()
            options = [
                ("Mark as Complete (Ctrl+M)", "complete"),
                ("Pin ⭐", "pin"),
                ("Edit", "edit"),
                ("Copy", "copy"),
                ("Delete", "delete"),
            ]
            for lbl, cmd in options:
                item = menu.Append(wx.ID_ANY, lbl)
                self.Bind(wx.EVT_MENU, lambda e, c=cmd: self.dispatch_command(c), item)
            self.PopupMenu(menu)
            menu.Destroy()

    def update_display(self, filter_text=""):
        self.task_list.Clear()
        tasks = self.model.get_filtered_tasks(filter_text)
        lim = self.settings.get("search", "lazy_load_threshold", 100) if self.settings else 100
        self.task_list.Set(tasks[:lim] if len(tasks) > lim and not filter_text else tasks)
        self.Layout()

    def update_theme_colors(self, bg, fg, accent):
        self.SetBackgroundColour(bg)
        for comp in [self.search_component, self.task_list_component, self.add_component]:
            comp.label_txt.SetForegroundColour(fg)
        for ctrl in [self.search_input, self.task_list, self.new_task_input]:
            ctrl.SetBackgroundColour(accent)
            ctrl.SetForegroundColour(fg)
        self.Refresh()

    def update_font_size(self, size):
        for ctrl in [self.task_list, self.search_input, self.new_task_input]:
            f = ctrl.GetFont()
            f.SetPointSize(size)
            ctrl.SetFont(f)
        self.Layout()

    def setup_auto_save(self):
        inv = self.settings.get("behavior", "auto_save_interval", 2) if self.settings else 2
        self.timer = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER,
            lambda e: (self.model.save_tasks_atomic() and self._notify()) if self.model.has_unsaved_changes else None,
            self.timer,
        )
        self.Bind(wx.EVT_WINDOW_DESTROY, lambda e: self.timer.Stop() if hasattr(self, 'timer') else None)
        self.timer.Start(inv * 1000)

    def _notify(self):
        p = self.GetParent()
        while p and not isinstance(p, wx.Notebook):
            p = p.GetParent()
        if p and hasattr(p.GetParent(), "update_tab_titles"):
            p.GetParent().update_tab_titles()
