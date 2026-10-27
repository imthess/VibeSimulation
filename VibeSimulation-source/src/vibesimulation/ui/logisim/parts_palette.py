"""Dialogs for choosing parts: the Parts palette (like Logisim's explorer) and the Properties form."""
import tkinter as tk
from tkinter import ttk

from ...components.registry import ComponentRegistry as R
from ...presets import PRESETS
from .parts_folders import FOLDERS
from ..widgets import Btn


def attr_form(ctx, parent, comp_cls, values):
    """Build entry widgets for a component's settings. Returns {name: getter}."""
    getters = {}
    for i, a in enumerate(comp_cls.attrs_spec):
        tk.Label(parent, text=a.label or a.name, bg=ctx.P["card"], fg=ctx.P["muted"], font=ctx.f_small, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
        cur = values.get(a.name, a.default)
        if a.kind == "choice":
            v = tk.StringVar(value=str(cur)); w = ttk.Combobox(parent, textvariable=v, values=list(a.choices), state="readonly", style="Modern.TCombobox", width=12)
            getters[a.name] = lambda v=v, a=a: next((c for c in a.choices if str(c) == v.get()), v.get())
        elif a.kind == "bool":
            v = tk.BooleanVar(value=bool(cur)); w = ttk.Checkbutton(parent, variable=v, style="Card.TCheckbutton"); getters[a.name] = v.get
        elif a.kind == "list":
            v = tk.StringVar(value=", ".join(map(str, cur))); w = ttk.Entry(parent, textvariable=v, style="Modern.TEntry", width=14)
            getters[a.name] = lambda v=v: [int(x) for x in v.get().replace(",", " ").split()]
        elif a.kind == "map":
            box = {"v": dict(cur)}
            def edit(box=box, a=a, getters=getters):
                from .memory_editor import MemoryEditor
                try: ab, wd = int(getters["addr"]()), int(getters["width"]())
                except (KeyError, ValueError): return
                dlg = MemoryEditor(ctx, "Contents", box["v"], ab, wd); dlg.wait_window()
                if dlg.result is not None: box["v"] = dlg.result
            w = Btn(ctx, parent, "Edit contents…", edit, "secondary", pady=3); getters[a.name] = lambda box=box: dict(box["v"])
        elif a.kind == "str":
            v = tk.StringVar(value=str(cur)); w = ttk.Entry(parent, textvariable=v, style="Modern.TEntry", width=14); getters[a.name] = v.get
        else:
            v = tk.StringVar(value=str(cur)); w = ttk.Entry(parent, textvariable=v, style="Modern.TEntry", width=8)
            getters[a.name] = lambda v=v: int(v.get())
        w.grid(row=i, column=1, sticky="w", padx=(12, 0), pady=3)
    return getters


def PRJ_lookup(n):
    from ...core import project
    return project.lookup(n)


class _Modal(tk.Toplevel):
    def __init__(self, ctx, title, w=None):
        super().__init__(ctx.root); self.ctx = ctx; self.result = None
        self.title(title); self.configure(bg=ctx.P["card"]); self.transient(ctx.root)
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.update_idletasks(); r = self.ctx.root
        self.geometry(f"+{r.winfo_rootx() + max(0, (r.winfo_width() - self.winfo_width()) // 2)}+{r.winfo_rooty() + 60}")
        try: self.grab_set()
        except tk.TclError: pass


class PropsDialog(_Modal):
    """Edit the settings of one placed part. result = {name: value} or None."""
    def __init__(self, ctx, comp):
        super().__init__(ctx, f"{comp.type_name} properties")
        P = ctx.P
        tk.Label(self, text=f"{comp.type_name}  ({comp.id})", bg=P["card"], fg=P["text"], font=ctx.f_title).pack(anchor="w", padx=20, pady=(16, 2))
        tk.Label(self, text=comp.summary, bg=P["card"], fg=P["muted"], font=ctx.f_small, wraplength=360, justify="left").pack(anchor="w", padx=20)
        f = tk.Frame(self, bg=P["card"]); f.pack(fill="x", padx=20, pady=10)
        self.get = attr_form(ctx, f, type(comp), comp.attrs)
        self.err = tk.Label(self, text="", bg=P["card"], fg=P["bad"], font=ctx.f_small, wraplength=360, justify="left"); self.err.pack(anchor="w", padx=20)
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=20, pady=14)
        Btn(ctx, row, "Apply", lambda: self.ok(comp), "primary").pack(side="right", padx=(8, 0)); Btn(ctx, row, "Cancel", self.destroy, "secondary").pack(side="right")
        self.show()

    def ok(self, comp):
        try:
            vals = {k: g() for k, g in self.get.items()}
            for k, v in vals.items(): comp.spec(k).coerce(v)
        except Exception as e:
            self.err.config(text=str(e)); return
        self.result = vals; self.destroy()


class PaletteDialog(_Modal):
    """Pick a part (with settings) or a ready-made circuit. result = ("part", type, attrs) / ("preset", Circuit, replace: bool)."""
    def __init__(self, ctx):
        super().__init__(ctx, "Parts")
        P = ctx.P; self.cls = None; self.get = {}
        tk.Label(self, text="Add a part", bg=P["card"], fg=P["text"], font=ctx.f_title).pack(anchor="w", padx=20, pady=(16, 2))
        tk.Label(self, text="Folders follow Logisim's explorer. Greyed parts (tunnels, tri-state parts, TTL chips…) are not supported yet.", bg=P["card"], fg=P["muted"],
                 font=ctx.f_small, wraplength=520, justify="left").pack(anchor="w", padx=20)
        mid = tk.Frame(self, bg=P["card"]); mid.pack(fill="both", padx=20, pady=10)
        left = tk.Frame(mid, bg=P["card"]); left.pack(side="left", fill="y")
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", style="Modern.Treeview", height=16)
        self.tree.pack(side="left", fill="y"); self.tree.column("#0", width=210)
        self.items = {}
        self.tree.tag_configure("off", foreground=P["muted"])
        shown = set()
        for folder, entries in FOLDERS:
            top = self.tree.insert("", "end", text=folder, open=folder in ("Wiring", "Gates"))
            for label, tname in entries:
                cls = R.lookup(tname) if tname else None
                if cls is not None:
                    self.items[self.tree.insert(top, "end", text=label)] = ("part", cls); shown.add(cls.type_name)
                else:
                    self.items[self.tree.insert(top, "end", text=label, tags=("off",))] = ("todo", (folder, label))
        from ...core import project as PRJ
        top = self.tree.insert("", "end", text="This project's circuits", open=True)
        names = PRJ.placeable()
        for n in names: self.items[self.tree.insert(top, "end", text=n)] = ("sub", n)
        if not names: self.items[self.tree.insert(top, "end", text="(add a second circuit with + Circuit)", tags=("off",))] = ("todo", ("This project", "Add another circuit first (the + Circuit tab button), then it appears here."))
        rest = [c for c in R._classes.values() if c.type_name not in shown and not getattr(c, "hidden", False)]
        if rest:
            top = self.tree.insert("", "end", text="Other", open=True)
            for c in sorted({c.type_name: c for c in rest}.values(), key=lambda c: c.type_name):
                self.items[self.tree.insert(top, "end", text=c.type_name)] = ("part", c)
        top = self.tree.insert("", "end", text="Ready-made circuits", open=True)
        for p in PRESETS: self.items[self.tree.insert(top, "end", text=p.name)] = ("preset", p)
        self.tree.bind("<<TreeviewSelect>>", self.select); self.tree.bind("<Double-1>", lambda e: self.ok())
        self.right = tk.Frame(mid, bg=P["card"], width=300); self.right.pack(side="left", fill="both", expand=True, padx=(16, 0)); self.right.pack_propagate(False)
        self.err = tk.Label(self, text="", bg=P["card"], fg=P["bad"], font=ctx.f_small); self.err.pack(anchor="w", padx=20)
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=20, pady=14)
        self.b_add = Btn(ctx, row, "Add to circuit", self.ok, "primary"); self.b_add.pack(side="right", padx=(8, 0))
        self.b_new = Btn(ctx, row, "Start new circuit", lambda: self.ok(True), "secondary"); self.b_new.pack(side="right")
        Btn(ctx, row, "Cancel", self.destroy, "ghost").pack(side="left")
        self.b_add.set_enabled(False); self.b_new.set_enabled(False)
        self.show()

    def select(self, _e=None):
        sel = self.tree.selection(); P = self.ctx.P
        for w in self.right.winfo_children(): w.destroy()
        self.cur = self.items.get(sel[0]) if sel else None
        self.b_add.set_enabled(bool(self.cur) and self.cur[0] != "todo"); self.b_new.set_enabled(bool(self.cur) and self.cur[0] == "preset")
        if not self.cur: return
        kind, obj = self.cur
        if kind == "sub":
            c = PRJ_lookup(obj); ins = ", ".join(p.name for p in c.inputs) if c else "?"; outs = ", ".join(p.name for p in c.outputs) if c else "?"
            tk.Label(self.right, text=obj, bg=P["card"], fg=P["text"], font=self.ctx.f_title).pack(anchor="w")
            tk.Label(self.right, text=f"A circuit of this project used as a part.\nInputs: {ins or '-'}\nOutputs: {outs or '-'}", bg=P["card"], fg=P["muted"], font=self.ctx.f_small, wraplength=280, justify="left").pack(anchor="w", pady=(2, 10))
            return
        if kind == "todo":
            tk.Label(self.right, text=obj[1], bg=P["card"], fg=P["text"], font=self.ctx.f_title, wraplength=280, justify="left").pack(anchor="w")
            tk.Label(self.right, text=f"This is in Logisim's '{obj[0]}' folder, but VibeSimulation cannot simulate it yet, so it cannot be added.",
                     bg=P["card"], fg=P["muted"], font=self.ctx.f_small, wraplength=280, justify="left").pack(anchor="w", pady=(2, 10))
            return
        name = obj.type_name if kind == "part" else obj.name
        tk.Label(self.right, text=name, bg=P["card"], fg=P["text"], font=self.ctx.f_title).pack(anchor="w")
        tk.Label(self.right, text=obj.summary if kind == "part" else obj.description, bg=P["card"], fg=P["muted"], font=self.ctx.f_small,
                 wraplength=280, justify="left").pack(anchor="w", pady=(2, 10))
        f = tk.Frame(self.right, bg=P["card"]); f.pack(anchor="w")
        self.get = {}
        if kind == "part":
            self.get = attr_form(self.ctx, f, obj, {})
        elif obj.param_label:
            tk.Label(f, text=obj.param_label, bg=P["card"], fg=P["muted"], font=self.ctx.f_small).grid(row=0, column=0, sticky="w")
            v = tk.StringVar(value=next((l for l, x in obj.choices if x == obj.default), obj.choices[0][0]))
            ttk.Combobox(f, textvariable=v, values=[l for l, _ in obj.choices], state="readonly", style="Modern.TCombobox", width=24).grid(row=0, column=1, padx=(12, 0))
            self.get = {"_p": lambda: next(x for l, x in obj.choices if l == v.get())}

    def ok(self, replace=False):
        if not self.cur or self.cur[0] == "todo": return
        kind, obj = self.cur
        try:
            if kind == "sub": self.result = ("part", "Circuit", {"circuit": obj})
            elif kind == "part":
                attrs = {k: g() for k, g in self.get.items()}
                for k, v in attrs.items(): obj.attrs_spec[[a.name for a in obj.attrs_spec].index(k)].coerce(v)
                self.result = ("part", obj.type_name, attrs)
            else:
                val = self.get["_p"]() if self.get else None
                self.result = ("preset", obj.build(val), replace)
        except Exception as e:
            self.err.config(text=str(e)); return
        self.destroy()
