"""The Side Bar (VS Code's Explorer area) between the activity bar and the editor.

Logisim page:  Logisim's own explorer: the project's circuits and the library folders (Wiring, Gates, Plexers ...). Click a part to
               make it the tool, then click in the circuit to place it, like Logisim.
Multisim page: the component database: Group > Family > Component. Double-click a component to add it.
Other pages:   recent files."""
import os
import tkinter as tk
from tkinter import ttk

from ..components.registry import ComponentRegistry as R
from ..workspaces.logisim.circuit.parts_folders import FOLDERS
from ..workspaces.multisim.schematic.parts_bin import BIN, label as part_label
from ..workspaces.systemverilog.editor.side_panel import SystemVerilogExplorer
from ..workspaces.verilog.editor.side_panel import VlsiExplorer

TITLES = {"settings": "SETTINGS", "logisim": "LOGISIM EXPLORER", "multisim": "COMPONENTS", "files": "EXPLORER", "vlsi": "VLSI EXPLORER", "systemverilog": "SYSTEMVERILOG EXPLORER"}


class SideBar(tk.Frame):
    MIN, MAX = 190, 520

    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell
        self.pack_propagate(False); self.configure(width=int(ctx.cfg.get("side_width", 262)))
        self.head = tk.Frame(self, bd=0); self.head.pack(fill="x", padx=10, pady=(8, 0))
        self.title = tk.Label(self.head, text="", font=ctx.f_small, anchor="w"); self.title.pack(side="left", padx=(18, 0), pady=(10, 8))
        self.body = tk.Frame(self, bd=0); self.body.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        self.views, self.cur = {}, None
        self.sash = tk.Frame(master, width=4, cursor="sb_h_double_arrow", bd=0)
        ctx.glass.attach(self.sash); self.sash.bind("<B1-Motion>", self._drag); self.sash.bind("<ButtonRelease-1>", lambda e: (ctx.cfg.__setitem__("side_width", int(self["width"])), ctx.save_cfg()))
        ctx.glass.attach(self, ctx.r_card, "panel", (2, 2, 2, 3)); ctx.themed.append(self.paint); self.paint()

    def paint(self):
        P = self.ctx.P; st = self.ctx.style; self.ctx.glass.attach(self, self.ctx.r_card, "panel", (2, 2, 2, 3))
        for w in (self, self.head, self.body): w.configure(bg=P["card"])
        self.title.configure(bg=P["card"], fg=P["muted"])
        st.configure("Side.Treeview", background=P["card"], fieldbackground=P["card"], foreground=P["text"], rowheight=int(self.ctx.f_body.metrics("linespace") + 8), borderwidth=0, relief="flat", font=self.ctx.f_body)
        st.map("Side.Treeview", background=[("selected", P["sel"])], foreground=[("selected", P["text"])])
        st.layout("Side.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        for v in self.views.values():
            if hasattr(v, "paint"): v.paint()

    def _drag(self, e):
        w = max(self.MIN, min(self.MAX, e.x_root - self.winfo_rootx())); self.configure(width=w)

    def kind_for(self, page): return {"logisim": "logisim", "multisim": "multisim", "vlsi": "vlsi", "systemverilog": "systemverilog", "home": "files", "import": "files", "settings": "settings"}.get(page)

    def show_for(self, page):
        k = self.kind_for(page)
        if k is None: return False
        if k not in self.views:
            self.views[k] = {"logisim": LogisimExplorer, "multisim": ComponentBin, "vlsi": VlsiExplorer, "systemverilog": SystemVerilogExplorer, "files": RecentFiles, "settings": SettingsNav}[k](self.ctx, self.body, self.sh)
        if self.cur and self.cur != k: self.views[self.cur].pack_forget()
        self.cur = k; self.title.configure(text=TITLES[k]); self.views[k].pack(fill="both", expand=True); self.views[k].refresh()
        return True

    def view(self): return self.views.get(self.cur)


def _tree(ctx, parent):
    f = tk.Frame(parent, bd=0); t = ttk.Treeview(f, show="tree", selectmode="browse", style="Side.Treeview")
    sb = ttk.Scrollbar(f, orient="vertical", command=t.yview, style="Thin.Vertical.TScrollbar"); t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); t.pack(side="left", fill="both", expand=True, padx=(6, 0)); return f, t


class LogisimExplorer(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell; self._lock = False
        from .widgets import Btn
        self.bar = tk.Frame(self, bd=0); self.bar.pack(fill="x", padx=10, pady=(0, 6))          # Logisim's explorer toolbar
        self.b_edit = Btn(ctx, self.bar, "↖  Edit tool", lambda: self.view().set_tool(None), "secondary", pady=3, padx=9).tip("Edit tool: select, move and wire (Esc)"); self.b_edit.pack(side="left", padx=(0, 4))
        Btn(ctx, self.bar, "+ Circuit", lambda: self.view().new_circuit(), "secondary", pady=3, padx=9).tip("Add another circuit to this project").pack(side="left")
        from .props_panel import PropsPanel
        self.props = PropsPanel(ctx, self); self.props.pack(side="bottom", fill="x"); self._hooked = False
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.note.pack(side="bottom", fill="x", padx=16, pady=(4, 8))
        self.t.bind("<<TreeviewSelect>>", self._select); self.t.bind("<Double-1>", self._double); self.t.bind("<Button-3>", self._right)
        self.t.tag_configure("dim", foreground=ctx.P["muted"]); self.t.tag_configure("cur", font=ctx.f_bold)
        shell.doc.subscribe(self._doc); self.paint()
        from .palette_drag import PaletteDrag
        self.drag = PaletteDrag(ctx, self.t, self._can_drag, lambda: self.view().canvas if self.sh.current == "logisim" else None, self._drop, self._hover)

    def _can_drag(self, iid):
        """Parts, input / output pins and other circuits of the project can be dragged out; folders and the greyed-out parts cannot."""
        if iid.startswith("p:"): return iid.split(":", 2)[2]
        if iid.startswith("c:") and iid[2:] != self.sh.doc.cur and iid[2:] in __import__("vibesimulation.core.project", fromlist=["x"]).placeable(): return iid[2:]
        return None

    def _drop(self, iid, x, y):
        cv = self.view(); self._select(None) if cv.tool is None else None
        if cv.tool is None: return
        class _E: pass
        e = _E(); e.x, e.y, e.state = x, y, 0
        cv.place(e)

    def _hover(self, x, y):
        cv = self.view(); cv.canvas.delete("tip")
        if x is None or cv.tool is None: return
        class _E: pass
        e = _E(); e.x, e.y = x, y; cv.tool_ghost(e)

    def paint(self):
        P = self.ctx.P; self.configure(bg=P["card"]); self.f.configure(bg=P["card"]); self.bar.configure(bg=P["card"]); self.note.configure(bg=P["card"], fg=P["muted"])
        self.t.tag_configure("dim", foreground=P["muted"]); self.t.tag_configure("cur", font=self.ctx.f_bold); self.props.paint()

    def _hook(self):
        if self._hooked: return
        self._hooked = True; cv = self.view(); cv.draw_hooks = getattr(cv, "draw_hooks", []); cv.draw_hooks.append(self.show_props)

    def show_props(self):
        if self.winfo_ismapped(): logisim_props(self.props, self.view())

    def _doc(self, kind):
        if kind in ("circuits", "changed") and self.winfo_ismapped(): self.refresh_circuits()

    def view(self): return self.sh.pages["logisim"].views["circuit"]

    def refresh(self):
        """Rebuild the whole tree (keeps which folders are open)."""
        self._hook(); self.after_idle(self.show_props)
        openf = {i for i in self.t.get_children("") if self.t.item(i, "open")} if self.t.get_children("") else {"proj"}
        self._lock = True; self.t.delete(*self.t.get_children(""))
        d = self.sh.doc
        self.t.insert("", "end", "proj", text="  Project", open=("proj" in openf))
        self.refresh_circuits(build=False)
        used = set()
        for fname, parts in FOLDERS:
            iid = "f:" + fname; self.t.insert("", "end", iid, text="  " + fname, open=iid in openf)
            items = list(parts)
            if fname == "Wiring": items = [("Input Pin", "@in"), ("Output Pin", "@out")] + [x for x in items if x[0] != "Pin"]
            for lab, tn in items:
                if tn and not tn.startswith("@"): used.add(tn)
                self.t.insert(iid, "end", f"p:{tn}:{lab}" if tn else f"x:{fname}:{lab}", text="  " + lab, tags=() if tn else ("dim",))
        extra = [c for c in R.by_category().values() for c in c if c.type_name not in used and not getattr(c, "is_sub", False) and c.type_name != "Circuit"]
        if extra:
            self.t.insert("", "end", "f:Other", text="  Other", open="f:Other" in openf)
            for c in sorted(extra, key=lambda c: c.type_name): self.t.insert("f:Other", "end", f"p:{c.type_name}:{c.type_name}", text="  " + c.type_name)
        self._lock = False; self.sync_tool()

    def refresh_circuits(self, build=True):
        d = self.sh.doc; self._lock = True
        if not self.t.exists("proj"): self._lock = False; return
        for k in self.t.get_children("proj"): self.t.delete(k)
        for n in d.circuit_names(): self.t.insert("proj", "end", "c:" + n, text="  ▣  " + n, tags=("cur",) if n == d.cur else ())
        self._lock = False

    def sync_tool(self):
        """Highlight the tool the circuit view has (or nothing for the Edit tool)."""
        self._lock = True
        try:
            tool = self.view().tool
            k = "primary" if tool is None else "secondary"
            if self.b_edit.kind != k: self.b_edit.kind = k; self.b_edit.paint()
            if tool is None:
                if self.t.selection(): self.t.selection_set(())
            else:
                key = "p:" + tool[1] if tool[0] == "part" else {"in": "p:@in:Input Pin", "out": "p:@out:Output Pin"}.get(tool[0])
                hit = next((i for i in self._all() if i.startswith(key or "?")), None) if key else None
                if hit and tuple(self.t.selection()) != (hit,): self.t.selection_set((hit,)); self.t.see(hit)
        finally: self.after_idle(self._unlock)

    def _unlock(self): self._lock = False

    def _all(self):
        out = []
        for i in self.t.get_children(""): out.append(i); out += list(self.t.get_children(i))
        return out

    def _select(self, e):
        if self._lock: return
        sel = self.t.selection()
        if not sel: return
        iid = sel[0]; cv = self.view(); self.sh.show("logisim") if self.sh.current != "logisim" else None
        if iid.startswith("p:"):
            _, tn, lab = iid.split(":", 2)
            if tn == "@in": cv.set_tool(("in",), lab)
            elif tn == "@out": cv.set_tool(("out",), lab)
            else: cv.set_tool(("part", tn), lab)
        elif iid.startswith("x:"): self.note.configure(text=f"{iid.split(':', 2)[2]}: Logisim has this part, VibeSimulation cannot simulate it yet."); self.sync_tool()
        elif iid.startswith("c:"):
            n = iid[2:]
            if n != self.sh.doc.cur and n in __import__("vibesimulation.core.project", fromlist=["x"]).placeable(): cv.set_tool(("circuit", n), n)
            else: cv.set_tool(None)
        else: cv.set_tool(None)

    def _double(self, e):
        iid = self.t.identify_row(e.y)
        if iid.startswith("c:"): self.sh.doc.switch(iid[2:]); self.view().set_tool(None); return "break"

    def _right(self, e):
        iid = self.t.identify_row(e.y); m = self.ctx.menu(); cv = self.view()
        if iid.startswith("c:"):
            n = iid[2:]
            m.add_command(label="Edit this circuit", command=lambda: self.sh.doc.switch(n)); m.add_command(label="Rename…", command=lambda: cv.rename_circuit(n))
            m.add_command(label="Delete circuit", command=lambda: cv.delete_circuit(n)); m.add_separator()
        m.add_command(label="Add circuit…", command=cv.new_circuit)
        m.tk_popup(e.x_root, e.y_root)


class ComponentBin(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell; self.cls = {}
        from .props_panel import PropsPanel
        self.props = PropsPanel(ctx, self); self.props.pack(side="bottom", fill="x"); self._hooked = False
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        self.note = tk.Label(self, text="Drag a component onto the schematic to add it.", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.note.pack(side="bottom", fill="x", padx=16, pady=(4, 8))
        self.t.bind("<Double-1>", self._double); self.t.bind("<Return>", self._double); self.t.bind("<<TreeviewSelect>>", self._select); self.paint()
        from .palette_drag import PaletteDrag
        sv = lambda: self.sh.pages["multisim"].views["schematic"]
        self.drag = PaletteDrag(ctx, self.t, lambda iid: part_label(self.cls[iid]) if iid in self.cls else None, lambda: sv().canvas if self.sh.current == "multisim" else None,
                                lambda iid, x, y: sv().place_at(self.cls[iid], x, y),
                                lambda x, y: sv().ghost_part(self.cls.get(self.drag.iid), x, y))

    def paint(self):
        P = self.ctx.P; self.configure(bg=P["card"]); self.f.configure(bg=P["card"]); self.note.configure(bg=P["card"], fg=P["muted"]); self.props.paint()

    def show_props(self):
        if self.winfo_ismapped(): multisim_props(self.props, self.sh.pages["multisim"].views["schematic"])

    def refresh(self):
        if not self._hooked:
            self._hooked = True; sv = self.sh.pages["multisim"].views["schematic"]; sv.draw_hooks = getattr(sv, "draw_hooks", []); sv.draw_hooks.append(self.show_props)
        self.after_idle(self.show_props)
        if self.t.get_children(""): return
        for g, fams in BIN:
            self.t.insert("", "end", "g:" + g, text="  " + g, open=g in ("Basic", "Sources"))
            for fam, classes in fams:
                fid = f"{g}:{fam}"; self.t.insert("g:" + g, "end", fid, text="  " + (fam.replace("_", " ").capitalize() if fam.isupper() else fam), open=False)
                for c in classes: self.t.insert(fid, "end", f"c:{c.type_name}", text="  " + part_label(c)); self.cls[f"c:{c.type_name}"] = c

    def _select(self, e):
        sel = self.t.selection()
        if sel and sel[0] in self.cls:
            c = self.cls[sel[0]]; self.note.configure(text=f"{part_label(c)}: {c.summary}" if getattr(c, "summary", "") else "Drag it onto the schematic.")

    def _double(self, e):
        iid = self.t.identify_row(e.y) if hasattr(e, "y") and e.type == "4" else (self.t.selection() or [""])[0]
        if iid in self.cls: return "break"                       # a part is added by dragging it onto the schematic, not by double-clicking
        if iid: self.t.item(iid, open=not self.t.item(iid, "open"))


class RecentFiles(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True); self.paths = {}
        self.t.bind("<Double-1>", self._open); self.t.bind("<Return>", self._open); self.paint()

    def paint(self): self.configure(bg=self.ctx.P["card"]); self.f.configure(bg=self.ctx.P["card"])

    def refresh(self):
        self.t.delete(*self.t.get_children("")); self.paths = {}
        self.t.insert("", "end", "rec", text="  Recent circuits (JSON)", open=True)
        for p, *_ in self.ctx.cfg.get("recent", [])[:15]:
            if os.path.isfile(p):
                iid = self.t.insert("rec", "end", text="  " + os.path.basename(p)); self.paths[iid] = p
        if not self.paths: self.t.insert("rec", "end", text="  (nothing opened yet)")
        self.t.insert("", "end", "act", text="  Start", open=True)
        for lab, key in (("New blank circuit", "new"), ("Open circuit JSON…", "open"), ("Open image (AI import)…", "img")):
            self.paths[self.t.insert("act", "end", text="  " + lab)] = "@" + key

    def _open(self, e):
        iid = self.t.identify_row(e.y) if e.type == "4" else (self.t.selection() or [""])[0]; p = self.paths.get(iid)
        if not p: return
        s = self.sh; page = "multisim" if s.analog() else "logisim"
        if p == "@new": s.cur_actions.new(); s.show(page)
        elif p == "@open": s.cur_actions.json_open() and s.show(page)
        elif p == "@img": s.open_image()
        else: s.cur_actions.json_open(p) and s.show(page)


class SettingsNav(tk.Frame):
    """The settings categories (VS Code's list on the left of its Settings editor). Click one to show it on the Settings page."""
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell; self._lock = False
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        from .settings.page import CATS
        for c in CATS: self.t.insert("", "end", c, text="  " + c)
        self.t.bind("<<TreeviewSelect>>", self._select); self.paint()

    def paint(self):
        P = self.ctx.P; self.configure(bg=P["card"]); self.f.configure(bg=P["card"])

    def refresh(self): self.show_cat(self.sh.pages["settings"].cur, bool(self.sh.pages["settings"].q.get().strip()))

    def show_cat(self, cat, searching=False):
        self._lock = True
        try:
            if searching: self.t.selection_set(())
            elif tuple(self.t.selection()) != (cat,): self.t.selection_set((cat,))
        finally: self.after_idle(self._unlock)

    def _unlock(self): self._lock = False

    def _select(self, e):
        if self._lock: return
        sel = self.t.selection()
        if sel: self.sh.pages["settings"].pick(sel[0])


# ------------------------------------------------------------------------------------------------- properties panel contents
def logisim_props(panel, cv):
    """Fill the panel from what the Logisim circuit view has selected."""
    from .props_panel import Field
    from ..core import commands as C
    d = cv.doc
    if not d.valid or d.circuit is None:
        return panel.show("Properties", "", [], ("none",))
    c = d.circuit; run = cv.run
    comps = {x.id: x for x in c.components}
    psel = sorted(getattr(cv, "psel", ()) or ())
    if cv.sel and cv.sel in comps and len(cv.sels) <= 1 and not psel:
        comp = comps[cv.sel]; fl = [Field("Name", "ro", comp.id), Field("Type", "ro", comp.type_name), Field("Facing", "ro", comp.facing)]
        for a in comp.attrs_spec:
            cur = comp.attrs.get(a.name, a.default); lab = a.label or a.name
            if a.kind == "choice":
                fl.append(Field(lab, "choice", cur, lambda v, a=a, cid=comp.id: run(C.SetAttrs(cid, {a.name: next((x for x in a.choices if str(x) == v), v)})), [str(x) for x in a.choices]))
            elif a.kind == "bool": fl.append(Field(lab, "bool", cur, lambda v, a=a, cid=comp.id: run(C.SetAttrs(cid, {a.name: bool(v)}))))
            elif a.kind in ("int", "number"): fl.append(Field(lab, "int", cur, lambda v, a=a, cid=comp.id: run(C.SetAttrs(cid, {a.name: v}))))
            elif a.kind == "str": fl.append(Field(lab, "str", cur, lambda v, a=a, cid=comp.id: run(C.SetAttrs(cid, {a.name: v}))))
            else: fl.append(Field(lab, "ro", "(right-click → Properties…)"))
        return panel.show(comp.type_name, comp.summary or "", fl, ("c", comp.id, tuple(sorted((k, str(v)) for k, v in comp.attrs.items())), comp.facing))
    if len(psel) == 1 and not cv.sels:
        kind, name = psel[0]
        if kind == "in":
            p = next((q for q in c.inputs if q.name == name), None)
            if p is not None:
                return panel.show("Input pin", "Click it with the hand tool to change its value.", [
                    Field("Label", "str", p.name, lambda v, n=p.name: run(C.RenameSignal(n, v.strip())) if v.strip() else None),
                    Field("Width (bits)", "int", p.width, lambda v, n=p.name: run(C.SetInputWidth(n, v)))], ("in", p.name, p.width))
        else:
            return panel.show("Output pin", "Draw a wire to it to show a signal.", [Field("Label", "ro", name)], ("out", name))
    n = len(cv.sels) + len(psel) + len(getattr(cv, "wsel", ()) or ())
    if n > 1: return panel.show("Selection", f"{len(cv.sels)} part(s), {len(psel)} pin(s), {len(cv.wsel)} wire piece(s) selected.", [], ("multi", n))
    return panel.show("Circuit: " + d.cur, "Select a part, an input or an output to see its properties.", [
        Field("Inputs", "ro", len(c.inputs)), Field("Outputs", "ro", len(c.outputs)), Field("Parts", "ro", len(c.components))], ("circ", d.cur, len(c.inputs), len(c.outputs), len(c.components)))


def multisim_props(panel, sv):
    from .props_panel import Field
    from ..workspaces.multisim.engine import components as AC
    from ..workspaces.multisim.engine.units import parse_value
    d = sv.doc; nl = d.netlist
    if nl is None or d.errors or not nl.parts: return panel.show("Properties", "", [], ("none",))
    p = nl.part(sv.sel) if sv.sel else None
    if p is None:
        return panel.show("Circuit", "Click a part to see its properties.", [Field("Parts", "ro", len(nl.parts))], ("circ", len(nl.parts)))
    pid = p.id
    def rename(v):
        v = v.strip()
        if not v or v == pid: return
        if nl.part(v) is not None: raise ValueError(f"There is already a part called {v}.")
        sv.edit(lambda n: setattr(n.part(pid), "id", v)); sv.select_part(v)
    def setval(v):
        parse_value(v); sv.edit(lambda n: setattr(n.part(pid), "value", v.strip()))
    def setextra(k, v):
        if k != "control": parse_value(v) if k not in ("wave",) else None
        cur = p.extra.get(k)
        val = [x.strip() for x in v.split(",") if x.strip()] if isinstance(cur, list) else v.strip()
        sv.edit(lambda n: n.part(pid).extra.__setitem__(k, val))
    fl = [Field("Label", "str", pid, rename), Field("Type", "ro", p.type_name)]
    if p.default is not None: fl.append(Field(f"Value ({p.unit})" if p.unit else "Value", "str", p.value, setval))
    for k in p.extras:
        cur = p.extra.get(k)
        if k == "wave": fl.append(Field("Waveform", "choice", cur, lambda v, k=k: setextra(k, v), list(AC.Waveform.WAVES)))
        else: fl.append(Field(k, "str", ", ".join(map(str, cur)) if isinstance(cur, list) else cur, lambda v, k=k: setextra(k, v)))
    term = p.terminals or ()
    fl.append(Field("Connects to", "ro", ", ".join((f"{t}={n}" if t else str(n)) for t, n in zip(term or [""] * len(p.nodes), p.nodes))))
    return panel.show(p.type_name, p.summary or "", fl, ("p", pid, str(p.value), tuple(sorted((k, str(v)) for k, v in p.extra.items())), tuple(map(str, p.nodes))))
