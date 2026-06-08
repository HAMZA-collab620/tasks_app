"""
Dialog Components for the Task Management Application.
Contains dialog classes like GlobalSearchDialog.
"""

import os
import wx
from dar_tasks.constants import BG_COLOR, DAILY_FILENAME, DAILY_TEMPLATE_FILENAME
from dar_tasks.ui_factory import create_static_text, create_text_ctrl, create_list_box, create_button


class GlobalSearchDialog(wx.Dialog):
    """Dialog for searching across all projects."""

    def __init__(self, parent, projects_dir, settings=None):
        super().__init__(parent, title="Global Search", size=(600, 400))
        self.projects_dir = projects_dir
        self.parent = parent
        self.settings = settings
        self.all_tasks = []  # List of (project_name, task_text)
        self.task_generators = {}  # Lazy loaders for each project file
        self.loaded_projects = set()  # Track which projects have been loaded

        self.init_ui()
        self.load_all_tasks()

    def init_ui(self):
        """Initialize the dialog UI using the UI factory."""
        panel = wx.Panel(self)
        panel.SetBackgroundColour(BG_COLOR)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Search field
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = create_static_text(panel, label="Search:")
        search_sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.search_ctrl = create_text_ctrl(
            panel, tooltip="Search across all projects...", handler=self.on_search, style=wx.TE_PROCESS_ENTER
        )
        self.search_ctrl.SetHint("Search across all projects...")
        search_sizer.Add(self.search_ctrl, 1, wx.ALL, 5)
        sizer.Add(search_sizer, 0, wx.EXPAND)

        # Results list
        results_label = create_static_text(panel, label="Results:")
        sizer.Add(results_label, 0, wx.LEFT | wx.TOP, 10)

        self.results_list = create_list_box(panel, style=wx.LB_SINGLE)
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_result_double_click)
        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_btn = create_button(panel, label="Close", handler=lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)

        panel.SetSizer(sizer)

    def load_all_tasks(self):
        """Initialize lazy loaders for all project files without loading them immediately."""
        self.all_tasks = []
        self.task_generators = {}
        self.loaded_projects = set()

        if not os.path.exists(self.projects_dir):
            return
        try:
            files = [
                f
                for f in os.listdir(self.projects_dir)
                if f.endswith(".txt") and f not in (DAILY_TEMPLATE_FILENAME, ".project_order.txt")
            ]
        except OSError:
            return

        # Create lazy loaders for each project
        for file in files:
            path = os.path.join(self.projects_dir, file)
            project_name = file[:-4] if file != DAILY_FILENAME else "Daily Tasks"
            self.task_generators[project_name] = path

    def _load_project_tasks(self, project_name):
        """Lazily load tasks from a specific project (called on-demand)."""
        if project_name in self.loaded_projects:
            return  # Already loaded

        path = self.task_generators.get(project_name)
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
                for line in lines:
                    self.all_tasks.append((project_name, line))
            self.loaded_projects.add(project_name)
        except (IOError, UnicodeDecodeError):
            pass

    def on_search(self, event):
        """Update search results with lazy loading."""
        query = self.search_ctrl.GetValue().strip()
        self.results_list.Clear()
        if len(query) < 2:
            return

        # Get case sensitivity setting
        case_sensitive = False
        if self.settings:
            case_sensitive = self.settings.get("search", "case_sensitive", False)

        # Load tasks from all projects lazily as needed
        for project_name in self.task_generators.keys():
            self._load_project_tasks(project_name)

        results = []
        for project, task in self.all_tasks:
            if case_sensitive:
                match = query in task
            else:
                match = query.lower() in task.lower()

            if match:
                results.append(f"[{project}] {task}")

        self.results_list.Set(results)

    def on_result_double_click(self, event):
        """Switch to the project and select the task."""
        from dar_tasks.task_panel import TaskProjectPanel

        selection = self.results_list.GetSelection()
        if selection != wx.NOT_FOUND:
            result_text = self.results_list.GetString(selection)
            # Parse [project] task
            if result_text.startswith("[") and "]" in result_text:
                end_bracket = result_text.find("]")
                project_name = result_text[1:end_bracket]
                task_text = result_text[end_bracket + 2 :]

                # Find the tab index
                for i in range(self.parent.notebook.GetPageCount()):
                    page = self.parent.notebook.GetPage(i)
                    if isinstance(page, TaskProjectPanel):
                        filename = os.path.basename(page.model.filename)
                        internal_name = filename[:-4] if filename != DAILY_FILENAME else "Daily Tasks"
                        if internal_name == project_name:
                            self.parent.notebook.SetSelection(i)
                            page.task_list.SetFocus()
                            # Try to select the task in the list
                            for j in range(page.task_list.GetCount()):
                                if page.task_list.GetString(j) == task_text:
                                    page.task_list.SetSelection(j)
                                    break
                            break
        self.EndModal(wx.ID_OK)
