"""Bottom panel, tab 1: errors and warnings of the last compile. Double-click one to jump to its line."""
import tkinter as tk
from tkinter import ttk


class ProblemsTab(tk.Frame):
    def __init__(self, ctx, master, doc, page):
        super().__init__(master, bd=0); self.ctx, self.doc, self.page = ctx, doc, page
        self.t = ttk.Treeview(self, columns=("line", "msg"), show="tree headings", selectmode="browse", style="Side.Treeview", height=5)
        self.t.heading("#0", text=""); self.t.heading("line", text="Line"); self.t.heading("msg", text="Message")
        self.t.column("#0", width=34, stretch=False); self.t.column("line", width=56, stretch=False, anchor="e"); self.t.column("msg", width=600, stretch=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.t.yview, style="Thin.Vertical.TScrollbar"); self.t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.t.pack(side="left", fill="both", expand=True)
        self.t.bind("<Double-1>", self._go); self.t.bind("<Return>", self._go)
        self.rows = {}
        self.refresh()

    def refresh(self):
        t = self.t; t.delete(*t.get_children()); self.rows = {}
        for sev, line, msg in self.doc.problems:
            i = t.insert("", "end", text="✘" if sev == "error" else "⚠", values=(line, msg), tags=(sev,)); self.rows[i] = line
        P = self.ctx.P
        t.tag_configure("error", foreground=P["bad"]); t.tag_configure("warning", foreground="#b45309" if not self.ctx.dark else "#fbbf24")
        if not self.doc.problems: t.insert("", "end", text="✔", values=("", "No problems."))

    def counts(self):
        e = sum(1 for p in self.doc.problems if p[0] == "error"); w = len(self.doc.problems) - e
        return e, w

    def _go(self, _e=None):
        sel = self.t.selection()
        if sel and sel[0] in self.rows: self.page.goto_line(self.rows[sel[0]])
        return "break"
