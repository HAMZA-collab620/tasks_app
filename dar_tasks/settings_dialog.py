import wx
from dar_tasks.constants import BG_COLOR
from dar_tasks.ui_factory import create_button
from dar_tasks.utils import load_json_data


def create_setting_widget(parent, info):
    if info["type"] == "checkbox":
        return wx.CheckBox(parent, label=info["label"])
    if info["type"] == "spin":
        return wx.SpinCtrl(parent, min=info.get("min", 0), max=info.get("max", 100))
    if info["type"] == "choice":
        return wx.Choice(parent, choices=info["choices"])
    return None


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, settings_manager):
        super().__init__(parent, title="Settings", size=(600, 500))
        self.settings_manager = settings_manager
        self.tabs_data = load_json_data("settings_layout.json", [])
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)
        for tab in self.tabs_data:
            panel = wx.Panel(self.notebook)
            panel.SetBackgroundColour(BG_COLOR)
            sizer = wx.BoxSizer(wx.VERTICAL)
            for w in tab["widgets"]:
                h_sizer = wx.BoxSizer(wx.HORIZONTAL)
                if w["type"] != "checkbox":
                    h_sizer.Add(wx.StaticText(panel, label=w["label"]), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                ctrl = create_setting_widget(panel, w)
                if w["type"] == "checkbox":
                    ctrl.SetLabel(w["label"])
                setattr(self, w["attr"], ctrl)
                h_sizer.Add(ctrl, 1 if w["type"] == "choice" else 0, wx.ALL, 5)
                sizer.Add(h_sizer, 0, wx.ALL, 5)
            sizer.AddStretchSpacer()
            panel.SetSizer(sizer)
            self.notebook.AddPage(panel, tab["title"])

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for lbl, hnd in [
            ("Reset to Defaults", self.on_reset),
            ("Save", self.on_save),
            ("Cancel", lambda e: self.EndModal(wx.ID_CANCEL)),
        ]:
            btn_sizer.Add(create_button(self, lbl, handler=hnd), 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizer(main_sizer)

    def load_settings(self):
        for tab in self.tabs_data:
            for w in tab["widgets"]:
                ctrl, val = getattr(self, w["attr"]), self.settings_manager.get(w["section"], w["key"])
                if w["type"] == "checkbox":
                    ctrl.SetValue(bool(val))
                elif w["type"] == "spin":
                    ctrl.SetValue(int(val))
                elif w["type"] == "choice":
                    try:
                        ctrl.SetSelection(w["map"].index(val.lower() if isinstance(val, str) else val))
                    except (ValueError, AttributeError):
                        ctrl.SetSelection(0)

    def save_settings(self):
        for tab in self.tabs_data:
            for w in tab["widgets"]:
                ctrl = getattr(self, w["attr"])
                val = ctrl.GetValue() if w["type"] != "choice" else w["map"][ctrl.GetSelection()]
                self.settings_manager.set(w["section"], w["key"], val)
        self.settings_manager.save()

    def on_save(self, e):
        self.save_settings()
        self.EndModal(wx.ID_OK)

    def on_reset(self, e):
        if wx.MessageBox("Reset?", "Confirm", wx.YES_NO) == wx.YES:
            self.settings_manager.reset_to_defaults()
            self.load_settings()
