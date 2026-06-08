"""
Main Frame for the Task Management Application.
Contains the MainFrame class with centralized command routing and data-driven UI.
"""

import datetime
import os
import subprocess
import platform
import wx

from dar_tasks.constants import BG_COLOR, DEFAULT_ARCHIVE_NAME, DAILY_FILENAME, DAILY_TEMPLATE_FILENAME
from dar_tasks.utils import get_base_dir
from dar_tasks.task_panel import TaskProjectPanel
from dar_tasks.dialogs import GlobalSearchDialog
from dar_tasks.project_manager import ProjectManagerDialog
from dar_tasks.project_utils import ensure_project_order, get_project_display_name, extract_filename_from_entry
from dar_tasks.settings_manager import SettingsManager
from dar_tasks.settings_dialog import SettingsDialog
from dar_tasks.translator import Translator
from dar_tasks.backup_manager import BackupManager
from dar_tasks.theme_manager import ThemeManager
from dar_tasks.ui_factory import create_button
from dar_tasks.logger import setup_logger, logger


class MainFrame(wx.Frame):
    """Main application window with streamlined routing and data-driven toolbar."""

    def __init__(self):
        super().__init__(None, title="Dar Tasks - All-in-One Developer", size=(800, 600))

        self.base_dir = get_base_dir()
        setup_logger(self.base_dir)
        logger.info("Application starting...")
        self.projects_dir = os.path.join(self.base_dir, "projects")
        self.backups_dir = os.path.join(self.base_dir, "backups")

        # Initialize managers
        self.settings = SettingsManager(self.base_dir)
        self.translator = Translator(self.settings)
        self.backup_mgr = BackupManager(self.base_dir, self.projects_dir, self.backups_dir, self.settings)
        self.theme_mgr = ThemeManager(self.settings)

        for d in [self.projects_dir, self.backups_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

        self.backup_mgr.setup_daily_tasks()
        self.setup_backup_schedule()

        self._define_toolbar_data()
        self.init_ui()
        self.setup_global_shortcuts()
        self.load_all_projects()
        self.theme_mgr.apply_all(self)
        self.check_for_updates()
        self.Show()

    def _define_toolbar_data(self):
        """Toolbar buttons configuration."""
        self.toolbar_data = [
            {"key": "proj_mgr", "mnemonic": "P", "handler": lambda e: self.on_project_manager(), "attr": "manager_btn"},
            {
                "key": "search",
                "mnemonic": "S",
                "handler": lambda e: self.dispatch_command("global_search"),
                "attr": "search_btn",
            },
            {"key": "harvest", "mnemonic": "H", "handler": lambda e: self.on_view_today_archive(), "attr": "arch_btn"},
            {
                "key": "open_arch",
                "mnemonic": "O",
                "handler": lambda e: self.on_open_archive_file(),
                "attr": "open_arch_btn",
            },
            {"key": "settings", "mnemonic": "T", "handler": lambda e: self.on_settings(), "attr": "settings_btn"},
        ]

    def _(self, key):
        return self.translator._(key)

    def init_ui(self):
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(BG_COLOR)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Build data-driven toolbar
        self.toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for item in self.toolbar_data:
            btn = create_button(
                self.panel,
                label=f"&{self._(item['key'])}",
                tooltip=f"{self._(item['key'])} (Alt+{item['mnemonic']})",
                handler=item["handler"],
            )
            setattr(self, item["attr"], btn)
            self.toolbar_sizer.Add(btn, 0, wx.ALL, 5)

        self.main_sizer.Add(self.toolbar_sizer, 0, wx.EXPAND)
        self.notebook = wx.Notebook(self.panel)
        self.main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.panel.SetSizer(self.main_sizer)

    def dispatch_command(self, cmd, *args):
        """Main dispatcher for global and tab-specific commands."""
        if cmd == "global_search":
            dlg = GlobalSearchDialog(self, self.projects_dir, self.settings)
            dlg.ShowModal()
            dlg.Destroy()

        elif cmd == "settings":
            self.on_settings()

        else:
            # Route to current tab
            page = self.notebook.GetCurrentPage()
            if isinstance(page, TaskProjectPanel):
                page.dispatch_command(cmd, *args)

    def setup_global_shortcuts(self):
        shortcuts = [
            (wx.ACCEL_CTRL, wx.WXK_UP, 1001, "move_up"),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, 1002, "move_down"),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, 1003, "delete"),
            (wx.ACCEL_NORMAL, wx.WXK_F2, 1004, "edit"),
            (wx.ACCEL_CTRL, ord("Z"), 1005, "undo"),
            (wx.ACCEL_CTRL, ord("M"), 1009, "complete"),
            (wx.ACCEL_CTRL, wx.WXK_TAB, 1006, "next_tab"),
            (wx.ACCEL_CTRL, ord("C"), 1007, "copy"),
            (wx.ACCEL_CTRL, ord("F"), 1008, "global_search"),
        ]

        accel_entries = []
        for flags, key, uid, cmd in shortcuts:
            accel_entries.append((flags, key, uid))
            if cmd == "next_tab":
                self.Bind(wx.EVT_MENU, self.next_tab, id=uid)
            else:
                self.Bind(wx.EVT_MENU, lambda e, c=cmd: self.dispatch_command(c), id=uid)

        for i in range(1, 10):
            uid = 1100 + i
            accel_entries.append((wx.ACCEL_CTRL, ord(str(i)), uid))
            self.Bind(wx.EVT_MENU, lambda e, idx=i - 1: self.select_tab(idx), id=uid)

        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

    def load_all_projects(self):
        order = ensure_project_order(self.projects_dir)
        for entry in order:
            filename = extract_filename_from_entry(entry)
            if filename == DAILY_TEMPLATE_FILENAME:
                continue
            path = os.path.join(self.projects_dir, filename)
            if not os.path.exists(path):
                continue

            title = get_project_display_name(filename, self.translator)
            self.notebook.AddPage(TaskProjectPanel(self.notebook, path, self.settings), title)

    def on_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.translator.setup_translations()
            for item in self.toolbar_data:
                btn = getattr(self, item["attr"])
                btn.SetLabel(f"&{self._(item['key'])}")
                btn.SetToolTip(f"{self._(item['key'])} (Alt+{item['mnemonic']})")

            for i in range(self.notebook.GetPageCount()):
                page = self.notebook.GetPage(i)
                if isinstance(page, TaskProjectPanel):
                    filename = os.path.basename(page.model.filename)
                    self.notebook.SetPageText(i, get_project_display_name(filename, self.translator))
            self.theme_mgr.apply_all(self)
        dlg.Destroy()

    def on_project_manager(self):
        dlg = ProjectManagerDialog(self, self.projects_dir)
        dlg.ShowModal()
        dlg.Destroy()

    def on_view_today_archive(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        done = []
        arch = self.settings.get("backup", "archive_location") or os.path.join(self.base_dir, DEFAULT_ARCHIVE_NAME)
        if os.path.exists(arch):
            with open(arch, "r", encoding="utf-8", errors="replace") as f:
                done = [line for line in f if line.startswith(f"[{today}")]
        wx.MessageBox("".join(done) if done else self._("no_harvest"), self._("arch_title"), wx.OK)

    def on_open_archive_file(self):
        arch = self.settings.get("backup", "archive_location") or os.path.join(self.base_dir, DEFAULT_ARCHIVE_NAME)
        if os.path.exists(arch):
            if platform.system() == "Windows":
                os.startfile(arch)
            else:
                subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", arch])
        else:
            wx.MessageBox(self._("no_arch"), "Info", wx.OK)

    def select_tab(self, index):
        if index < self.notebook.GetPageCount():
            self.notebook.SetSelection(index)
            wx.CallAfter(self.notebook.GetCurrentPage().task_list.SetFocus)

    def next_tab(self, e):
        cnt = self.notebook.GetPageCount()
        if cnt > 0:
            self.select_tab((self.notebook.GetSelection() + 1) % cnt)

    def setup_backup_schedule(self):
        freq = self.settings.get("backup", "auto_backup_frequency", "daily").lower()
        if freq == "never":
            return
        today = datetime.date.today().isoformat()
        if self.settings.get("backup", "last_backup_date", "") != today:
            self.backup_mgr.perform_routine_maintenance()
            self.settings.set("backup", "last_backup_date", today)
            self.settings.save()
        self.backup_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.backup_mgr.perform_routine_maintenance(), self.backup_timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, lambda e: self.backup_timer.Stop() if hasattr(self, 'backup_timer') else None)
        self.backup_timer.Start(86400000 if freq == "daily" else 604800000)

    def check_for_updates(self):
        pass

    def update_tab_titles(self):
        pass

