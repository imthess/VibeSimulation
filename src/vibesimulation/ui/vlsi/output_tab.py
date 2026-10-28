"""Bottom panel, tab 2: what a run printed ($display, $monitor ...) and how it ended."""
import tkinter as tk
from tkinter import ttk

from ..theme import auto


class OutputTab(tk.Frame):
    def __init__(self, ctx, master):
        super().__init__(master, bd=0); self.ctx = ctx
        self.t = tk.Text(self, height=6, wrap="none", bd=0, highlightthickness=0, padx=12, pady=8, relief="flat", font=ctx.f_mono, cursor="arrow")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.t.yview, style="Thin.Vertical.TScrollbar"); self.t.configure(yscrollcommand=auto(sb, self.t))
        self.t.pack(side="left", fill="both", expand=True)
        self.t.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in "ca") or e.keysym in ("Up", "Down", "Prior", "Next", "Home", "End") else "break")
        ctx.themed.append(self.paint); self.paint()
        self.clear("Press  ▶ Run  to simulate. A testbench written in the Testbench tab is used; without one a clock, a reset and random inputs are generated.")

    def paint(self):
        P = self.ctx.P
        self.t.configure(bg=P["field"], fg=P["text"], insertbackground=P["text"], selectbackground=P["sel"])
        self.t.tag_configure("head", foreground=P["accent"]); self.t.tag_configure("bad", foreground=P["bad"]); self.t.tag_configure("warn", foreground="#b45309" if not self.ctx.dark else "#fbbf24")
        self.t.tag_configure("muted", foreground=P["muted"])

    def clear(self, note=""):
        self.t.delete("1.0", "end")
        if note: self.t.insert("end", note + "\n", "muted")

    def show(self, result, label):
        t = self.t; t.delete("1.0", "end")
        t.insert("end", f"▶ {label}\n", "head")
        for w in result.warnings: t.insert("end", f"⚠ line {w[0]}: {w[1]}\n", "warn")
        for ln in result.lines: t.insert("end", ln + "\n")
        if result.error: t.insert("end", f"✘ line {getattr(result.error, 'line', '?')}: {result.error.msg}\n", "bad")
        end = f"time {result.end_time}"
        if result.finished: t.insert("end", f"■ $finish at {end}\n", "muted")
        elif result.truncated: t.insert("end", f"■ stopped at {end}: {result.truncated}\n", "warn")
        elif not result.error: t.insert("end", f"■ nothing left to do at {end}\n", "muted")
        t.see("end")
