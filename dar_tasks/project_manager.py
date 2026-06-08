import os
import wx
import send2trash
from dar_tasks.constants import BG_COLOR, DAILY_FILENAME, DAILY_TEMPLATE_FILENAME
from dar_tasks.utils import sanitize_project_name, load_json_data
from dar_tasks.task_panel import TaskProjectPanel
from dar_tasks.ui_factory import create_static_text, create_list_box, create_button
from dar_tasks.project_utils import (
    extract_filename_from_entry,
    get_project_order,
    save_project_order,
    ensure_project_order,
)


class ProjectManagerDialog(wx.Dialog):
    def __init__(self, parent, projects_dir):
        super().__init__(parent, title="Project Manager", size=(680, 460))
        self.parent, self.projects_dir, self.projects = parent, projects_dir, []
        self.buttons_config = load_json_data("project_manager_layout.json", [])
        self.init_ui()
        self.load_projects()

    def init_ui(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(BG_COLOR)
        sizer = wx.BoxSizer(wx.VERTICAL)
        header = create_static_text(panel, label="&Manage all projects")
        header.SetFont(header.GetFont().Bold())
        sizer.Add(header, 0, wx.ALL, 8)
        self.project_list = create_list_box(panel, tooltip="List of projects (Alt+M)")
        self.project_list.Bind(wx.EVT_LISTBOX, self.on_selection_changed)
        self.project_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.dispatch_command("open"))
        sizer.Add(self.project_list, 1, wx.EXPAND | wx.ALL, 10)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for b in self.buttons_config:
            btn = create_button(panel, b["label"], b["tooltip"], lambda e, c=b["cmd"]: self.dispatch_command(c))
            setattr(self, b["attr"], btn)
            btn_sizer.Add(btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)
        if hasattr(self, "open_btn"):
            self.open_btn.SetDefault()

    def dispatch_command(self, cmd):
        if cmd == "new":
            self.on_new_project()
            return
        if cmd == "refresh":
            self.load_projects()
            return
        if cmd == "close":
            self.EndModal(wx.ID_CANCEL)
            return
        p = self.get_selected_project()
        if not p:
            return
        if cmd == "open":
            self._open_project_tab(p)
        elif cmd == "pin" and not p["readonly"]:
            self._update_order(
                lambda e: [
                    (
                        (f if r.startswith("⭐ ") else f"⭐ {f}")
                        if extract_filename_from_entry(r) == p["filename"]
                        else r
                    )
                    for r in e
                    for f in [extract_filename_from_entry(r)]
                ]
            )
        elif cmd == "move_up":
            self._move_project(-1)
        elif cmd == "move_down":
            self._move_project(1)
        elif cmd == "rename" and not p["readonly"]:
            self.on_rename_project(p)
        elif cmd == "delete" and not p["readonly"]:
            self.on_delete_project(p)

    def load_projects(self, event=None):
        self.projects = []
        for r in ensure_project_order(self.projects_dir):
            fn = extract_filename_from_entry(r)
            if fn == DAILY_TEMPLATE_FILENAME:
                continue
            self.projects.append(
                {
                    "display_name": "Daily Tasks" if fn == DAILY_FILENAME else fn[:-4],
                    "filename": fn,
                    "path": os.path.join(self.projects_dir, fn),
                    "readonly": fn == DAILY_FILENAME,
                    "pinned": r.startswith("⭐ "),
                    "raw_entry": r,
                }
            )
        self.project_list.Set(
            [
                f"{'⭐ ' if p['pinned'] else ''}{p['display_name']}{' (daily)' if p['readonly'] else ''}"
                for p in self.projects
            ]
        )
        self.on_selection_changed(None)

    def get_selected_project(self):
        idx = self.project_list.GetSelection()
        return self.projects[idx] if 0 <= idx < len(self.projects) else None

    def on_selection_changed(self, event):
        p = self.get_selected_project()
        idx = self.projects.index(p) if p else -1
        for attr, enabled in [
            ("open_btn", p),
            ("pin_btn", p and not p["readonly"]),
            ("up_btn", p and idx > 0),
            ("down_btn", p and idx < len(self.projects) - 1),
            ("rename_btn", p and not p["readonly"]),
            ("delete_btn", p and not p["readonly"]),
        ]:
            getattr(self, attr).Enable(bool(enabled))
        if p:
            self.pin_btn.SetLabel("Unpin" if p["pinned"] else "Pin")

    def _open_project_tab(self, p):
        for i in range(self.parent.notebook.GetPageCount()):
            page = self.parent.notebook.GetPage(i)
            if getattr(page, "filename", None) == p["path"]:
                self.parent.notebook.SetSelection(i)
                page.task_list.SetFocus()
                return
        page = TaskProjectPanel(self.parent.notebook, p["path"], self.parent.settings)
        self.parent.notebook.AddPage(page, p["display_name"])
        self.parent.notebook.SetSelection(self.parent.notebook.GetPageCount() - 1)
        page.task_list.SetFocus()

    def _update_order(self, update_func, filename_to_select=None):
        new_entries = update_func(get_project_order(self.projects_dir))
        save_project_order(self.projects_dir, new_entries)
        self.load_projects()
        if filename_to_select:
            for i, p in enumerate(self.projects):
                if p["filename"] == filename_to_select:
                    self.project_list.SetSelection(i)
                    self.on_selection_changed(None)
                    break

    def _move_project(self, direction):
        p = self.get_selected_project()
        entries = get_project_order(self.projects_dir)
        idx = next((i for i, r in enumerate(entries) if extract_filename_from_entry(r) == p["filename"]), None)
        if idx is not None and 0 <= idx + direction < len(entries):
            entries[idx], entries[idx + direction] = entries[idx + direction], entries[idx]
            save_project_order(self.projects_dir, entries)
            self.load_projects()
            for i, proj in enumerate(self.projects):
                if proj["filename"] == p["filename"]:
                    self.project_list.SetSelection(i)
                    self.on_selection_changed(None)
                    break

    def on_new_project(self):
        dlg = wx.TextEntryDialog(self, "New project name:", "Create")
        if dlg.ShowModal() == wx.ID_OK:
            name = sanitize_project_name(dlg.GetValue().strip())
            if name:
                path = os.path.join(self.projects_dir, f"{name}.txt")
                if os.path.exists(path):
                    wx.MessageBox("Exists!", "Error", wx.OK)
                else:
                    try:
                        with open(path, "w", encoding="utf-8") as f:
                            pass
                    except IOError as e:
                        wx.MessageBox(f"Failed to create project: {e}", "Error", wx.OK | wx.ICON_ERROR)
                        dlg.Destroy()
                        return
                    self._update_order(lambda e: e + [f"{name}.txt"], f"{name}.txt")
                    self._open_project_tab(self.get_selected_project())
        dlg.Destroy()

    def on_rename_project(self, p):
        dlg = wx.TextEntryDialog(self, "New name:", "Rename", p["display_name"])
        if dlg.ShowModal() == wx.ID_OK:
            new = sanitize_project_name(dlg.GetValue())
            new_fn = f"{new}.txt"
            new_path = os.path.join(self.projects_dir, new_fn)
            if new and not os.path.exists(new_path):
                try:
                    os.rename(p["path"], new_path)
                    # Critical Fix: Update file path in any open tab
                    for i in range(self.parent.notebook.GetPageCount()):
                        page = self.parent.notebook.GetPage(i)
                        if getattr(page, "filename", None) == p["path"]:
                            page.filename = new_path
                            page.model.filename = new_path
                            self.parent.notebook.SetPageText(i, new)
                            break
                    
                    self._update_order(
                        lambda e: [
                            (
                                (f"⭐ {new_fn}" if r.startswith("⭐ ") else new_fn)
                                if extract_filename_from_entry(r) == p["filename"]
                                else r
                            )
                            for r in e
                        ],
                        new_fn,
                    )
                except OSError as e:
                    wx.MessageBox(f"Rename failed: {e}", "Error", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()

    def on_delete_project(self, p):
        if wx.MessageBox(f"Delete {p['display_name']}?", "Confirm", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            try:
                # Critical Fix: Close the tab if it's open
                for i in range(self.parent.notebook.GetPageCount()):
                    page = self.parent.notebook.GetPage(i)
                    if getattr(page, "filename", None) == p["path"]:
                        self.parent.notebook.DeletePage(i)
                        break

                if os.path.exists(p["path"]):
                    send2trash.send2trash(p["path"])
                
                self._update_order(lambda e: [r for r in e if extract_filename_from_entry(r) != p["filename"]])
            except OSError as e:
                wx.MessageBox(f"Delete failed: {e}", "Error", wx.OK | wx.ICON_ERROR)
