import unittest
import os
import shutil
import tempfile
import json
from dar_tasks.utils import sanitize_project_name, get_base_dir
from dar_tasks.settings_manager import SettingsManager
from dar_tasks.project_utils import (
    get_project_order,
    save_project_order,
    extract_filename_from_entry,
)


class TestDarTasksLogic(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for projects
        self.test_dir = tempfile.mkdtemp()
        self.projects_dir = os.path.join(self.test_dir, "projects")
        os.makedirs(self.projects_dir)

    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    def test_sanitize_project_name(self):
        self.assertEqual(sanitize_project_name("My Project!"), "My Project")
        self.assertEqual(sanitize_project_name("Project_123"), "Project_123")
        self.assertEqual(sanitize_project_name("  Trim Me  "), "Trim Me")
        self.assertEqual(sanitize_project_name("Valid-Name"), "Valid-Name")

    def test_settings_manager_defaults(self):
        sm = SettingsManager(self.test_dir)
        self.assertEqual(sm.get("appearance", "theme"), "dark")
        self.assertEqual(sm.get("behavior", "auto_save_interval"), 2)
        self.assertEqual(sm.get("general", "language"), "en")

    def test_settings_manager_save_load(self):
        sm = SettingsManager(self.test_dir)
        sm.set("appearance", "theme", "light")
        sm.save()

        # Load in a new manager
        sm2 = SettingsManager(self.test_dir)
        self.assertEqual(sm2.get("appearance", "theme"), "light")

    def test_project_order_logic(self):
        # Create some dummy files
        files = ["Alpha.txt", "Beta.txt", "daily.txt"]
        for f in files:
            open(os.path.join(self.projects_dir, f), "w").close()

        # Test initial order (should prioritize daily.txt)
        order = get_project_order(self.projects_dir)
        self.assertIn("daily.txt", order)
        self.assertEqual(extract_filename_from_entry(order[0]), "daily.txt")

        # Save custom order
        custom_order = ["Beta.txt", "Alpha.txt", "daily.txt"]
        save_project_order(self.projects_dir, custom_order)

        # Verify custom order
        new_order = get_project_order(self.projects_dir)
        self.assertEqual(new_order, custom_order)

    def test_extract_filename(self):
        self.assertEqual(extract_filename_from_entry("⭐ Project.txt"), "Project.txt")
        self.assertEqual(extract_filename_from_entry("Normal.txt"), "Normal.txt")


if __name__ == "__main__":
    unittest.main()
