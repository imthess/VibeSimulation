"""Help > Examples gallery: pick an example, read its short tutorial, open it in its workspace."""
import tkinter as tk

from ...product.examples import EXAMPLES
from ..widgets import Btn
from .box import Box

SECTIONS = (("logisim", "Logisim"), ("multisim", "Multisim"), ("vlsi", "VLSI"))


class GalleryBox(Box):
    def __init__(self, ctx, shell, section=None):
        self.shell, self.sec = shell, section or (shell.workspace_key() if hasattr(shell, "workspace_key") else "logisim"); self.sel = None
        super().__init__(ctx, "Examples gallery", 820, 520)

    def build(self, b):
        ctx, P = self.ctx, self.ctx.P
        b.columnconfigure(1, weight=1); b.rowconfigure(1, weight=1)
        tabs = tk.Frame(b, bg=P["card"]); tabs.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.tabs = {}
        for key, name in SECTIONS:
            t = Btn(ctx, tabs, name, lambda k=key: self.pick_section(k), "secondary", padx=14, pady=4); t.pack(side="left", padx=(0, 6)); self.tabs[key] = t
        self.list = tk.Listbox(b, width=34, activestyle="none", exportselection=False, bd=0, highlightthickness=1, font=ctx.f_body, bg=P["field"], fg=P["text"],
                               selectbackground=P["accent"], selectforeground=P["accent_fg"], highlightbackground=P["border"])
        self.list.grid(row=1, column=0, sticky="ns", padx=(0, 16)); self.list.bind("<<ListboxSelect>>", lambda e: self.pick())
        self.list.bind("<Double-1>", lambda e: self.open())
        right = tk.Frame(b, bg=P["card"]); right.grid(row=1, column=1, sticky="nsew"); right.columnconfigure(0, weight=1)
        self.h = self.label(right, "", "title"); self.h.grid(row=0, column=0, sticky="ew")
        self.lv = self.label(right, "", "small"); self.lv.grid(row=1, column=0, sticky="ew")
        self.sm = self.label(right, "", "body", wraplength=440); self.sm.grid(row=2, column=0, sticky="ew", pady=(8, 8))
        self.label(right, "Short tutorial", "small").grid(row=3, column=0, sticky="ew")
        self.st = self.label(right, "", "body", wraplength=440); self.st.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        row = tk.Frame(b, bg=P["card"]); row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        Btn(ctx, row, "Close", self.destroy, "secondary").pack(side="right")
        self.b_open = Btn(ctx, row, "Open example", self.open, "primary"); self.b_open.pack(side="right", padx=8)
        self.note = self.label(row, "Opening replaces what is in that workspace now Save first if you want to keep it.", "small"); self.note.pack(side="left")
        self.pick_section(self.sec if self.sec in dict(SECTIONS) else "logisim")

    def pick_section(self, key):
        self.sec = key; self.items = [e for e in EXAMPLES if e.section == key]
        for k, t in self.tabs.items(): t.kind = "primary" if k == key else "secondary"; t.paint()
        self.list.delete(0, "end")
        for e in self.items: self.list.insert("end", e.title)
        self.list.selection_set(0); self.pick()

    def pick(self):
        s = self.list.curselection()
        if not s: return
        e = self.sel = self.items[s[0]]
        self.h.configure(text=e.title); self.lv.configure(text=f"{e.level}  ·  {dict(SECTIONS)[e.section]}"); self.sm.configure(text=e.summary)
        self.st.configure(text="\n".join(f"{i}.  {t}" for i, t in enumerate(e.steps, 1)), wraplength=440)

    def open(self):
        if self.sel is None: return
        open_example(self.shell, self.sel); self.destroy()


def open_example(sh, e):
    """Load an example into its workspace and show it."""
    if e.section == "logisim": sh.doc.load_text(e.text); sh.doc.set_inputs({})
    elif e.section == "multisim": sh.adoc.load_text(e.text)
    else:
        sh.vdoc.new_blank(e.text); sh.vdoc.set_inputs({})
        if e.testbench: sh.vdoc.set_testbench(e.testbench)
    sh.show(e.section)
    sh.ctx.toast(f"Opened example: {e.title}")
