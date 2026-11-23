"""The IC view window: your circuit rebuilt from real 74xx chips, wired automatically.

Tabs
- Summary: how many chips, the parts list, notes, and the test "chips give the same answers as the gates".
- Gate view: your circuit as gates (what the Logisim tab shows), live, so the three views can be compared.
- IC view: the chips placed and wired like a circuit you would build in Logisim from its TTL library; inputs and outputs show live
  values, click an input to flip it.  Pressing play in the truth table runs the gates and the chips side by side.
- X-ray: the same circuit, with every chip opened up so the gates inside it, and which pin each one uses, are drawn.  Click a pin to follow its signal, double-click to rewire it.  The rewiring
  only changes the chip version - never the circuit or its JSON - and the test shows whether the chips still match the gates.
- Chips / Wiring / IC library: pin diagrams, the wire list, all chips of Logisim's TTL library.

The window belongs to the Logisim tab: it hides while Multisim or another workspace is shown.
"""
import io
import tkinter as tk
from tkinter import ttk

from vibesimulation.ui.controls.canvas_renderer import TkRenderer
from vibesimulation.ui.controls.widgets import Btn, Segmented
from vibesimulation.ui.look.theme import auto
from vibesimulation.workspaces.logisim.ic import breadboard as B
from vibesimulation.workspaces.logisim.ic import edit as E
from vibesimulation.workspaces.logisim.ic import catalog as K
from vibesimulation.workspaces.logisim.ic import report, schematic as S, verify, xray as X
from vibesimulation.workspaces.logisim.layout.painter import CircuitPainter, extent as gate_extent
from vibesimulation.workspaces.logisim.ic.mapper import GND, TIES, VCC
from vibesimulation.workspaces.logisim.ic.session import NONE, session_for

TABS = (("Summary", "sum"), ("Gate view", "gate"), ("IC view", "ic"), ("X-ray", "xray"), ("Chips", "chips"), ("Wiring", "wires"), ("IC library", "lib"))
MAX_AUTO_TEST_UNITS = 70                  # bigger circuits are only tested when you press the button


def open_ic_view(ctx, doc, page=None):
    """Open the window (or bring the open one to the front).  ``page`` is the Logisim page that owns it."""
    w = getattr(page, "_ic_window", None) if page is not None else None
    try:
        if w is not None and w.winfo_exists(): w.deiconify(); w.lift(); w.refresh(); return w
    except tk.TclError: pass
    w = ICWindow(ctx, doc)
    if page is not None: page._ic_window = w
    return w


class Zoom:
    """A canvas you can zoom (wheel, +/-) and drag; ``draw(renderer)`` paints it, ``extent()`` gives its size in layout units."""
    def __init__(self, ctx, parent, extent, draw, on_click=None, on_double=None, on_right=None, on_hover=None, on_move=None):
        self.ctx, self.extent, self.draw, self.on_move = ctx, extent, draw, on_move
        self.on_click, self.on_double, self.on_right, self.on_hover = on_click, on_double, on_right, on_hover
        self.c = c = tk.Canvas(parent, highlightthickness=0, bd=0)
        self.view = None; self._p = None
        c.bind("<Configure>", lambda e: self.redraw())
        c.bind("<Button-1>", self.press); c.bind("<B1-Motion>", self.drag); c.bind("<ButtonRelease-1>", self.release)
        c.bind("<Double-Button-1>", self.double); c.bind("<Button-3>", self.right); c.bind("<Motion>", self.motion)
        c.bind("<MouseWheel>", lambda e: self.zoom_at(e.x, e.y, 1.15 if e.delta > 0 else 1 / 1.15))
        c.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, 1.15)); c.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, 1 / 1.15))

    def tags_at(self, x, y):
        out = []
        for item in reversed(self.c.find_overlapping(x - 3, y - 3, x + 3, y + 3)): out += list(self.c.gettags(item))
        return out

    def scale(self):
        if self.view is None:
            W, H = max(self.c.winfo_width(), 200), max(self.c.winfo_height(), 200)
            x0, y0, x1, y1 = self.extent(); w, h = max(x1 - x0, 1), max(y1 - y0, 1)
            s = min((W - 20) / w, (H - 20) / h, 2.2)
            self.view = [s, (W - w * s) / 2 - x0 * s, max(10, (H - h * s) / 2) - y0 * s]
        return self.view

    def redraw(self):
        self.c.delete("all")
        try: s, ox, oy = self.scale()
        except Exception: return                                     # noqa: BLE001 - nothing to draw yet
        self.draw(TkRenderer(self.c, self.ctx.P, self.ctx.sans, s, ox, oy))

    def fit(self): self.view = None; self.redraw()

    def zoom_at(self, x, y, f):
        s, ox, oy = self.scale(); ns = max(0.15, min(8.0, s * f)); f = ns / s
        self.view = [ns, x - (x - ox) * f, y - (y - oy) * f]; self.redraw()

    def zoom_by(self, f): self.zoom_at(self.c.winfo_width() / 2, self.c.winfo_height() / 2, f)

    def press(self, e):
        tags = self.tags_at(e.x, e.y)
        ref = None
        if self.on_move and not any(t.startswith(("pin:", "net:")) for t in tags):
            ref = next((t.split(":", 1)[1] for t in tags if t.startswith(("node:", "ext:"))), None)
        self._p = [e.x, e.y, False, ref, e.x, e.y]

    def drag(self, e):
        if not self._p: return
        if not self._p[2] and abs(e.x - self._p[0]) + abs(e.y - self._p[1]) < 5: return
        if len(self._p) > 3 and self._p[3]:                          # a chip or a terminal: it follows the mouse
            self.scale(); self._p[2] = True
            self.on_move(self._p[3], (e.x - self._p[4]) / self.view[0], (e.y - self._p[5]) / self.view[0]); return
        self.scale(); self._p[2] = True
        self.view[1] += e.x - self._p[0]; self.view[2] += e.y - self._p[1]; self._p[0], self._p[1] = e.x, e.y; self.redraw()

    def release(self, e):
        p, self._p = self._p, None
        if p and p[2] and len(p) > 3 and p[3] and self.on_move: self.on_move(p[3], None, None)
        if p and not p[2] and self.on_click: self.on_click(e, self.tags_at(e.x, e.y))

    def double(self, e):
        if self.on_double: self.on_double(e, self.tags_at(e.x, e.y))

    def right(self, e):
        if self.on_right: self.on_right(e, self.tags_at(e.x, e.y))

    def motion(self, e):
        if self.on_hover and not self._p: self.on_hover(e, self.tags_at(e.x, e.y))


class NetPicker(tk.Toplevel):
    """Choose what a pin is connected to: a signal, GND, +5 V or nothing."""
    def __init__(self, win, info, current, options, on_pick, on_reset=None):
        ctx = win.ctx; P = ctx.P
        super().__init__(win)
        self.title("Rewire pin"); self.transient(win); self.geometry("420x480"); self.configure(bg=P["card"])
        self.on_pick = on_pick
        tk.Label(self, text=info, font=ctx.f_bold, bg=P["card"], fg=P["text"], anchor="w", justify="left", wraplength=390).pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(self, text=f"Now connected to: {current}", font=ctx.f_small, bg=P["card"], fg=P["muted"], anchor="w").pack(fill="x", padx=14)
        self.q = tk.StringVar(); self.q.trace_add("write", lambda *a: self.fill())
        tk.Entry(self, textvariable=self.q, bg=P["field"], fg=P["text"], insertbackground=P["text"], relief="flat", font=ctx.f_body).pack(fill="x", padx=14, pady=8, ipady=4)
        self.options = options
        self.tree = ttk.Treeview(self, columns=("net", "note"), show="headings", selectmode="browse", style="Modern.Treeview", height=12)
        self.tree.heading("net", text="Connect to"); self.tree.heading("note", text="")
        self.tree.column("net", width=230, anchor="w"); self.tree.column("note", width=120, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=14)
        self.tree.bind("<Double-Button-1>", lambda e: self.ok())
        bar = tk.Frame(self, bg=P["card"]); bar.pack(fill="x", padx=14, pady=10)
        Btn(ctx, bar, "Connect", self.ok, "primary", pady=4).pack(side="right")
        Btn(ctx, bar, "Cancel", self.destroy, "secondary", pady=4).pack(side="right", padx=6)
        if on_reset: Btn(ctx, bar, "Undo my change", lambda: (on_reset(), self.destroy()), "ghost", pady=4).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy()); self.bind("<Return>", lambda e: self.ok())
        self.fill()

    def fill(self):
        q = self.q.get().lower().strip()
        self.tree.delete(*self.tree.get_children())
        for i, (label, value, note) in enumerate(self.options):
            if q and q not in label.lower(): continue
            self.tree.insert("", "end", iid=str(i), values=(label, note))
        kids = self.tree.get_children()
        if kids: self.tree.selection_set(kids[0])

    def ok(self):
        s = self.tree.selection()
        if not s: return
        self.on_pick(self.options[int(s[0])][1]); self.destroy()


class ICWindow(tk.Toplevel):
    def __init__(self, ctx, doc):
        super().__init__(ctx.root)
        self.ctx, self.doc = ctx, doc
        self.sess = session_for(doc, ctx.cfg)
        self.plan = self.board = self.sch = self.xsch = None
        self.pos_ic, self.pos_x = {}, {}                      # chips and terminals dragged by the user: ref -> (x, y); a view setting, the circuit is untouched
        self._grab = None
        self.sel_net = None; self.x_sel = None; self.x_hot = None
        self.ic_sel = None
        self.cur = "sum"; self._job = self._test_job = None; self.hints = []
        self.title("IC view - the circuit as real 74xx chips")
        self.geometry("1240x800"); self.minsize(820, 520)
        P = ctx.P
        self.configure(bg=P["card"])
        self.columnconfigure(0, weight=1); self.rowconfigure(1, weight=1)

        bar = tk.Frame(self, bd=0); bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6)); self.bar = bar
        self.tabs = Segmented(ctx, bar, TABS, "sum", self.show); self.tabs.pack(side="left")
        Btn(ctx, bar, "Export…", self.export_menu, "secondary", pady=4).tip("Save the build guide, pictures and lists").pack(side="right")

        self.holder = tk.Frame(self, bd=0); self.holder.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.holder.columnconfigure(0, weight=1); self.holder.rowconfigure(0, weight=1)
        self.pages = {k: tk.Frame(self.holder, bd=0) for _, k in TABS}
        for f in self.pages.values(): f.grid(row=0, column=0, sticky="nsew")
        self.build_summary(self.pages["sum"]); self.build_gate(self.pages["gate"]); self.build_ic(self.pages["ic"]); self.build_xray(self.pages["xray"])
        self.build_chips(self.pages["chips"]); self.build_wires(self.pages["wires"]); self.build_library(self.pages["lib"])

        ctx.themed.append(self._paint)
        self.sess.listeners.append(self.on_sess)
        self.bind("<Destroy>", self._gone)
        self.bind("<Escape>", lambda e: self.destroy())
        self.show("sum"); self._paint(); self.refresh()

    # ---------------------------------------------------------------- housekeeping
    def _gone(self, e):
        if e.widget is self:
            if self.on_sess in self.sess.listeners: self.sess.listeners.remove(self.on_sess)
            for j in (self._job, self._test_job):
                if j:
                    try: self.after_cancel(j)
                    except (tk.TclError, ValueError): pass

    def _paint(self):
        P = self.ctx.P
        try:
            self.configure(bg=P["card"]); self.bar.configure(bg=P["card"]); self.holder.configure(bg=P["card"])
            for f in self.pages.values(): f.configure(bg=P["card"])
            for w in (self.headline, self.test_lbl, self.low): w.configure(bg=P["card"])
            self.headline.configure(fg=P["text"])
            self.notes.configure(bg=P["field"], fg=P["text"], insertbackground=P["text"])
            for z in (self.gate_zoom, self.ic_zoom, self.x_zoom): z.c.configure(bg=P["canvas"])
            self.chip_canvas.configure(bg=P["canvas"])
            for b in (self.gate_bar, self.ic_bar, self.x_bar): b.configure(bg=P["card"])
            for lab in (self.gate_status, self.ic_status, self.x_status): lab.configure(bg=P["soft_h"], fg=P["text"])
            for lab in self.hints: lab.configure(bg=P["card"], fg=P["muted"])
            self.lib_text.configure(bg=P["field"], fg=P["text"], insertbackground=P["text"])
            for t in (self.bom, self.wire_tree, self.lib_tree): t.tag_configure("odd", background=P["field"])
            if self.plan is not None: self.draw_all()
        except tk.TclError: pass

    def show(self, key):
        self.pages[key].tkraise(); self.tabs.set(key); self.cur = key
        if self.plan is not None: self.after_idle(self.draw_all)

    # ---------------------------------------------------------------- the pages
    def build_summary(self, f):
        ctx = self.ctx; f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1)
        self.headline = tk.Label(f, text="", font=ctx.f_bold, anchor="w", justify="left", wraplength=1100)
        self.headline.grid(row=0, column=0, sticky="ew", pady=(2, 8))
        box = tk.Frame(f, bd=0); box.grid(row=1, column=0, sticky="nsew"); box.columnconfigure(0, weight=1); box.rowconfigure(0, weight=1)
        self.bom = ttk.Treeview(box, columns=("qty", "item", "note"), show="headings", selectmode="none", style="Modern.Treeview")
        for c, t, w, st in (("qty", "Qty", 56, False), ("item", "Logisim part", 230, False), ("note", "In the IC version", 640, True)):
            self.bom.heading(c, text=t); self.bom.column(c, width=w, minwidth=40, stretch=st, anchor="center" if c == "qty" else "w")
        sy = ttk.Scrollbar(box, command=self.bom.yview, style="Thin.Vertical.TScrollbar"); self.bom.configure(yscrollcommand=auto(sy))
        self.bom.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns")
        low = tk.Frame(f, bd=0); low.grid(row=2, column=0, sticky="ew", pady=(8, 0)); low.columnconfigure(0, weight=1); self.low = low
        self.test_lbl = tk.Label(low, text="", font=ctx.f_small, anchor="w", justify="left", wraplength=980)
        self.test_lbl.grid(row=0, column=0, sticky="w")
        Btn(ctx, low, "Test the chips", self.run_test, "secondary", pady=3).tip("Simulate the chip version and compare it with your circuit").grid(row=0, column=1, sticky="e")
        self.notes = tk.Text(low, height=6, wrap="word", bd=0, relief="flat", font=ctx.f_small, padx=8, pady=6, state="disabled")
        self.notes.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _bar(self, f, buttons, hint):
        ctx = self.ctx
        bar = tk.Frame(f, bd=0); bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for txt, fn, tip in buttons: Btn(ctx, bar, txt, fn, "ghost", padx=9, pady=4).tip(tip).pack(side="left", padx=(0, 2))
        lab = tk.Label(bar, text=hint, font=ctx.f_small); lab.pack(side="left", padx=12); self.hints.append(lab)
        return bar

    def build_gate(self, f):
        f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1)
        self.gate_zoom = None
        self.gate_bar = self._bar(f, (("Fit", lambda: self.gate_zoom.fit(), "Show everything"), ("+", lambda: self.gate_zoom.zoom_by(1.25), "Zoom in (mouse wheel)"),
                                      ("−", lambda: self.gate_zoom.zoom_by(0.8), "Zoom out")),
                                  "Your circuit as gates, as in the Logisim tab (edit it there) · click an input to flip it · the IC view and X-ray view are built from this")
        self.gate_zoom = Zoom(self.ctx, f, self.gate_ext, self.paint_gate, on_click=self.gate_click)
        self.gate_zoom.c.grid(row=1, column=0, sticky="nsew")
        self.gate_status = tk.Label(f, text="", font=self.ctx.f_small, anchor="w", padx=10, pady=4); self.gate_status.grid(row=2, column=0, sticky="ew", pady=(6, 0))

    def gate_ext(self):
        lay = getattr(self.doc, "layout", None)
        return gate_extent(lay) if lay is not None and (lay.parts or lay.inputs or lay.outputs) else (0, 0, 400, 200)

    def paint_gate(self, r):
        d = self.doc
        if d.layout is None or d.circuit is None: return
        try: CircuitPainter(r).paint(d.layout, d.circuit, d.values(), d.invals)
        except Exception as e: r.text(20, 20, f"{type(e).__name__}: {e}", 10, "bad", False, "w")           # noqa: BLE001

    def gate_click(self, e, tags):
        t = next((t for t in tags if t.startswith(("inpin:", "indot:"))), None)
        if t is None: return
        name = t.split(":", 1)[1]; p = next((q for q in self.doc.circuit.inputs if q.name == name), None)
        if p is not None and p.width == 1: self.doc.set_input(name, self.doc.invals.get(name, 0) ^ 1)

    def build_ic(self, f):
        f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1)
        self.ic_zoom = None
        self.ic_bar = self._bar(f, (("Fit", lambda: self.ic_zoom.fit(), "Show everything"), ("+", lambda: self.ic_zoom.zoom_by(1.25), "Zoom in (mouse wheel)"),
                                    ("−", lambda: self.ic_zoom.zoom_by(0.8), "Zoom out"), ("Arrange", lambda: self.arrange(False), "Put every chip and terminal back in the automatic arrangement"),
                                    ("Rewire pin…", self.ic_rewire_sel, "Choose which signal the selected pin takes: the circuit changes"), ("Change IC…", self.ic_change_sel, "Make the selected chip's gates another type (7400 -> 7408 ...): the circuit changes")),
                                "Chips instead of gates · click an input to flip it · drag chips and terminals · click a pin, then Rewire · right-click for more · edits change the circuit")
        self.ic_zoom = Zoom(self.ctx, f, lambda: self.sch.extent() if self.sch else (0, 0, 400, 200), self.paint_ic, on_click=self.ic_click, on_hover=self.ic_hover, on_move=lambda ref, dx, dy: self.move_node(ref, dx, dy, False), on_double=self.ic_double, on_right=self.ic_menu)
        self.ic_zoom.c.grid(row=1, column=0, sticky="nsew")
        self.ic_status = tk.Label(f, text="", font=self.ctx.f_small, anchor="w", padx=10, pady=4); self.ic_status.grid(row=2, column=0, sticky="ew", pady=(6, 0))

    def build_xray(self, f):
        f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1)
        self.x_zoom = None
        self.x_bar = self._bar(f, (("Fit", lambda: self.x_zoom.fit(), "Show everything"), ("+", lambda: self.x_zoom.zoom_by(1.25), "Zoom in"), ("−", lambda: self.x_zoom.zoom_by(0.8), "Zoom out"),
                                   ("Rewire pin…", self.x_rewire_sel, "Choose what the selected pin connects to"), ("Undo pin", self.x_undo_sel, "Put the selected pin back as it was"),
                                   ("Reset all", self.x_reset_all, "Remove every rewiring: the chips are wired from the circuit again"), ("Arrange", lambda: self.arrange(True), "Back to the automatic arrangement")),
                               "Chips opened up · drag chips and terminals · click a pin to follow its signal · double-click to rewire · your circuit never changes")
        self.x_zoom = Zoom(self.ctx, f, self.x_extent, self.paint_xray, on_click=self.x_click, on_double=self.x_double, on_right=self.x_double, on_hover=self.x_hover, on_move=lambda ref, dx, dy: self.move_node(ref, dx, dy, True))
        self.x_zoom.c.grid(row=1, column=0, sticky="nsew")
        self.x_status = tk.Label(f, text="", font=self.ctx.f_small, anchor="w", padx=10, pady=4); self.x_status.grid(row=2, column=0, sticky="ew", pady=(6, 0))

    def build_chips(self, f):
        f.columnconfigure(0, weight=1); f.rowconfigure(0, weight=1)
        self.chip_canvas = tk.Canvas(f, highlightthickness=0, bd=0); self.chip_canvas.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(f, command=self.chip_canvas.yview, style="Thin.Vertical.TScrollbar"); sy.grid(row=0, column=1, sticky="ns")
        self.chip_canvas.configure(yscrollcommand=auto(sy))
        self.chip_canvas.bind("<Configure>", lambda e: self.draw_chips())
        for ev, d in (("<Button-4>", -2), ("<Button-5>", 2)): self.chip_canvas.bind(ev, lambda e, d=d: self.chip_canvas.yview_scroll(d, "units"))
        self.chip_canvas.bind("<MouseWheel>", lambda e: self.chip_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def build_wires(self, f):
        f.columnconfigure(0, weight=1); f.rowconfigure(0, weight=1)
        cols = (("n", "#", 44, False), ("sig", "Signal", 120, False), ("a", "From", 300, True), ("b", "To", 300, True), ("col", "Wire", 70, False), ("len", "Holes", 56, False))
        self.wire_tree = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings", selectmode="browse", style="Modern.Treeview")
        for c, t, w, st in cols: self.wire_tree.heading(c, text=t); self.wire_tree.column(c, width=w, minwidth=40, stretch=st, anchor="center" if c in ("n", "col", "len") else "w")
        sy = ttk.Scrollbar(f, command=self.wire_tree.yview, style="Thin.Vertical.TScrollbar"); self.wire_tree.configure(yscrollcommand=auto(sy))
        self.wire_tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns")

    def build_library(self, f):
        f.columnconfigure(0, weight=3); f.columnconfigure(1, weight=2); f.rowconfigure(0, weight=1)
        cols = (("part", "Chip", 70, False), ("title", "Description (as in Logisim-evolution)", 380, True), ("pins", "Pins", 44, False), ("use", "This circuit", 80, False))
        self.lib_tree = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings", selectmode="browse", style="Modern.Treeview")
        for c, t, w, st in cols: self.lib_tree.heading(c, text=t); self.lib_tree.column(c, width=w, minwidth=40, stretch=st, anchor="w" if c == "title" else "center")
        sy = ttk.Scrollbar(f, command=self.lib_tree.yview, style="Thin.Vertical.TScrollbar"); self.lib_tree.configure(yscrollcommand=auto(sy))
        self.lib_tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=0, sticky="nse")
        self.lib_text = tk.Text(f, wrap="none", bd=0, relief="flat", font=("Courier", 10), padx=10, pady=8, state="disabled")
        self.lib_text.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        for i, c in enumerate(K.all_chips()):
            self.lib_tree.insert("", "end", iid=c.part, values=(c.part, c.title, c.pins, ""), tags=("odd",) if i % 2 else ())
        self.lib_tree.bind("<<TreeviewSelect>>", self.lib_pick)

    # ---------------------------------------------------------------- following the circuit
    def on_sess(self, kind):
        if kind in ("changed", "circuits"): self.schedule()
        elif kind == "values" and self.plan is not None: self.live()

    def schedule(self):
        if self._job:
            try: self.after_cancel(self._job)
            except (tk.TclError, ValueError): pass
        self._job = self.after(200, self.refresh)

    def refresh(self):
        self._job = None
        sess = self.sess
        pl = sess.plan()
        if pl is None:
            self.plan = self.board = self.sch = self.xsch = None
            self.headline.configure(text="There is no valid circuit yet - fix the circuit first, then the chips appear here.")
            self.bom.delete(*self.bom.get_children()); self.set_notes(""); self.wire_tree.delete(*self.wire_tree.get_children())
            for c in (self.gate_zoom.c, self.ic_zoom.c, self.x_zoom.c, self.chip_canvas): c.delete("all")
            return
        try:
            self.plan = pl; self.board = B.layout(pl); self.sch = S.layout(pl, False, None, self.pos_ic); self.xsch = S.layout(pl, True, None, self.pos_x)
        except Exception as e:                                           # noqa: BLE001 - never leave the window empty
            self.plan = self.board = self.sch = self.xsch = None
            self.headline.configure(text="The chips could not be worked out for this circuit."); self.set_notes(f"{type(e).__name__}: {e}"); return
        self.title(f"IC view - circuit '{self.doc.cur}' as real 74xx chips")
        self.headline.configure(text=f"Circuit '{self.doc.cur}':  " + report.summary(pl))
        self.bom.delete(*self.bom.get_children())
        for i, (q, item, note) in enumerate(report.logisim_rows(self.doc.circuit, pl)): self.bom.insert("", "end", values=(q, item, note), tags=("odd",) if i % 2 else ())
        lines = [f"• {w}" for w in pl.warnings] + [f"• NOT BUILT - {t} {i}: {why}. It is drawn as a yellow block so you can see what connects to it." for i, t, why in pl.unmapped]
        lines += [f"• {k}" for k in sorted({c.note for ch in pl.chips for c in ch.slots if c and c.note} | {ch.chip.notes for ch in pl.chips if ch.chip.notes})]
        if sess.edits: lines.append(f"• {len(sess.edits)} pin(s) rewired in the X-ray view. This changes only the chip version, not your circuit or its JSON.")
        if sess.dropped: lines.append(f"• {len(sess.dropped)} rewired pin(s) could not be kept because the circuit changed (the chip or the signal is gone).")
        if pl.shorts: lines.append("• Warning: the circuit connects +5 V to GND through constants or wires.")
        self.set_notes("\n".join(lines) if lines else "No warnings.")
        self.wire_tree.delete(*self.wire_tree.get_children())
        for i, (n, name, a, b, col, holes) in enumerate(report.wire_rows(self.board)):
            self.wire_tree.insert("", "end", iid=str(n - 1), values=(n, name, a, b, col, holes), tags=("odd",) if i % 2 else ())
        counts = pl.counts()
        for c in K.all_chips():
            self.lib_tree.set(c.part, "use", f"{counts[c.part]}×" if c.part in counts else ("builds" if c.mapped else "catalogue"))
        self.sel_net = None
        if self.x_sel and (self.x_sel[0] not in {c.ref for c in pl.chips}): self.x_sel = self.x_hot = None
        self.ic_zoom.view = None; self.x_zoom.view = None; self.gate_zoom.view = None
        self.draw_all(); self.queue_test()

    def set_notes(self, text):
        self.notes.configure(state="normal"); self.notes.delete("1.0", "end"); self.notes.insert("1.0", text); self.notes.configure(state="disabled")

    # ---------------------------------------------------------------- testing the chip version
    def queue_test(self):
        units = sum(len(ch.slots) for ch in self.plan.chips)
        P = self.ctx.P
        if self.plan.unmapped:
            self.test_lbl.configure(text="Not tested: some parts have no 74xx chip, so the chip version is incomplete.", fg=P["muted"]); return
        if units > MAX_AUTO_TEST_UNITS:
            self.test_lbl.configure(text="Large circuit: press 'Test the chips' to compare it with your circuit.", fg=P["muted"]); return
        self.test_lbl.configure(text="Testing the chips ...", fg=P["muted"])
        if self._test_job:
            try: self.after_cancel(self._test_job)
            except (tk.TclError, ValueError): pass
        self._test_job = self.after(60, self.run_test)

    def run_test(self):
        self._test_job = None
        if self.plan is None: return
        P = self.ctx.P
        try: res = verify.check(self.doc.circuit, self.plan, trials=40, exhaustive_bits=6)
        except Exception as e:                                           # noqa: BLE001
            self.test_lbl.configure(text=f"The test could not run: {type(e).__name__}: {e}", fg=P["bad"]); return
        if res is None: self.test_lbl.configure(text="Not tested: some parts have no 74xx chip, so the chip version is incomplete.", fg=P["muted"]); return
        n, bad = res
        edited = " (with your rewiring)" if self.sess.edits else ""
        if bad: self.test_lbl.configure(text=f"✗ The chip version{edited} differs from your gates: " + bad[0], fg=P["bad"])
        else: self.test_lbl.configure(text=f"✓ Tested{edited}: the chips gave the same result as your gates in all {n} output checks (inputs: {'every combination' if sum(p.width for p in self.doc.circuit.inputs) <= 6 else 'random values'}).", fg=P["ok"])

    # ---------------------------------------------------------------- drawing
    def draw_all(self):
        if self.plan is None: return
        k = self.cur
        if k == "chips": self.draw_chips()
        elif k == "gate": self.gate_zoom.redraw(); self.gate_text()
        elif k == "ic": self.ic_zoom.redraw(); self.live_status()
        elif k == "xray": self.x_zoom.redraw(); self.x_text()

    def live(self):
        """The inputs or the clock changed (truth-table play, click, tick): the chips run again, show the new values."""
        if self.cur == "gate": self.gate_zoom.redraw(); self.gate_text()
        elif self.cur == "ic": self.ic_zoom.redraw(); self.live_status()
        elif self.cur == "xray": self.x_zoom.redraw()

    # ---- Gate view
    def gate_text(self):
        d = self.doc
        try: v = d.values()
        except Exception: v = {}                                         # noqa: BLE001
        self.gate_status.configure(text="Inputs  " + "  ".join(f"{p.name}={v.get(p.name)}" for p in d.circuit.inputs[:10]) + "     Outputs  " + "  ".join(f"{p.name}={v.get(p.name)}" for p in d.circuit.outputs[:10]))

    # ---- moving chips and terminals (each of the IC view and the X-ray view keeps its own arrangement; the circuit is untouched)
    def move_node(self, ref, dx, dy, xray):
        sch = self.xsch if xray else self.sch; pos = self.pos_x if xray else self.pos_ic
        if dx is None: self._grab = None; return
        if self._grab is None or self._grab[0] != ref:
            n = sch.node(ref)
            if n is None: return
            self._grab = (ref, n.x, n.y)
        _r, x0, y0 = self._grab
        pos[ref] = (round((x0 + dx) / 10) * 10, round((y0 + dy) / 10) * 10)
        if xray: self.xsch = S.layout(self.plan, True, None, self.pos_x); self.x_zoom.redraw()
        else: self.sch = S.layout(self.plan, False, None, self.pos_ic); self.ic_zoom.redraw()

    def arrange(self, xray):
        (self.pos_x if xray else self.pos_ic).clear()
        if xray: self.xsch = S.layout(self.plan, True); self.x_zoom.fit()
        else: self.sch = S.layout(self.plan, False); self.ic_zoom.fit()

    # ---- IC view
    def paint_ic(self, r):
        S.draw(r, self.sch, self.sess.value, self.sel_net, self.x_hot)

    def live_status(self):
        pl, d = self.plan, self.doc
        if pl is None: return
        try: v = d.values()
        except Exception: v = {}                                         # noqa: BLE001
        ins = [f"{p.name}={v.get(p.name)}" for p in d.circuit.inputs]
        gates, chips = [], []
        for e in pl.externals:
            if e.kind != "led" or not e.src or e.src[0] is None: continue
            w = v.get(e.src[0]); nm = e.label.replace("Output ", "").replace("LED ", "")
            gates.append(f"{nm}={'–' if w is None else (w >> e.src[1]) & 1}"); chips.append(f"{nm}={self.sess.value(e.pins['anode'])}")
        same = "" if not self.sess.checked else ("   ✗ different" if self.sess.mismatch else "   ✓ same")
        self.ic_status.configure(text="Inputs  " + "  ".join(ins[:8]) + "     Gates: " + "  ".join(gates[:8]) + "     Chips: " + "  ".join(chips[:8]) + same)

    def ic_click(self, e, tags):
        ext = next((t[4:] for t in tags if t.startswith("ext:")), None)
        if ext is not None: self.flip(ext); return
        p = self.pin_of(tags)
        if p is not None:
            self.ic_sel = p; net = self.plan.chip(p[0]).pins.get(p[1]) if self.plan.chip(p[0]) else None
            self.x_hot = net if net not in TIES else None; self.sel_net = None
            self.ic_zoom.redraw(); self.ic_status.configure(text=self.pin_text(*p) + "     (double-click: rewire - changes the circuit)"); return
        self.ic_sel = None; self.x_hot = None
        nid = next((t[4:] for t in tags if t.startswith("net:") and t[4:].isdigit()), None)
        self.sel_net = int(nid) if nid is not None else None
        self.ic_zoom.redraw()
        if self.sel_net is not None: self.ic_status.configure(text=self.net_info(self.sel_net))

    def ic_hover(self, e, tags):
        nid = next((t[4:] for t in tags if t.startswith("net:") and t[4:].isdigit()), None)
        if nid is not None: self.ic_status.configure(text=self.net_info(int(nid)))

    def net_info(self, nid):
        for net, i in self.sch.nid_of.items():
            if i == nid:
                v = self.sess.value(net)
                ends = self.plan.nets().get(net, [])
                return f"Signal {self.plan.name(net)} = {'?' if v is None else v}:   " + ",  ".join(sorted(report.endpoint(self.plan, x) for x in ends))
        return ""

    # ---- editing the circuit from the IC view
    def ic_double(self, e, tags):
        p = self.pin_of(tags)
        if p is not None: self.ic_sel = p; self.ic_rewire(p)

    def ic_rewire_sel(self):
        if self.ic_sel: self.ic_rewire(self.ic_sel)
        else: self.ic_status.configure(text="Click a pin of a chip first, then press Rewire pin…")

    def ic_change_sel(self):
        ref = self.ic_sel[0] if self.ic_sel else (self.plan.chips[0].ref if len(self.plan.chips) == 1 else None)
        if ref: self.ic_change(ref)
        else: self.ic_status.configure(text="Click a pin of the chip first (or right-click the chip), then press Change IC…")

    def ic_menu(self, e, tags):
        m = self.ctx.menu(); p = self.pin_of(tags)
        ref = p[0] if p else next((t[5:] for t in tags if t.startswith("node:")), None)
        if ref is None or self.plan.chip(ref) is None:
            m.add_command(label="Arrange chips and terminals automatically", command=lambda: self.arrange(False))
        else:
            ch = self.plan.chip(ref)
            if p: m.add_command(label=f"Rewire pin {p[1]} ({ch.chip.pin_name(p[1])})…", command=lambda: self.ic_rewire(p))
            m.add_command(label=f"Change {ch.ref} ({ch.part}) to another IC…", command=lambda: self.ic_change(ref))
            m.add_separator(); m.add_command(label="Arrange chips and terminals automatically", command=lambda: self.arrange(False))
        m.tk_popup(e.x_root, e.y_root)

    def ic_rewire(self, p):
        """Rewire an input pin of a chip in the IC view: the gate that the unit stands for takes the new signal (the circuit changes)."""
        ref, pin = p; ch = self.plan.chip(ref)
        if ch is None: return
        src = E.pin_source(self.doc, ch, pin)
        if src is None:
            self.ic_status.configure(text=f"{ref} pin {pin} is not the pin of a single gate of the circuit (power, unused or part of a bigger block): edit the Gate view or the JSON, or rewire it in the X-ray view."); return
        gate, port, kind = src
        if kind == "out":
            self.ic_status.configure(text="The signal on an output pin is the gate's output name: rename it in the JSON, or rewire the pins that read it."); return
        now = gate.ins.get(port) or "(not connected)"
        opts = [(nm, nm, "signal") for nm in sorted(E.signal_choices(self.doc, gate), key=str.lower)]
        NetPicker(self, f"{ref} ({ch.part}) pin {pin}: input {port} of gate {gate.id} ({gate.type_name}) - the circuit changes", now, opts,
                  lambda nm: self._edit_done(E.set_input(self.doc, gate.id, port, nm)))

    def ic_change(self, ref):
        ch = self.plan.chip(ref); opts = E.swap_choices(self.doc, ch) if ch else []
        if not opts:
            self.ic_status.configure(text=f"{ref} cannot be changed to another IC here (it holds gates that are not one-to-one with the circuit); edit the Gate view or the JSON."); return
        NetPicker(self, f"Change {ref} ({ch.part}): its gates become another type and the circuit changes", ch.chip.units[0].func,
                  [(f"{f}  →  {part}", f, f"{part}") for f, part in opts], lambda f: self._edit_done(E.swap_type(self.doc, ch, f)))

    def _edit_done(self, err):
        if err: self.ic_status.configure(text=err)

    def flip(self, ref):
        """Click an input of the IC view: flip that input of the circuit (so the gates and the chips both follow)."""
        x = self.plan.external(ref)
        if x is None or x.kind != "switch" or not x.src: return
        name, bit = x.src
        self.doc.set_input(name, (self.doc.invals.get(name, 0) ^ (1 << bit)))

    # ---- X-ray
    def x_extent(self):
        return self.xsch.extent() if self.xsch is not None else (0, 0, 400, 100)

    def paint_xray(self, r):
        if self.xsch is None: return
        if not self.plan.chips:
            r.text(20, 20, "No 74xx chips are needed for this circuit.", 11, "#9ca3af", False, "w"); return
        S.draw(r, self.xsch, self.sess.value, self.sel_net, self.x_hot)

    def pin_of(self, tags):
        t = next((t for t in tags if t.startswith("pin:")), None)
        if t is None: return None
        _, ref, pin = t.split(":"); return ref, int(pin)

    def pin_text(self, ref, pin):
        ch = self.plan.chip(ref); cat = ch.chip; net = ch.pins.get(pin)
        where = "not connected" if net is None else "+5 V" if net == VCC else "GND" if net == GND else self.plan.name(net)
        mark = "  (rewired by you)" if (ref, pin) in self.plan.edited else ""
        return f"{ref} ({ch.part}) pin {pin} [{cat.pin_name(pin)}] → {where}{mark}"

    def x_text(self):
        n = len(self.sess.edits)
        if self.x_sel and self.plan.chip(self.x_sel[0]): self.x_status.configure(text=self.pin_text(*self.x_sel) + "     (double-click to rewire)")
        else: self.x_status.configure(text=(f"{n} pin(s) rewired. " if n else "") + "Click a pin to follow its signal; double-click it to rewire.")

    def x_click(self, e, tags):
        p = self.pin_of(tags)
        ext = next((t[4:] for t in tags if t.startswith("ext:")), None)
        if ext is not None: self.flip(ext); return
        nid = next((t[4:] for t in tags if t.startswith("net:") and t[4:].isdigit()), None)
        if p is None:
            self.x_sel = self.x_hot = None; self.sel_net = int(nid) if nid is not None else None
        else:
            self.sel_net = None
            self.x_sel = p; net = self.plan.chip(p[0]).pins.get(p[1]); self.x_hot = net if net not in TIES else None
        self.x_zoom.redraw(); self.x_text()

    def x_hover(self, e, tags):
        p = self.pin_of(tags)
        if p is not None and self.plan is not None: self.x_status.configure(text=self.pin_text(*p) + "     (double-click to rewire)")

    def x_double(self, e, tags):
        p = self.pin_of(tags)
        if p is not None: self.x_sel = p; self.x_rewire(p)

    def x_rewire_sel(self):
        if self.x_sel: self.x_rewire(self.x_sel)
        else: self.x_status.configure(text="Click a pin first, then press Rewire pin…")

    def x_undo_sel(self):
        if self.x_sel: self.sess.reset_pin(*self.x_sel)

    def x_reset_all(self): self.sess.clear_edits()

    def x_rewire(self, p):
        ref, pin = p; pl = self.plan; ch = pl.chip(ref); cat = ch.chip
        names = {}
        for net, ends in pl.nets().items():
            if net not in TIES: names[pl.name(net)] = len(ends)
        now = self.pin_text(ref, pin).split("→")[1].strip()
        opts = [("(not connected)", NONE, "pin left open"), ("GND  (0 V)", "GND", "rail"), ("+5 V  (VCC)", "VCC", "rail")]
        opts += [(nm, nm, f"{k} pin(s)") for nm, k in sorted(names.items(), key=lambda kv: kv[0].lower())]
        kind = {"in": "input", "out": "output", "io": "input/output", "vcc": "power", "gnd": "power", "nc": "not used"}[cat.pin_kind(pin)]
        NetPicker(self, f"{ref} ({ch.part}) pin {pin} [{cat.pin_name(pin)}] - {kind}", now, opts,
                  lambda v: self.sess.set_pin(ref, pin, v), (lambda: self.sess.reset_pin(ref, pin)) if (ref, pin) in pl.edited else None)

    # ---- Chips tab
    def draw_chips(self):
        c = self.chip_canvas; c.delete("all")
        if self.plan is None: return
        if not self.plan.chips: c.create_text(20, 20, anchor="nw", text="No 74xx chips are needed for this circuit.", fill=self.ctx.P["muted"], font=self.ctx.f_body); return
        W = max(c.winfo_width(), 400); gap = 14
        cols = max(1, int((W - gap) // (B.CARD_W + gap)))
        r = TkRenderer(c, self.ctx.P, self.ctx.sans, 1.0, 0, 0)
        x = y = gap; rowh = 0; col = 0
        for ch in self.plan.chips:
            w, h = B.card_size(ch)
            if col == cols: col = 0; x = gap; y += rowh + gap; rowh = 0
            B.draw_chip_card(r, self.plan, ch, x, y)
            x += w + gap; rowh = max(rowh, h); col += 1
        c.configure(scrollregion=(0, 0, cols * (B.CARD_W + gap) + gap, y + rowh + gap))

    def lib_pick(self, _e=None):
        s = self.lib_tree.selection()
        if not s: return
        c = K.chip(s[0]); half = c.pins // 2
        L = [f"{c.part}  -  {c.title}", f"{c.pins}-pin DIP" + ("  (0.6 inch wide)" if c.wide else ""), "" if c.logisim else "From a lab sheet (not in Logisim's TTL library)", ""]
        if c.notes: L += [c.notes, ""]
        L.append("   pin  name      " + "name    pin")
        for i in range(1, half + 1):
            a, b = i, c.pins + 1 - i
            L.append(f"   {a:>2}   {c.pin_name(a):<8}  {c.pin_name(b):>8}  {b:<2}")
        L += ["", "Pins are numbered anticlockwise, starting at the notch.", "The IC view " + ("builds circuits with this chip." if c.mapped else "only lists this chip (it does not place it automatically).")]
        self.lib_text.configure(state="normal"); self.lib_text.delete("1.0", "end"); self.lib_text.insert("1.0", "\n".join(L)); self.lib_text.configure(state="disabled")

    # ---------------------------------------------------------------- export
    def export_menu(self):
        if self.plan is None: return
        m = self.ctx.menu()
        for label, fn in (("Build guide (.txt)", self.save_guide), ("IC view picture (.png)", self.save_ic), ("X-ray view picture (.png)", self.save_xray),
                          ("Chip pin diagrams (.png)", self.save_cards), ("Parts list (.csv)", self.save_bom), ("Wiring list (.csv)", self.save_wires)):
            m.add_command(label=label, command=fn)
        m.tk_popup(self.winfo_rootx() + self.winfo_width() - 240, self.winfo_rooty() + 48)

    def _save(self, title, ext, name, data, binary=False):
        p = self.ctx.choose_file("save", title, [ext], name)
        if not p: return
        if not p.lower().endswith(ext): p += ext
        try:
            with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as f: f.write(data)
        except Exception as e:                                           # noqa: BLE001
            self.ctx.say(title, str(e), self); return
        self.ctx.say("Saved", p, self)

    def _png(self, im):
        buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()

    def save_guide(self): self._save("Save build guide", ".txt", "build_guide.txt", report.guide(self.plan, self.board, self.doc.cur))
    def save_ic(self): self._save("Save IC view picture", ".png", "ic_view.png", self._png(S.to_png(self.sch, self.sess.value)), True)

    def save_xray(self):
        im = S.to_png(self.xsch, self.sess.value) if self.xsch is not None and self.plan.chips else None
        if im is None: self.ctx.say("X-ray", "There are no chips to draw.", self); return
        self._save("Save X-ray pictures", ".png", "xray.png", self._png(im), True)

    def save_cards(self):
        im = B.cards_png(self.plan)
        if im is None: self.ctx.say("Chip diagrams", "There are no chips to draw.", self); return
        self._save("Save chip diagrams", ".png", "chips.png", self._png(im), True)

    def save_bom(self): self._save("Save parts list", ".csv", "parts.csv", report.to_csv([(q, i, n) for q, i, n in report.bom(self.plan, self.board)], ("Qty", "Part", "Notes")))
    def save_wires(self): self._save("Save wiring list", ".csv", "wiring.csv", report.to_csv(report.wire_rows(self.board), ("#", "Signal", "From", "To", "Wire", "Holes")))
