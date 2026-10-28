"""The explorer of the VLSI page (next to the activity bar): the project's modules, snippet templates and library cells."""
import tkinter as tk
from tkinter import ttk

from ...components.registry import ComponentRegistry as R
from ...verilog.emit import cellname
from ..widgets import Btn
from .templates import TEMPLATES


def _tree(ctx, parent):
    f = tk.Frame(parent, bd=0); t = ttk.Treeview(f, show="tree", selectmode="browse", style="Side.Treeview")
    sb = ttk.Scrollbar(f, orient="vertical", command=t.yview, style="Thin.Vertical.TScrollbar"); t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); t.pack(side="left", fill="both", expand=True, padx=(6, 0)); return f, t


class VlsiExplorer(tk.Frame):
    """Double-click a module to open it, a template to insert it at the cursor, or a library cell to insert an instance of it."""
    DOC, PAGE, TEMPLATES = "vdoc", "vlsi", TEMPLATES            # the SystemVerilog explorer changes these three
    NEW_MODULE = "module {n} (\n  input  a,\n  output y\n);\n  assign y = a;\nendmodule\n"

    @property
    def doc(self): return getattr(self.sh, self.DOC)

    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell; self.items = {}
        self.bar = bar = tk.Frame(self, bd=0); bar.pack(fill="x", padx=10, pady=(0, 6))
        Btn(ctx, bar, "+ Module", self.new_module, "secondary", pady=3, padx=9).tip("Add another module (circuit) to this project").pack(side="left")
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        self.note = tk.Label(self, text="Double-click to open or insert.", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.note.pack(fill="x", padx=16, pady=(4, 8))
        self.t.bind("<Double-1>", self._double); self.t.bind("<Return>", self._double)
        self.t.tag_configure("cur", font=ctx.f_bold)
        self.paint()
        self.doc.subscribe(self._on_doc)

    def paint(self):
        P = self.ctx.P
        self.note.configure(bg=P["soft"], fg=P["muted"]); self.configure(bg=P["soft"]); self.bar.configure(bg=P["soft"]); self.f.configure(bg=P["soft"])

    def _on_doc(self, kind):
        if kind in ("changed", "circuits") and self.winfo_ismapped(): self.refresh()

    def refresh(self):
        t = self.t; t.delete(*t.get_children()); self.items = {}; d = self.doc
        proj = t.insert("", "end", text="Project", open=True)
        for n in d.circuit_names():
            i = t.insert(proj, "end", text=("▣  " + n), tags=("cur",) if n == d.cur else ()); self.items[i] = ("module", n)
        tp = t.insert("", "end", text="Templates", open=False)
        for name, text in self.TEMPLATES: i = t.insert(tp, "end", text=name); self.items[i] = ("template", text)
        lib = t.insert("", "end", text="Library cells (vs_)", open=False)
        for cls in sorted({c for c in R._classes.values()}, key=lambda c: (c.library, c.type_name)):
            if getattr(cls, "is_sub", False) or cls.type_name == "Circuit": continue
            i = t.insert(lib, "end", text=cls.type_name); self.items[i] = ("cell", cls)

    def _editor(self): return self.sh.pages[self.PAGE].views["verilog"]

    def _double(self, _e=None):
        sel = self.t.selection()
        if not sel or sel[0] not in self.items: return "break"
        kind, v = self.items[sel[0]]
        if kind == "module": self.doc.switch(v)
        elif kind == "template": self._insert(v)
        elif kind == "cell": self._insert(self.cell_text(v))
        return "break"

    @staticmethod
    def cell_text(cls):
        proto = cls("x")
        pins = ", ".join(f".{p.name}()" for p in proto.all_ports() if not p.optional)
        return f"  {cellname(cls.type_name)} u1 ({pins});\n"

    def _insert(self, text):
        v = self._editor(); v.txt.focus_set(); v.txt.insert("insert", text); v.txt.edit_modified(True); v._modified()

    def new_module(self):
        n = self.ctx.ask_string("New module", "Name of the new module:", f"module{len(self.doc.circuit_names()) + 1}")
        if not n: return
        err = self.doc.add_circuit(n)
        if err: self.ctx.say("New module", err)
        else:
            self.doc.set_verilog(self.NEW_MODULE.format(n=n))
