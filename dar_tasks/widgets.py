"""
Custom Reusable UI Components (Subclassing).
Reduces complexity and promotes standardized layouts.
"""

import wx
from dar_tasks.ui_factory import create_static_text, create_text_ctrl, create_list_box


class LabeledControl(wx.Panel):
    """Base class for pairing a label with a control."""

    def __init__(self, parent, label, control_creator, orient=wx.HORIZONTAL):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(orient)

        self.label_txt = create_static_text(self, label=label)
        self.sizer.Add(self.label_txt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.control = control_creator(self)
        self.sizer.Add(self.control, 1, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(self.sizer)


class LabeledTextCtrl(LabeledControl):
    """A labeled text ctrl."""

    def __init__(self, parent, label, *args, **kwargs):
        super().__init__(parent, label, lambda p: create_text_ctrl(p, *args, **kwargs))


class TaskListBox(wx.Panel):
    """Standard task list component with label and styling."""

    def __init__(self, parent, label, tooltip=None):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.label_txt = create_static_text(self, label=label)
        self.sizer.Add(self.label_txt, 0, wx.LEFT | wx.TOP, 5)

        self.list_box = create_list_box(self, tooltip=tooltip, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.sizer.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(self.sizer)
