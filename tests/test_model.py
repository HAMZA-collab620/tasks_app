"""
Unit tests for ProjectModel - Testing the core logic of task management.
"""

import os
import shutil
import tempfile
import unittest
from dar_tasks.project_model import ProjectModel
from dar_tasks.settings_manager import SettingsManager


class TestProjectModel(unittest.TestCase):
    """Test suite for ProjectModel logic and file I/O."""

    def setUp(self):
        """Setup a temporary workspace for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.projects_dir = os.path.join(self.test_dir, "projects")
        os.makedirs(self.projects_dir)

        self.settings = SettingsManager(self.test_dir)
        self.project_file = os.path.join(self.projects_dir, "test_project.txt")

        # Initial tasks
        with open(self.project_file, "w", encoding="utf-8") as f:
            f.write("Task 1\n⭐ Pinned 1\nTask 2\n")

        self.model = ProjectModel(self.project_file, self.settings, self.test_dir)

    def tearDown(self):
        """Cleanup the temporary workspace."""
        shutil.rmtree(self.test_dir)

    def test_load_tasks(self):
        """Verify tasks are loaded and split correctly into pinned and regular lists."""
        self.assertTrue(self.model.load_tasks())
        self.assertEqual(len(self.model.pinned_tasks), 1)
        self.assertEqual(len(self.model.all_tasks), 2)
        self.assertIn("⭐ Pinned 1", self.model.pinned_tasks)
        self.assertIn("Task 1", self.model.all_tasks)

    def test_add_task(self):
        """Verify adding a new task updates the model state."""
        self.model.load_tasks()
        self.assertTrue(self.model.add_task("New Task"))
        self.assertIn("New Task", self.model.all_tasks)
        self.assertTrue(self.model.has_unsaved_changes)

    def test_archive_task(self):
        """Verify archiving a task moves it to the archive file and removes it from memory."""
        self.model.load_tasks()
        task_to_archive = "Task 1"
        self.assertTrue(self.model.archive_task(task_to_archive))
        self.assertNotIn(task_to_archive, self.model.all_tasks)

        # Check archive file
        archive_path = os.path.join(self.test_dir, "أرشيف_المهام.txt")
        self.assertTrue(os.path.exists(archive_path))
        with open(archive_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn(task_to_archive, content)

    def test_delete_task(self):
        """Verify deleting a task moves it to trash and removes it from memory."""
        self.model.load_tasks()
        task_to_delete = "Task 2"
        self.assertTrue(self.model.delete_task(task_to_delete))
        self.assertNotIn(task_to_delete, self.model.all_tasks)

        # Check trash file
        trash_path = os.path.join(self.test_dir, "trash.txt")
        self.assertTrue(os.path.exists(trash_path))
        with open(trash_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn(task_to_delete, content)

    def test_undo_archive(self):
        """Verify undoing an archive action restores the task to memory."""
        self.model.load_tasks()
        task = "Task 1"
        self.model.archive_task(task)
        self.assertTrue(self.model.undo())
        self.assertIn(task, self.model.all_tasks)

    def test_toggle_pin(self):
        """Verify pinning/unpinning correctly moves tasks between lists."""
        self.model.load_tasks()

        # Pin a regular task
        task = "Task 1"
        self.assertTrue(self.model.toggle_pin(task))
        self.assertIn("⭐ Task 1", self.model.pinned_tasks)
        self.assertNotIn(task, self.model.all_tasks)

        # Unpin a pinned task
        pinned_task = "⭐ Pinned 1"
        self.assertTrue(self.model.toggle_pin(pinned_task))
        self.assertIn("Pinned 1", self.model.all_tasks)
        self.assertNotIn(pinned_task, self.model.pinned_tasks)

    def test_edit_task(self):
        """Verify editing a task updates its content in the correct list."""
        self.model.load_tasks()

        # Edit regular task
        self.assertTrue(self.model.edit_task("Task 1", "Edited Task 1"))
        self.assertIn("Edited Task 1", self.model.all_tasks)
        self.assertNotIn("Task 1", self.model.all_tasks)

        # Edit pinned task
        self.assertTrue(self.model.edit_task("⭐ Pinned 1", "⭐ Edited Pinned"))
        self.assertIn("⭐ Edited Pinned", self.model.pinned_tasks)

    def test_move_task(self):
        """Verify task reordering works within the task's own category."""
        self.model.load_tasks()
        # Initial all_tasks: [Task 1, Task 2]
        # Move "Task 2" (index 2 in combined, index 1 in all_tasks) up
        self.assertTrue(self.model.move_task(2, -1))
        
        # After move, all_tasks should be: [Task 2, Task 1]
        self.assertEqual(self.model.all_tasks[0], "Task 2")
        self.assertEqual(self.model.all_tasks[1], "Task 1")

        # Move "⭐ Pinned 1" (index 0) - should fail if moving up or stay same
        self.assertFalse(self.model.move_task(0, -1))

    def test_atomic_save(self):
        """Verify saving updates the actual file on disk."""
        self.model.load_tasks()
        self.model.add_task("New Atomic Task")
        self.assertTrue(self.model.save_tasks_atomic())

        with open(self.project_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("New Atomic Task", content)


if __name__ == "__main__":
    unittest.main()
