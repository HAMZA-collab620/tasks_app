"""
Dar Tasks - Presentation Dialog Adapters.
Contains modal dialogs for Project Management, Global Search, and Settings.
Connects accessible wxPython user controls directly to deep domain module seams.
"""

from pathlib import Path
import wx

from core_models import (
    ProjectWorkspace,
    SearchEngine,
    SettingsManager,
    Translator,
    get_project_display_name,
    open_file_in_editor,
)


class GlobalSearchDialog(wx.Dialog):
    """Accessible UI adapter over the SearchEngine deep module."""

    def __init__(self, parent, search_engine: SearchEngine, settings=None):
        self.settings = settings
        self.translator = Translator(self.settings)
        super().__init__(
            parent, title=self.translator._("Global Search"), size=(600, 420)
        )
        self.parent, self.search_engine, self.last_results = parent, search_engine, []

        pnl = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(
            wx.StaticText(pnl, label=self.translator._("&Search:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.search_ctrl = wx.TextCtrl(pnl, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName(self.translator._("Search Query"))
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search)
        self.search_ctrl.Bind(
            wx.EVT_TEXT_ENTER,
            lambda e: (
                (self.results_list.SetSelection(0), self.results_list.SetFocus())
                if self.last_results
                else None
            ),
        )
        row.Add(self.search_ctrl, 1, wx.EXPAND)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(
            wx.StaticText(pnl, label=self.translator._("&Results:")),
            0,
            wx.LEFT,
            10,
        )
        self.results_list = wx.ListBox(pnl, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.results_list.SetName(self.translator._("Search Results"))
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_open_task)
        self.results_list.Bind(
            wx.EVT_KEY_DOWN,
            lambda e: (
                self.on_open_task()
                if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
                else e.Skip()
            ),
        )
        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 10)

        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        np_btn = wx.Button(pnl, label=self.translator._("&Notepad"))
        np_btn.Bind(wx.EVT_BUTTON, self.on_notepad)
        btn_box.Add(np_btn, 0, wx.RIGHT, 5)
        btn_box.Add(
            wx.Button(pnl, wx.ID_CANCEL, label=self.translator._("&Close")), 0
        )
        sizer.Add(btn_box, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)
        pnl.SetSizer(sizer)

    def on_search(self, event=None):
        query = self.search_ctrl.GetValue().strip()
        self.results_list.Clear()
        if len(query) < 2:
            self.last_results = []
            return
        sens = (
            self.settings.get("search", "case_sensitive", False)
            if self.settings
            else False
        )
        self.last_results = self.search_engine.search(query, case_sensitive=sens)
        self.results_list.Set([r["formatted"] for r in self.last_results])

    def on_open_task(self, event=None):
        sel = self.results_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.last_results):
            self.parent.open_or_select_project(self.last_results[sel]["filename"])
            self.EndModal(wx.ID_OK)

    def on_notepad(self, event=None):
        sel = self.results_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.last_results):
            open_file_in_editor(
                self.search_engine.workspace.get_project_path(
                    self.last_results[sel]["filename"]
                )
            )


class ProjectManagerDialog(wx.Dialog):
    """Accessible UI adapter over the ProjectWorkspace deep module."""

    def __init__(self, parent, workspace: ProjectWorkspace):
        self.parent, self.workspace, self.projects = parent, workspace, []
        self.translator = getattr(parent, "translator", Translator())
        super().__init__(
            parent,
            title=self.translator._("Project Manager"),
            size=(680, 440),
        )

        pnl = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(pnl, label=self.translator._("&Projects:")),
            0,
            wx.ALL,
            5,
        )

        self.project_list = wx.ListBox(pnl, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.project_list.SetName(self.translator._("Projects List"))
        self.project_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.on_open())
        self.project_list.Bind(
            wx.EVT_KEY_DOWN,
            lambda e: (
                self.on_open()
                if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
                else e.Skip()
            ),
        )
        sizer.Add(self.project_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        actions = [
            (self.translator._("&New"), self.on_new),
            (self.translator._("&Open"), self.on_open),
            (self.translator._("&Pin ⭐"), self.on_pin),
            (self.translator._("Move &Up"), lambda e: self.on_move(-1)),
            (self.translator._("Move &Down"), lambda e: self.on_move(1)),
            (self.translator._("&Rename"), self.on_rename),
            (self.translator._("Note&pad"), self.on_notepad),
            (self.translator._("&Delete"), self.on_delete),
            (self.translator._("&Close"), lambda e: self.EndModal(wx.ID_CANCEL)),
        ]
        for label, handler in actions:
            btn = wx.Button(pnl, label=label)
            btn.Bind(wx.EVT_BUTTON, handler)
            btn_sizer.Add(btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        pnl.SetSizer(sizer)
        self.refresh_list()

    def refresh_list(self):
        self.projects = self.workspace.list_projects()
        sfx = self.translator._(" (daily)")
        self.project_list.Set(
            [
                f"{'⭐ ' if p['pinned'] else ''}{get_project_display_name(p['filename'], self.translator)}{sfx if p['readonly'] else ''}"
                for p in self.projects
            ]
        )

    def on_new(self, event=None):
        dlg = wx.TextEntryDialog(
            self,
            self.translator._("New project name:"),
            self.translator._("New Project"),
        )
        if dlg.ShowModal() == wx.ID_OK and self.workspace.create_project(
            dlg.GetValue()
        ):
            self.refresh_list()
        dlg.Destroy()

    def on_open(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.projects):
            self.parent.open_or_select_project(self.projects[sel]["filename"])
            self.EndModal(wx.ID_OK)

    def on_notepad(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.projects):
            open_file_in_editor(Path(self.projects[sel]["path"]))

    def on_pin(self, event=None):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and not self.projects[sel]["readonly"]:
            self.workspace.toggle_pin(self.projects[sel]["filename"])
            self.refresh_list()
            self.project_list.SetSelection(sel)

    def on_move(self, direction: int):
        sel = self.project_list.GetSelection()
        if sel != wx.NOT_FOUND and self.workspace.move_project(sel, direction):
            self.refresh_list()
            self.project_list.SetSelection(sel + direction)

    def on_rename(self, event=None):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND or self.projects[sel]["readonly"]:
            return
        p = self.projects[sel]
        disp = get_project_display_name(p["filename"], self.translator)
        dlg = wx.TextEntryDialog(
            self,
            self.translator._("New project name:"),
            self.translator._("Rename Project"),
            disp,
        )
        if dlg.ShowModal() == wx.ID_OK:
            renamed = self.workspace.rename_project(p["filename"], dlg.GetValue())
            if renamed:
                if hasattr(self.parent, "on_project_renamed"):
                    self.parent.on_project_renamed(p["filename"], renamed)
                self.refresh_list()
        dlg.Destroy()

    def on_delete(self, event=None):
        sel = self.project_list.GetSelection()
        if sel == wx.NOT_FOUND or self.projects[sel]["readonly"]:
            return
        p = self.projects[sel]
        disp = get_project_display_name(p["filename"], self.translator)
        prompt = self.translator._("Delete project '{display}'?").format(display=disp)
        if (
            wx.MessageBox(
                prompt,
                self.translator._("Confirm Delete"),
                wx.YES_NO | wx.ICON_WARNING,
            )
            == wx.YES
        ):
            if self.workspace.delete_project(p["filename"]):
                if hasattr(self.parent, "on_project_deleted"):
                    self.parent.on_project_deleted(p["filename"])
                self.refresh_list()


class SettingsDialog(wx.Dialog):
    """Accessible dialog for managing application settings."""

    def __init__(self, parent, settings_manager: SettingsManager):
        self.settings = settings_manager
        self.translator = Translator(self.settings)
        super().__init__(
            parent, title=self.translator._("Settings"), size=(480, 360)
        )

        pnl = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.confirm_archive_cb = wx.CheckBox(
            pnl, label=self.translator._("Confirm on &archive")
        )
        self.confirm_delete_cb = wx.CheckBox(
            pnl, label=self.translator._("Confirm on &delete")
        )
        self.confirm_archive_cb.SetValue(
            self.settings.get("behavior", "confirm_on_archive", False)
        )
        self.confirm_delete_cb.SetValue(
            self.settings.get("behavior", "confirm_on_delete", True)
        )
        sizer.Add(self.confirm_archive_cb, 0, wx.ALL, 8)
        sizer.Add(self.confirm_delete_cb, 0, wx.ALL, 8)

        spin_box = wx.BoxSizer(wx.HORIZONTAL)
        spin_box.Add(
            wx.StaticText(
                pnl,
                label=self.translator._("Auto-save interval (&seconds):"),
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.auto_save_spin = wx.SpinCtrl(
            pnl,
            min=1,
            max=60,
            initial=self.settings.get("behavior", "auto_save_interval", 2),
        )
        spin_box.Add(self.auto_save_spin, 0)
        sizer.Add(spin_box, 0, wx.ALL, 8)

        lang_box = wx.BoxSizer(wx.HORIZONTAL)
        lang_box.Add(
            wx.StaticText(pnl, label=self.translator._("&Language:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.lang_choice = wx.Choice(pnl, choices=["English", "العربية"])
        self.lang_choice.SetSelection(
            1 if self.settings.get("general", "language", "en") == "ar" else 0
        )
        lang_box.Add(self.lang_choice, 1, wx.EXPAND)
        sizer.Add(lang_box, 0, wx.EXPAND | wx.ALL, 8)

        sizer.AddStretchSpacer()
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for lbl, h, uid in [
            (
                self.translator._("&Reset Defaults"),
                self.on_reset,
                wx.ID_ANY,
            ),
            (self.translator._("&Save"), self.on_save, wx.ID_OK),
            (
                self.translator._("&Cancel"),
                lambda e: self.EndModal(wx.ID_CANCEL),
                wx.ID_CANCEL,
            ),
        ]:
            b = wx.Button(pnl, uid, label=lbl)
            b.Bind(wx.EVT_BUTTON, h)
            btn_sizer.Add(b, 0, wx.RIGHT if uid != wx.ID_CANCEL else 0, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        pnl.SetSizer(sizer)

    def on_save(self, event=None):
        self.settings.set(
            "behavior", "confirm_on_archive", self.confirm_archive_cb.GetValue()
        )
        self.settings.set(
            "behavior", "confirm_on_delete", self.confirm_delete_cb.GetValue()
        )
        self.settings.set(
            "behavior", "auto_save_interval", self.auto_save_spin.GetValue()
        )
        self.settings.set(
            "general",
            "language",
            "ar" if self.lang_choice.GetSelection() == 1 else "en",
        )
        self.settings.save()
        self.EndModal(wx.ID_OK)

    def on_reset(self, event=None):
        prompt = self.translator._("Reset settings to default?")
        if (
            wx.MessageBox(prompt, self.translator._("Confirm Reset"), wx.YES_NO)
            == wx.YES
        ):
            self.settings.reset_to_defaults()
            self.confirm_archive_cb.SetValue(
                self.settings.get("behavior", "confirm_on_archive", False)
            )
            self.confirm_delete_cb.SetValue(
                self.settings.get("behavior", "confirm_on_delete", True)
            )
            self.auto_save_spin.SetValue(
                self.settings.get("behavior", "auto_save_interval", 2)
            )
            self.lang_choice.SetSelection(
                1 if self.settings.get("general", "language", "en") == "ar" else 0
            )
