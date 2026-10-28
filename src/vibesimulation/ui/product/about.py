"""Help > About: version, the system it runs on and the update check."""
import platform
import queue
import sys
import tkinter as tk
import webbrowser

from ... import APP_NAME, __version__
from ...product import updates
from ..widgets import Btn
from .box import Box

LICENSE = "Free software. Logisim-style simulation, SPICE-style analog analysis and Verilog synthesis are written from scratch; no code from those tools is included."


class AboutBox(Box):
    def __init__(self, ctx, shell):
        self.shell = shell; super().__init__(ctx, f"About {APP_NAME}", 520)

    def build(self, b):
        ctx = self.ctx
        self.label(b, f"{APP_NAME}", "title").pack(fill="x")
        self.label(b, f"Version {__version__}").pack(fill="x", pady=(2, 8))
        self.label(b, "Three workspaces in one free desktop app: Logisim-style digital circuits, Multisim-style analog circuits, and VLSI (Verilog to circuit, testbenches and waveforms).", "body", wraplength=470).pack(fill="x")
        self.label(b, LICENSE, "small", wraplength=470).pack(fill="x", pady=(8, 8))
        try: import tkinter; tk_v = tkinter.TkVersion
        except Exception: tk_v = "?"
        self.label(b, f"Python {platform.python_version()}  ·  Tk {tk_v}  ·  {platform.system()} {platform.release()}", "small").pack(fill="x")
        self.res = self.label(b, "", "small", wraplength=470); self.res.pack(fill="x", pady=(10, 0))
        row = tk.Frame(b, bg=ctx.P["card"]); row.pack(fill="x", pady=(16, 0))
        Btn(ctx, row, "Close", self.destroy, "primary").pack(side="right")
        self.b_up = Btn(ctx, row, "Check for updates", self.check, "secondary"); self.b_up.pack(side="right", padx=8)
        self.link = None

    def check(self):
        check_for_updates(self.ctx, self.shell, self.show_result, interactive=True)

    def show_result(self, text, kind="info", url=""):
        P = self.ctx.P
        try: self.res.configure(text=text, fg={"ok": P["ok"], "bad": P["bad"]}.get(kind, P["muted"]))
        except tk.TclError: return
        if url and self.link is None:
            self.link = Btn(self.ctx, self.res.master, "Open download page", lambda: webbrowser.open(url), "ghost", padx=6, pady=2)
            self.link.pack(after=self.res, anchor="w")


def check_for_updates(ctx, shell, report, interactive):
    """Run the update check. report(text, kind, url) shows the answer. Without an address nothing is contacted."""
    url = str(ctx.cfg.get("update_url", "")).strip()
    if not url:
        if interactive: report("No update address is set, so nothing was checked. Put one in Settings (update_url in the settings file) to enable update checks.", "info")
        return
    if interactive: report("Checking…", "info")

    def done(newer, info, err):
        if err: report(f"Could not check for updates: {err}", "bad") if interactive else None; return
        ctx.cfg["last_update_check"] = __import__("time").time(); ctx.save_cfg()
        if newer: report(f"Version {info['version']} is available (you have {__version__}).", "ok", info["url"])
        elif interactive: report(f"You have the newest version ({__version__}).", "ok")
    q = queue.Queue()

    def poll():                       # the answer comes from a thread; Tk is only touched from this (main) thread
        try:
            while True: q.get_nowait()()
        except queue.Empty: pass
        if not q.empty() or waiting[0]: ctx.root.after(100, poll)
    waiting = [True]

    def finish(f): waiting[0] = False; q.put(f)
    updates.check_async(url, __version__, done, finish); ctx.root.after(100, poll)
