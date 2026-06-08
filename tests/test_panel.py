import unittest
import os
import shutil
import tempfile
import wx
from dar_tasks.task_panel import TaskProjectPanel
from dar_tasks.settings_manager import SettingsManager


class TestTaskPanelLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We need a wxApp for wx.Colour and other wx components used in __init__
        cls.app = wx.App(False)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.settings = SettingsManager(self.test_dir)
        self.filename = os.path.join(self.test_dir, "test_project.txt")
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write("Task 1\n⭐ Pinned Task\nTask 2\n")

        # Mock parent for the panel
        self.frame = wx.Frame(None)
        self.panel = TaskProjectPanel(self.frame, self.filename, self.settings)

    def tearDown(self):
        self.frame.Destroy()
        shutil.rmtree(self.test_dir)

    def test_load_tasks(self):
        self.assertIn("Task 1", self.panel.all_tasks)
        self.assertIn("Task 2", self.panel.all_tasks)
        self.assertIn("⭐ Pinned Task", self.panel.pinned_tasks)
        self.assertEqual(len(self.panel.all_tasks), 2)
        self.assertEqual(len(self.panel.pinned_tasks), 1)

    def test_add_task(self):
        # Manually trigger addition logic
        self.panel.new_task_input.SetValue("New Task")
        self.panel.on_add_task(None)
        self.assertIn("New Task", self.panel.all_tasks)

    def test_archive_task(self):
        task = "Task 1"
        self.panel.archive_task(task)
        self.assertNotIn(task, self.panel.all_tasks)

        # Check archive file
        with open(self.panel.archive_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn(task, content)

    def test_delete_task(self):
        # Disable confirmation for test
        self.settings.set("behavior", "confirm_on_delete", False)
        task = "Task 2"
        self.panel.delete_task_final(task)
        self.assertNotIn(task, self.panel.all_tasks)

        # Check trash file
        with open(self.panel.trash_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn(task, content)

    def test_undo(self):
        task = "Task 1"
        self.panel.archive_task(task)
        self.assertNotIn(task, self.panel.all_tasks)
        self.panel.undo()
        self.assertIn(task, self.panel.all_tasks)


if __name__ == "__main__":
    unittest.main()
