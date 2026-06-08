"""
Settings Management Module for the Task Management Application.
Handles loading, saving, and managing application settings.
"""

import json
import os
import copy
from dar_tasks.logger import logger


class SettingsManager:
    """Manages application settings with JSON persistence."""

    DEFAULT_SETTINGS = {
        "behavior": {
            "confirm_on_archive": False,
            "confirm_on_delete": True,
            "auto_save_interval": 2,
            "show_undo_notifications": True,
        },
        "backup": {
            "auto_backup_frequency": "daily",
            "backup_retention_days": 30,
            "trash_retention_days": 7,
            "archive_location": "",
        },
        "appearance": {
            "theme": "dark",
            "font_size": 14,
            "start_maximized": False,
            "custom_bg_color": None,
            "custom_accent_color": None,
            "custom_fg_color": None,
        },
        "search": {
            "lazy_load_threshold": 100,
            "show_project_count": True,
            "sort_by": "manual",
            "case_sensitive": False,
        },
        "general": {
            "check_updates": True,
            "show_tips": True,
            "time_format_24h": True,
            "language": "en",
        },
    }

    def __init__(self, app_dir):
        """Initialize settings manager with app directory."""
        self.app_dir = app_dir
        self.settings_file = os.path.join(app_dir, ".app_settings.json")
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self.load()

    def load(self):
        """Load settings from JSON file, use defaults if missing."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Deep merge saved settings with defaults
                    self._deep_merge(self.settings, saved)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading settings: {e}. Using defaults.")

    def save(self):
        """Save current settings to JSON file using an atomic pattern."""
        import tempfile

        tempname = None
        try:
            dir_name = os.path.dirname(self.settings_file)
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(self.settings, tf, indent=2, ensure_ascii=False)
                tempname = tf.name

            os.replace(tempname, self.settings_file)
        except (IOError, OSError) as e:
            logger.error(f"Error saving settings: {e}")
            if tempname and os.path.exists(tempname):
                try:
                    os.remove(tempname)
                except OSError:
                    pass

    def get(self, section, key, default=None):
        """Get a setting value by section and key."""
        try:
            return self.settings.get(section, {}).get(key, default)
        except (KeyError, TypeError):
            return default

    def set(self, section, key, value):
        """Set a setting value by section and key."""
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value

    def get_section(self, section):
        """Get an entire settings section."""
        return self.settings.get(section, {})

    def set_section(self, section, values):
        """Set an entire settings section."""
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section].update(values)

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.settings = json.loads(json.dumps(self.DEFAULT_SETTINGS))
        self.save()

    def reset_section(self, section):
        """Reset a specific section to defaults."""
        if section in self.DEFAULT_SETTINGS:
            self.settings[section] = json.loads(json.dumps(self.DEFAULT_SETTINGS[section]))

    def _deep_merge(self, target, source):
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if isinstance(value, dict) and key in target:
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def export_settings(self, filepath):
        """Export settings to a file."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False

    def import_settings(self, filepath):
        """Import settings from a file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                imported = json.load(f)
                self._deep_merge(self.settings, imported)
                self.save()
                return True
        except (json.JSONDecodeError, IOError):
            return False
