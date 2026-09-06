"""
Targeted automated test suite for Dar Tasks domain logic and persistence invariants.
Executes against isolated temporary directories using Python's standard unittest and pathlib.Path.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from core_models import (
    DAILY_FILENAME,
    DEFAULT_ARCHIVE_NAME,
    DEFAULT_TRASH_NAME,
    PROJECT_ORDER_FILENAME,
    ProjectModel,
    ProjectWorkspace,
    SearchEngine,
    SettingsManager,
    Task,
    sanitize_project_name,
)


class TestProjectWorkspace(unittest.TestCase):
    """Verifies workspace disk operations, ordering invariants, and path manipulations."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = ProjectWorkspace(self.test_dir)
        self.daily_path = self.workspace.get_project_path(DAILY_FILENAME)
        with open(self.daily_path, "w", encoding="utf-8"):
            pass

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_project_name(self):
        self.assertEqual(sanitize_project_name("My Project!@#"), "My Project")
        self.assertEqual(sanitize_project_name("Safe_Name-1"), "Safe_Name-1")

    def test_ensure_order_includes_daily(self):
        order = self.workspace.ensure_order()
        self.assertIn(DAILY_FILENAME, order)
        self.assertTrue(self.daily_path.exists())

    def test_create_project(self):
        fn = self.workspace.create_project("Alpha Project")
        self.assertEqual(fn, "Alpha Project.txt")
        self.assertTrue(self.workspace.get_project_path(fn).exists())
        order = self.workspace.ensure_order()
        self.assertIn(fn, order)

    def test_rename_project(self):
        fn = self.workspace.create_project("Old Name")
        new_fn = self.workspace.rename_project(fn, "New Name")
        self.assertEqual(new_fn, "New Name.txt")
        self.assertFalse(self.workspace.get_project_path("Old Name.txt").exists())
        self.assertTrue(self.workspace.get_project_path("New Name.txt").exists())
        order = self.workspace.ensure_order()
        self.assertIn("New Name.txt", order)
        self.assertNotIn("Old Name.txt", order)

    def test_cannot_rename_daily(self):
        res = self.workspace.rename_project(DAILY_FILENAME, "Other")
        self.assertIsNone(res)

    def test_delete_project(self):
        fn = self.workspace.create_project("To Delete")
        deleted = self.workspace.delete_project(fn)
        self.assertTrue(deleted)
        self.assertFalse(self.workspace.get_project_path(fn).exists())
        order = self.workspace.ensure_order()
        self.assertNotIn(fn, order)

    def test_cannot_delete_daily(self):
        deleted = self.workspace.delete_project(DAILY_FILENAME)
        self.assertFalse(deleted)
        self.assertTrue(self.daily_path.exists())

    def test_toggle_pin_project(self):
        fn = self.workspace.create_project("Pinnable")
        self.assertTrue(self.workspace.toggle_pin(fn))
        order = self.workspace.ensure_order()
        self.assertIn(f"⭐ {fn}", order)
        # Unpin
        self.assertTrue(self.workspace.toggle_pin(fn))
        order = self.workspace.ensure_order()
        self.assertIn(fn, order)
        self.assertNotIn(f"⭐ {fn}", order)

    def test_move_and_reorder_project(self):
        p1 = self.workspace.create_project("P1")
        p2 = self.workspace.create_project("P2")
        order = self.workspace.ensure_order()
        idx_p1 = order.index(p1)
        idx_p2 = order.index(p2)
        # Swap
        self.assertTrue(self.workspace.move_project(idx_p1, 1))
        new_order = self.workspace.ensure_order()
        self.assertEqual(new_order[idx_p1], p2)


class TestProjectModel(unittest.TestCase):
    """Verifies single-project task handling, atomic saving, undo, and archive harvesting."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.project_path = self.test_dir / "test_proj.txt"
        with open(self.project_path, "w", encoding="utf-8") as f:
            f.write("⭐ Urgent task\nNormal task 1\nNormal task 2\n")
        self.model = ProjectModel(self.project_path, base_dir=self.test_dir)
        self.assertTrue(self.model.load_tasks())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_task_entity_serialization(self):
        task = Task.from_line("⭐ Buy milk")
        self.assertEqual(task.title, "Buy milk")
        self.assertTrue(task.is_pinned)
        self.assertEqual(task.to_line(), "⭐ Buy milk")

        normal_task = Task.from_line("Read book")
        self.assertEqual(normal_task.title, "Read book")
        self.assertFalse(normal_task.is_pinned)
        self.assertEqual(normal_task.to_line(), "Read book")

    def test_load_tasks_separates_pinned(self):
        pinned = [t for t in self.model.tasks if t.is_pinned]
        unpinned = [t for t in self.model.tasks if not t.is_pinned]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(len(unpinned), 2)
        self.assertEqual(pinned[0].title, "Urgent task")

    def test_add_and_atomic_save(self):
        self.assertTrue(self.model.add_task("New task"))
        self.assertTrue(self.model.save_tasks_atomic())
        with open(self.project_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertIn("New task", lines)
        self.assertIn("⭐ Urgent task", lines)

    def test_archive_task_and_harvest(self):
        task_to_archive = "Normal task 1"
        self.assertTrue(self.model.archive_task(task_to_archive))
        self.assertTrue(self.model.archive_file.exists())
        with open(self.model.archive_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(task_to_archive, content)

        # Harvest query test
        harvest = ProjectModel.get_today_harvest(base_dir=self.test_dir)
        self.assertEqual(len(harvest), 1)
        self.assertIn(task_to_archive, harvest[0])

    def test_delete_task_isolates_in_trash(self):
        task_to_delete = "Normal task 2"
        self.assertTrue(self.model.delete_task(task_to_delete))
        self.assertTrue(self.model.trash_file.exists())
        with open(self.model.trash_file, "r", encoding="utf-8") as f:
            trash_content = f.read()
        self.assertIn(task_to_delete, trash_content)

    def test_undo_archive(self):
        task_to_archive = "Normal task 1"
        self.assertTrue(self.model.archive_task(task_to_archive))
        self.assertTrue(self.model.undo())
        titles = [t.title for t in self.model.tasks]
        self.assertIn(task_to_archive, titles)


class TestSearchEngine(unittest.TestCase):
    """Verifies multi-project query logic."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = ProjectWorkspace(self.test_dir)
        self.p1 = self.workspace.create_project("Project Alpha")
        self.p2 = self.workspace.create_project("Project Beta")
        with open(self.workspace.get_project_path(self.p1), "w", encoding="utf-8") as f:
            f.write("Fix critical authentication bug\nReview PR\n")
        with open(self.workspace.get_project_path(self.p2), "w", encoding="utf-8") as f:
            f.write("Update documentation\nDeploy bug fix to staging\n")
        self.engine = SearchEngine(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_search_finds_matches_across_projects(self):
        results = self.engine.search("bug")
        self.assertEqual(len(results), 2)
        tasks = [r["task"] for r in results]
        self.assertTrue(any("authentication" in t for t in tasks))
        self.assertTrue(any("staging" in t for t in tasks))

    def test_search_project_specific(self):
        results = self.engine.search("bug", project_filename=self.p1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], self.p1)

    def test_search_short_query_returns_empty(self):
        self.assertEqual(self.engine.search("a"), [])

    def test_search_case_sensitive(self):
        self.assertEqual(len(self.engine.search("Fix", case_sensitive=True)), 1)
        self.assertEqual(len(self.engine.search("fix", case_sensitive=True)), 1)
        self.assertEqual(len(self.engine.search("fix", case_sensitive=False)), 2)


class TestSettingsManager(unittest.TestCase):
    """Verifies settings JSON persistence and defaults."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.mgr = SettingsManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_values(self):
        self.assertEqual(self.mgr.get("general", "language"), "en")
        self.assertFalse(self.mgr.get("behavior", "confirm_on_archive"))

    def test_modify_and_persist(self):
        self.mgr.set("general", "language", "ar")
        self.mgr.save()
        new_mgr = SettingsManager(self.test_dir)
        self.assertEqual(new_mgr.get("general", "language"), "ar")


if __name__ == "__main__":
    unittest.main()
