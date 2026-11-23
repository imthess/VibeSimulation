"""UiContext: what every widget needs - palette, fonts, dialogs, saved settings."""
import json
import time
import tkinter as tk
from pathlib import Path

from vibesimulation.ui.window.dialogs import Dialog
from vibesimulation.ui.navigation.file_browser import FileDialog
from vibesimulation.ui.window.popup import PopupMenu
from vibesimulation.ui.look.theme import Theme
from vibesimulation.ui.controls.widgets import Toast
CFG = Path.home() / ".vibesimulation.json"
OLD_CFG = Path.home() / ".circuitsim.json"


class UiContext(Theme):
    def __init__(self, root):
        self.cfg = {}
        for f in (CFG, OLD_CFG):
            try:
                self.cfg = json.loads(f.read_text(encoding="utf-8")); break
            except Exception:
                pass
        super().__init__(root, self.cfg)
        from vibesimulation.ui.look.glass import Glass
        self.glass = Glass(self)
        self.toaster = Toast(self); self.popup = None; self.popup_closed = None

    def save_cfg(self):
        try:
            CFG.write_text(json.dumps(self.cfg), encoding="utf-8")
        except Exception:
            pass

    # ---- dialogs
    def toast(self, msg, kind="info"): self.toaster.show(msg, kind)

    def say(self, title, msg, parent=None):
        if title == "Saved" and "\n" not in msg:
            return self.toast("Saved  ·  " + msg, "ok")
        Dialog(self, title, msg, parent).wait_window()

    def ask(self, title, msg, parent=None):
        d = Dialog(self, title, msg, parent, ask=True); d.wait_window(); return bool(d.result)

    def ask_string(self, title, msg, initial=""):
        d = Dialog(self, title, msg, field=initial); d.wait_window(); return d.result

    def pick_circuits(self, names, current, title="Save which circuits?"):
        """List of the circuits (tabs) the user ticked, or None if cancelled. One circuit: no question."""
        if len(names) < 2: return list(names)
        from vibesimulation.ui.window.dialogs import PickCircuits
        d = PickCircuits(self, names, current, title); d.wait_window(); return d.result

    def ask_form(self, title, msg, fields, check=None):
        from vibesimulation.ui.window.dialogs import FormDialog
        d = FormDialog(self, title, msg, fields, check); d.wait_window(); return d.result

    def choose_file(self, mode, title, exts, name=""):
        d = FileDialog(self, mode, title, exts, self.cfg.get("last_dir"), name); d.wait_window()
        if d.result:
            self.cfg["last_dir"] = str(Path(d.result).parent); self.add_recent(d.result)
        return d.result

    def add_recent(self, path):
        r = [x for x in self.cfg.get("recent", []) if x[0] != str(path)]
        self.cfg["recent"] = ([[str(path), time.time()]] + r)[:60]; self.save_cfg()

    def menu(self):
        return PopupMenu(self)

    def close_popups(self):
        if self.popup is not None: self.popup.close_all()
