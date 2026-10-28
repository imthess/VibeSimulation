"""The Side Bar (VS Code's Explorer area) between the activity bar and the editor.

Logisim page:  Logisim's own explorer: the project's circuits and the library folders (Wiring, Gates, Plexers ...). Click a part to
               make it the tool, then click in the circuit to place it, like Logisim.
Multisim page: the component database: Group > Family > Component. Double-click a component to add it.
Other pages:   recent files."""
import os
import tkinter as tk
from tkinter import ttk

from ..components.registry import ComponentRegistry as R
from .logisim.parts_folders import FOLDERS
from .multisim.parts_bin import BIN, label as part_label
from .systemverilog.side_panel import SystemVerilogExplorer
from .vlsi.side_panel import VlsiExplorer

TITLES = {"settings": "SETTINGS", "logisim": "LOGISIM EXPLORER", "multisim": "COMPONENTS", "files": "EXPLORER", "vlsi": "VLSI EXPLORER", "systemverilog": "SYSTEMVERILOG EXPLORER"}


class SideBar(tk.Frame):
    MIN, MAX = 190, 520

    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell
        self.pack_propagate(False); self.configure(width=int(ctx.cfg.get("side_width", 262)))
        self.head = tk.Frame(self, bd=0); self.head.pack(fill="x")
        self.title = tk.Label(self.head, text="", font=ctx.f_small, anchor="w"); self.title.pack(side="left", padx=(18, 0), pady=(10, 8))
        self.body = tk.Frame(self, bd=0); self.body.pack(fill="both", expand=True)
        self.views, self.cur = {}, None
        self.sash = tk.Frame(master, width=4, cursor="sb_h_double_arrow", bd=0)
        self.sash.bind("<B1-Motion>", self._drag); self.sash.bind("<ButtonRelease-1>", lambda e: (ctx.cfg.__setitem__("side_width", int(self["width"])), ctx.save_cfg()))
        ctx.themed.append(self.paint); self.paint()

    def paint(self):
        P = self.ctx.P; st = self.ctx.style
        for w in (self, self.head, self.body): w.configure(bg=P["soft"])
        self.title.configure(bg=P["soft"], fg=P["muted"]); self.sash.configure(bg=P["border"])
        st.configure("Side.Treeview", background=P["soft"], fieldbackground=P["soft"], foreground=P["text"], rowheight=int(self.ctx.f_body.metrics("linespace") + 8), borderwidth=0, relief="flat", font=self.ctx.f_body)
        st.map("Side.Treeview", background=[("selected", P["accent"])], foreground=[("selected", P["accent_fg"])])
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
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.note.pack(fill="x", padx=16, pady=(4, 8))
        self.t.bind("<<TreeviewSelect>>", self._select); self.t.bind("<Double-1>", self._double); self.t.bind("<Button-3>", self._right)
        self.t.tag_configure("dim", foreground=ctx.P["muted"]); self.t.tag_configure("cur", font=ctx.f_bold)
        shell.doc.subscribe(self._doc); self.paint()

    def paint(self):
        P = self.ctx.P; self.configure(bg=P["soft"]); self.f.configure(bg=P["soft"]); self.bar.configure(bg=P["soft"]); self.note.configure(bg=P["soft"], fg=P["muted"])
        self.t.tag_configure("dim", foreground=P["muted"]); self.t.tag_configure("cur", font=self.ctx.f_bold)

    def _doc(self, kind):
        if kind in ("circuits", "changed") and self.winfo_ismapped(): self.refresh_circuits()

    def view(self): return self.sh.pages["logisim"].views["circuit"]

    def refresh(self):
        """Rebuild the whole tree (keeps which folders are open)."""
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
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True)
        self.note = tk.Label(self, text="Double-click a component to add it to the schematic.", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.note.pack(fill="x", padx=16, pady=(4, 8))
        self.t.bind("<Double-1>", self._double); self.t.bind("<Return>", self._double); self.t.bind("<<TreeviewSelect>>", self._select); self.paint()

    def paint(self):
        P = self.ctx.P; self.configure(bg=P["soft"]); self.f.configure(bg=P["soft"]); self.note.configure(bg=P["soft"], fg=P["muted"])

    def refresh(self):
        if self.t.get_children(""): return
        for g, fams in BIN:
            self.t.insert("", "end", "g:" + g, text="  " + g, open=g in ("Basic", "Sources"))
            for fam, classes in fams:
                fid = f"{g}:{fam}"; self.t.insert("g:" + g, "end", fid, text="  " + fam, open=False)
                for c in classes: self.t.insert(fid, "end", f"c:{c.type_name}", text="  " + part_label(c)); self.cls[f"c:{c.type_name}"] = c

    def _select(self, e):
        sel = self.t.selection()
        if sel and sel[0] in self.cls:
            c = self.cls[sel[0]]; self.note.configure(text=f"{part_label(c)}: {c.summary}" if getattr(c, "summary", "") else "Double-click to add it.")

    def _double(self, e):
        iid = self.t.identify_row(e.y) if hasattr(e, "y") and e.type == "4" else (self.t.selection() or [""])[0]
        if iid in self.cls: self.sh.pages["multisim"].views["schematic"].place(self.cls[iid]); return "break"
        if iid: self.t.item(iid, open=not self.t.item(iid, "open"))


class RecentFiles(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell
        self.f, self.t = _tree(ctx, self); self.f.pack(fill="both", expand=True); self.paths = {}
        self.t.bind("<Double-1>", self._open); self.t.bind("<Return>", self._open); self.paint()

    def paint(self): self.configure(bg=self.ctx.P["soft"]); self.f.configure(bg=self.ctx.P["soft"])

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
        P = self.ctx.P; self.configure(bg=P["soft"]); self.f.configure(bg=P["soft"])

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
