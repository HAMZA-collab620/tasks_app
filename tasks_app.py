"""
Main Entry Point for the Task Management Application.
Imports and runs the main components.
"""

import sys

import wx

from dar_tasks.main_frame import MainFrame

if __name__ == "__main__":
    app = wx.App()

    # Safety Fix: Single Instance Lock
    name = "DarTasks-%s" % wx.GetUserId()
    instance_checker = wx.SingleInstanceChecker(name)
    if instance_checker.IsAnotherRunning():
        wx.MessageBox(
            "An instance of Dar Tasks is already running.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        sys.exit(0)

    MainFrame()
    app.MainLoop()
