"""
Translation management for the Dar Tasks application.
Loads strings from translations.json.
"""

from dar_tasks.utils import load_json_data


class Translator:
    """Manages translations and provides localized strings from JSON."""

    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.all_translations = load_json_data("translations.json")
        self.setup_translations()

    def setup_translations(self):
        """Select translations based on current language setting."""
        lang = self.settings.get("general", "language", "en")
        self.trans = self.all_translations.get(lang, self.all_translations.get("en", {}))

    def translate(self, key):
        """Translate a key to the current language."""
        return self.trans.get(key, key)

    def _(self, key):
        """Short alias for translate."""
        return self.translate(key)
