"""
UI Factory for consistent widget creation across the application.
Provides helper functions for creating styled and accessible UI components.
"""

import wx

from dar_tasks.constants import ACCENT_COLOR, FG_COLOR


def create_button(parent, label, tooltip=None, handler=None, btn_id=wx.ID_ANY):
    """Create a styled button with optional tooltip and event handler."""
    btn = wx.Button(parent, id=btn_id, label=label)
    btn.SetBackgroundColour(ACCENT_COLOR)
    btn.SetForegroundColour(FG_COLOR)
    if tooltip:
        btn.SetToolTip(tooltip)
    if handler:
        btn.Bind(wx.EVT_BUTTON, handler)
    return btn


def create_static_text(parent, label, fg_color=FG_COLOR):
    """Create styled static text."""
    txt = wx.StaticText(parent, label=label)
    txt.SetForegroundColour(fg_color)
    return txt


def create_spin_ctrl(parent, value="", min=0, max=100, initial=0):
    """Create a styled spin control."""
    sc = wx.SpinCtrl(parent, value=value, min=min, max=max, initial=initial)
    sc.SetBackgroundColour(ACCENT_COLOR)
    sc.SetForegroundColour(FG_COLOR)
    return sc


def create_choice(parent, choices, selection=0):
    """Create a styled choice control."""
    ch = wx.Choice(parent, choices=choices)
    ch.SetSelection(selection)
    ch.SetBackgroundColour(ACCENT_COLOR)
    ch.SetForegroundColour(FG_COLOR)
    return ch


def create_text_ctrl(parent, value="", tooltip=None, handler=None, style=0):
    """Create a styled text control."""
    tc = wx.TextCtrl(parent, value=value, style=style)
    tc.SetBackgroundColour(ACCENT_COLOR)
    tc.SetForegroundColour(FG_COLOR)
    if tooltip:
        tc.SetToolTip(tooltip)
    if handler:
        # Bind enter event if TE_PROCESS_ENTER is set, else default text event
        if style & wx.TE_PROCESS_ENTER:
            tc.Bind(wx.EVT_TEXT_ENTER, handler)
        else:
            tc.Bind(wx.EVT_TEXT, handler)
    return tc


def create_list_box(parent, choices=None, tooltip=None, style=0):
    """Create a styled list box."""
    lb = wx.ListBox(parent, choices=choices or [], style=style)
    lb.SetBackgroundColour(ACCENT_COLOR)
    lb.SetForegroundColour(FG_COLOR)
    if tooltip:
        lb.SetToolTip(tooltip)
    return lb
