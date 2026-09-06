"""
Dar Tasks - Presentation Dialog Adapters.
Contains modal dialogs for Project Management, Global Search, and Settings.
Connects accessible wxPython user controls directly to deep domain module seams.
"""

import wx

from core_models import (
    ProjectWorkspace,
    SearchEngine,
    SettingsManager,
)


class GlobalSearchDialog(wx.Dialog):
    """Accessible UI adapter over the SearchEngine deep module."""

    def __init__(self, parent, search_engine: SearchEngine, settings=None):
        super().__init__(parent, title="Global Search", size=(600, 420))
        self.parent = parent
        self.search_engine = search_engine
        self.settings = settings
        self.last_results = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        search_box = wx.BoxSizer(wx.HORIZONTAL)
        search_box.Add(
            wx.StaticText(panel, label="&Search:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5
        )
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
        query = self.search_ctrl.GetValue().strip()
        self.results_list.Clear()
        if len(query) < 2:
            self.last_results = []
            return
        case_sensitive = (
            self.settings.get("search", "case_sensitive", False) if self.settings else False
        )
        self.last_results = self.search_engine.search(query, case_sensitive=case_sensitive)
        self.results_list.Set([result["formatted"] for result in self.last_results])

    def on_open_task(self, event=None):
        sel = self.results_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.last_results):
            result = self.last_results[sel]
            self.parent.open_or_select_project(result["filename"])
            self.EndModal(wx.ID_OK)


class ProjectManagerDialog(wx.Dialog):
    """Accessible UI adapter over the ProjectWorkspace deep module."""

    def __init__(self, parent, workspace: ProjectWorkspace):
        super().__init__(parent, title="Project Manager", size=(650, 420))
        self.parent = parent
        self.workspace = workspace
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
            [
                f"{'⭐ ' if p['pinned'] else ''}{p['display']}{' (daily)' if p['readonly'] else ''}"
                for p in self.projects
            ]
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
            selected_project = self.projects[sel]
            self.parent.open_or_select_project(selected_project["filename"])
            self.EndModal(wx.ID_OK)

    def on_pin(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and not self.projects[sel]["readonly"]:
            self.workspace.toggle_pin(self.projects[sel]["filename"])
            self.refresh_list()
            self.project_list.SetSelection(sel)

    def on_move(self, direction: int):
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
        selected_project = self.projects[sel]
        dlg = wx.TextEntryDialog(self, "New project name:", "Rename Project", selected_project["display"])
        if dlg.ShowModal() == wx.ID_OK:
            renamed = self.workspace.rename_project(selected_project["filename"], dlg.GetValue())
            if renamed:
                self.refresh_list()
        dlg.Destroy()

    def on_delete(self, event=None):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND or self.projects[sel]["readonly"]:
            return
        selected_project = self.projects[sel]
        if (
            wx.MessageBox(
                f"Delete project '{selected_project['display']}'?",
                "Confirm Delete",
                wx.YES_NO | wx.ICON_WARNING,
            )
            == wx.YES
        ):
            if self.workspace.delete_project(selected_project["filename"]):
                self.refresh_list()


class SettingsDialog(wx.Dialog):
    """Accessible dialog for managing application settings."""

    def __init__(self, parent, settings_manager: SettingsManager):
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
        spin_box.Add(
            wx.StaticText(panel, label="Auto-save interval (&seconds):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.auto_save_spin = wx.SpinCtrl(
            panel, min=1, max=60, initial=self.settings.get("behavior", "auto_save_interval", 2)
        )
        spin_box.Add(self.auto_save_spin, 0)
        sizer.Add(spin_box, 0, wx.ALL, 8)

        lang_box = wx.BoxSizer(wx.HORIZONTAL)
        lang_box.Add(
            wx.StaticText(panel, label="&Language:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.lang_choice = wx.Choice(panel, choices=["English", "العربية"])
        self.lang_choice.SetSelection(
            1 if self.settings.get("general", "language", "en") == "ar" else 0
        )
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
        self.settings.set(
            "general", "language", "ar" if self.lang_choice.GetSelection() == 1 else "en"
        )
        self.settings.save()
        self.EndModal(wx.ID_OK)

    def on_reset(self, event=None):
        if wx.MessageBox("Reset settings to default?", "Confirm Reset", wx.YES_NO) == wx.YES:
            self.settings.reset_to_defaults()
            self.confirm_archive_cb.SetValue(
                self.settings.get("behavior", "confirm_on_archive", False)
            )
            self.confirm_delete_cb.SetValue(
                self.settings.get("behavior", "confirm_on_delete", True)
            )
            self.auto_save_spin.SetValue(self.settings.get("behavior", "auto_save_interval", 2))
            self.lang_choice.SetSelection(
                1 if self.settings.get("general", "language", "en") == "ar" else 0
            )
