"""
Theme and Appearance management for the Dar Tasks application.
"""

import wx
from dar_tasks.constants import ACCENT_COLOR, BG_COLOR, FG_COLOR


class ThemeManager:
    """Handles applying themes, fonts, and window sizing to the UI."""

    def __init__(self, settings_manager):
        self.settings = settings_manager

    def apply_theme(self, frame):
        """Apply theme settings with support for custom colors to the frame and its components."""
        theme = self.settings.get("appearance", "theme", "dark").lower()

        # Defaults
        if theme == "light":
            bg = wx.Colour(240, 240, 240)
            fg = wx.Colour(30, 30, 30)
            accent = wx.Colour(200, 200, 200)
        else:  # Dark
            bg = BG_COLOR
            fg = FG_COLOR
            accent = ACCENT_COLOR

        # Override with custom if present
        custom_bg = self.settings.get("appearance", "custom_bg_color")
        custom_fg = self.settings.get("appearance", "custom_fg_color")
        custom_accent = self.settings.get("appearance", "custom_accent_color")

        if custom_bg:
            bg = wx.Colour(custom_bg)
        if custom_fg:
            fg = wx.Colour(custom_fg)
        if custom_accent:
            accent = wx.Colour(custom_accent)

        frame.panel.SetBackgroundColour(bg)

        # Update toolbar buttons dynamically from frame's toolbar data
        if hasattr(frame, "toolbar_data"):
            for item in frame.toolbar_data:
                btn = getattr(frame, item["attr"])
                btn.SetBackgroundColour(accent)
                btn.SetForegroundColour(fg)

        # Update notebook pages
        for i in range(frame.notebook.GetPageCount()):
            page = frame.notebook.GetPage(i)
            if hasattr(page, "update_theme_colors"):
                page.update_theme_colors(bg, fg, accent)

        frame.Refresh()

    def apply_font_size(self, frame):
        """Apply font size settings to all task panels."""
        font_size = self.settings.get("appearance", "font_size", 14)
        font_size = max(10, min(18, font_size))  # Clamp to valid range

        for i in range(frame.notebook.GetPageCount()):
            page = frame.notebook.GetPage(i)
            if hasattr(page, "update_font_size"):
                page.update_font_size(font_size)

    def apply_window_size(self, frame):
        """Apply window size settings like maximization."""
        start_maximized = self.settings.get("appearance", "start_maximized", False)
        if start_maximized:
            frame.Maximize()

    def apply_all(self, frame):
        """Apply all appearance settings at once."""
        self.apply_theme(frame)
        self.apply_font_size(frame)
        self.apply_window_size(frame)
