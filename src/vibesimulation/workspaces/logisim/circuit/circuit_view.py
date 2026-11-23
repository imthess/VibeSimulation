"""Box 3: the circuit drawn with Logisim's symbols. Click pins to toggle inputs; right-click parts to edit."""
import tkinter as tk

from vibesimulation.workspaces.logisim.components.gates.gate_base import Gate
from vibesimulation.workspaces.logisim.components.registry import ComponentRegistry as R
import vibesimulation.workspaces.logisim.core.commands as C
from vibesimulation.workspaces.logisim.export.logisim import to_circ
from vibesimulation.workspaces.logisim.layout.painter import CircuitPainter, extent, pin_box_width
from vibesimulation.presets import merge
from vibesimulation.ui.controls.canvas_renderer import TkRenderer
from vibesimulation.workspaces.logisim.circuit.dragging import DragMixin, snap
from vibesimulation.workspaces.logisim.circuit.parts_palette import PaletteDialog, PropsDialog
from vibesimulation.ui.controls.widgets import Btn, QuietLabel
from vibesimulation.ui.views.base import View
class CircuitView(DragMixin, View):
    HAS_IC = True                      # the IC view belongs to the Logisim tab only
    number, title, hint = None, "Circuit", "click an input to toggle it; right-click a part to edit"

    def build(self):
        ctx = self.ctx
        self.main = None
        t = self.tools
        for txt, fn, tip, side in (("↷", lambda: self.main.redo(), "Redo (Ctrl+Y)", "right"), ("↶", lambda: self.main.undo(), "Undo (Ctrl+Z)", "right")):
            b = Btn(ctx, t, txt, fn, "ghost", padx=9, pady=0, font=ctx.f_icon).tip(tip); b.pack(side=side)
            if tip.startswith("Undo"): self.b_undo = b
            else: self.b_redo = b
        Btn(ctx, t, "⬇", self.download, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Download .circ (open it in Logisim-evolution)").pack(side="right", before=self.b_redo)
        self.mode = "edit"; self.mode_btns = {}; self.psel = set()          # Logisim's tools: Edit (arrow), Wire (pencil), Poke (hand); psel = selected circuit pins
        sep = tk.Frame(t, width=1, bd=0); sep.pack(side="right", fill="y", padx=6, pady=4); self.sep = sep
        Btn(ctx, t, "▦", self.arrange, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Arrange: tidy the whole circuit. Every connection stays; only the picture is rearranged").pack(side="right")
        if self.HAS_IC: Btn(ctx, t, "IC", self.ic_view, "ghost", padx=9, pady=0, font=ctx.f_bold).tip("IC view: this circuit built from real 74xx chips, wired automatically").pack(side="right")
        for key, txt, tip in (("poke", "☝", "Poke tool (hand): click an input to switch it. Drag empty space to move the view"), ("wire", "✎", "Wire tool: drag from a pin, an input, an output or the middle of a wire to draw a new wire"),
                              ("edit", "↖", "Edit tool (arrow): select, move and bend things")):
            bt = Btn(ctx, t, txt, lambda k=key: self.set_mode(k), "primary" if key == "edit" else "ghost", padx=9, pady=0, font=ctx.f_icon).tip(tip); bt.pack(side="right"); self.mode_btns[key] = bt
        b = self.body; b.rowconfigure(1, weight=1)
        bar = tk.Frame(b, bd=0); bar.grid(row=0, column=0, sticky="ew", pady=(0, 6)); self.bar = bar
        self.tool = None; self.tool_btns = {}          # the tools and the circuit list live in the side bar (explorer), like Logisim's
        # ---- simulation controls (only shown when the circuit has a clock / flip-flops ...): Logisim's Simulate menu
        self.simbar = tk.Frame(bar, bd=0); self._auto = None; self.hz = 2      # second row, so a narrow pane never squeezes the title
        self.b_hz = Btn(ctx, self.simbar, f"{self.hz} Hz", self.next_hz, "ghost", padx=6, pady=0); self.b_hz.tip("Speed of Run (click to change)")
        self.b_auto = Btn(ctx, self.simbar, "▶", self.toggle_auto, "ghost", padx=8, pady=0, font=ctx.f_icon); self.b_auto.tip("Run: tick by itself (Ctrl+K)")
        for txt, fn, tip in (("↺", lambda: self.reset_sim(), "Reset the simulation: every flip-flop forgets, the clock starts again (Ctrl+R)"), ("⟳", lambda: self.doc.tick(2), "Tick a full clock cycle (Ctrl+Shift+T)"), ("⏭", lambda: self.doc.tick(1), "Tick half a clock cycle (Ctrl+T)")):
            Btn(ctx, self.simbar, txt, fn, "ghost", padx=8, pady=0, font=ctx.f_icon).tip(tip).pack(side="right")
        self.b_auto.pack(side="right"); self.b_hz.pack(side="right")
        self.view = None; self._pan = None; self._drag = None; self.wsel = set()          # None = fit the whole circuit; else (scale, x offset, y offset)
        for txt, fn, tip in (("Fit", self.fit, "Show the whole circuit (double-click empty space)"), ("+", lambda: self.zoom_by(1.25), "Zoom in (mouse wheel)"), ("−", lambda: self.zoom_by(0.8), "Zoom out (mouse wheel)")):
            Btn(ctx, bar, txt, fn, "ghost", padx=9, pady=4).tip(tip).pack(side="right", padx=(0, 2))
        self.canvas = tk.Canvas(b, highlightthickness=0, bd=0); self.canvas.grid(row=1, column=0, sticky="nsew")
        self.status = QuietLabel(b, text="", font=ctx.f_small, anchor="w", padx=10, pady=3); self.status.over = self.canvas
        self.canvas.bind("<Configure>", lambda e: self.draw()); self.canvas.bind("<Button-1>", self.on_click)
        import sys
        MID, RGT = ("3", "2") if sys.platform == "darwin" else ("2", "3")        # on macOS Tk the middle button is 3 and the right one 2
        for ev in (f"<Button-{RGT}>", "<Control-Button-1>"): self.canvas.bind(ev, self.on_right)
        self._space = False                                                         # like Logisim / KiCad: the middle button or Space + drag moves the view
        self.canvas.bind(f"<Button-{MID}>", self.pan_start); self.canvas.bind(f"<B{MID}-Motion>", self.pan_drag); self.canvas.bind(f"<ButtonRelease-{MID}>", lambda e: setattr(self, "_pan", None))
        self.canvas.bind("<KeyPress-space>", lambda e: setattr(self, "_space", True)); self.canvas.bind("<KeyRelease-space>", lambda e: setattr(self, "_space", False))
        self.canvas.bind("<Motion>", self.on_move)
        self.sel = None                                     # the part that is selected (turn / delete it from the keyboard)
        self.sels = set()                                   # all selected parts (Ctrl+click, Shift+drag a rectangle, Ctrl+A)
        self.canvas.configure(takefocus=1)
        for key in ("<Key-r>", "<Key-R>"): self.canvas.bind(key, lambda e: self.turn(1))
        self.canvas.bind("<Shift-Key-R>", lambda e: self.turn(-1)); self.canvas.bind("<Key-l>", lambda e: self.turn(-1))
        for key, fn in (("<Control-Key-t>", lambda e: self.doc.tick(1)), ("<Control-Key-T>", lambda e: self.doc.tick(2)), ("<Control-Key-k>", lambda e: self.toggle_auto()), ("<Control-Key-r>", lambda e: self.reset_sim())):
            self.canvas.bind(key, fn)
        for key, fn in (("<Control-Key-a>", lambda e: self.select_all()), ("<Control-Key-c>", lambda e: self.copy()), ("<Control-Key-x>", lambda e: self.cut()), ("<Control-Key-v>", lambda e: self.paste())):
            self.canvas.bind(key, fn)
        for key in ("<Key-Delete>", "<Key-BackSpace>"): self.canvas.bind(key, lambda e: self.delete_selected())
        self.canvas.bind("<Key-Escape>", lambda e: (self.set_tool(None) if self.tool else self.select(None)))
        self.canvas.bind("<MouseWheel>", lambda e: self.wheel(e, 1.15 if e.delta > 0 else 1 / 1.15))
        self.canvas.bind("<Button-4>", lambda e: self.wheel(e, 1.15)); self.canvas.bind("<Button-5>", lambda e: self.wheel(e, 1 / 1.15))
        self.canvas.bind("<B1-Motion>", self.motion); self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Double-Button-1>", self.on_double)
        ctx.themed.append(self._paint); self._paint()

    def set_mode(self, m):
        self.mode = m; self._drag = None
        for k, b in self.mode_btns.items():
            kind = "primary" if k == m else "ghost"
            if b.kind != kind: b.kind = kind; b.paint()
        if self.tool: self.set_tool(None)
        self.canvas.configure(cursor={"edit": "arrow", "wire": "pencil", "poke": "hand2"}[m])
        self.status.configure(text={"edit": "Edit tool: drag a part to move it, drag empty space to select, drag a wire to move it",
                                    "wire": "Wire tool: drag from a pin, an input, an output or the middle of a wire to a pin to connect it",
                                    "poke": "Poke tool: click an input to switch it. Drag empty space to move the view"}[m])
        self.canvas.focus_set()

    def ic_view(self):
        """Open the IC view window: the circuit as real 74xx chips, with a breadboard wiring picture."""
        if not self.doc.valid or self.doc.circuit is None:
            self.status.configure(text="There is no valid circuit yet; fix it first, then open the IC view."); return
        from vibesimulation.workspaces.logisim.ic.view import open_ic_view
        open_ic_view(self.ctx, self.doc, self.card.master)

    def arrange(self):
        """Tidy the whole circuit: the engine places every part, input and output again; connections do not change."""
        if not self.doc.valid or self.doc.layout is None: return
        c = self.doc.circuit.copy(); C.ClearPositions().apply(c)
        if self._try(c) is None: return self.status.configure(text="The circuit could not be arranged automatically; nothing changed.")
        self.run(C.ClearPositions()); self.view = None; self.wsel = set(); self.psel = set(); self.draw()
        self.status.configure(text="Arranged. Every connection is the same; Ctrl+Z brings the old picture back.")

    def _freeze(self):
        """Once you start editing by hand the picture stops zooming to fit, so nothing shifts under your mouse."""
        if self.view is None and getattr(self, "fit_view", None): self.view = self.fit_view

    def _pin_all(self):
        """A command that remembers where everything is drawn now (so adding or moving one thing never moves another)."""
        lay = self.doc.layout
        return C.PinLayout({p.comp.id: (p.x, p.y) for p in lay.parts}, {**{("in", pin.name): (x, y) for pin, x, y in lay.inputs}, **{("out", pin.name): (x, y) for pin, x, y in lay.outputs}})

    def _paint(self):
        P = self.ctx.P
        self.sep.configure(bg=P["border"] if "border" in P else P["muted"])
        self.bar.configure(bg=P["card"]); self.status.configure(bg=P["soft_h"], fg=P["text"]); self.canvas.configure(bg=P["canvas"])
        self.draw()

    # ---------------------------------------------------------------- drawing
    # ---------------------------------------------------------------- circuits of the project (Logisim: the explorer's circuit list)
    def refresh_tabs(self): pass          # the circuit list is the explorer's job now

    def new_circuit(self):
        n = self.ctx.ask_string("New circuit", "Name of the new circuit:", f"circuit{len(self.doc.circuit_names()) + 1}")
        if n:
            err = self.doc.add_circuit(n)
            if err: self.ctx.say("New circuit", err)

    def tab_menu(self, e, name):
        m = self.ctx.menu()
        m.add_command(label="Edit this circuit", command=lambda: self.doc.switch(name))
        m.add_command(label="Rename…", command=lambda: self.rename_circuit(name))
        m.add_command(label="Delete circuit", command=lambda: self.delete_circuit(name))
        m.tk_popup(e.x_root, e.y_root)

    def rename_circuit(self, name):
        n = self.ctx.ask_string("Rename circuit", f"New name for '{name}':", name)
        if n:
            err = self.doc.rename_circuit(name, n)
            if err: self.ctx.say("Rename circuit", err)

    def delete_circuit(self, name):
        if self.ctx.ask("Delete circuit", f"Delete the circuit '{name}'?"):
            err = self.doc.delete_circuit(name)
            if err: self.ctx.say("Delete circuit", err)

    def on_doc(self, kind):
        if kind in ("changed", "circuits"): self.refresh_tabs()
        if kind == "changed":
            self.b_undo.set_enabled(self.doc.can_undo()); self.b_redo.set_enabled(self.doc.can_redo())
            seq = self.doc.has_seq()
            if seq and not self.simbar.winfo_ismapped(): self.simbar.pack(side="left", padx=(0, 8))
            elif not seq:
                self.simbar.pack_forget()
                if self._auto: self.toggle_auto()
        self.draw()

    # ---------------------------------------------------------------- simulation (Logisim: Simulate menu)
    def toggle_auto(self):
        if self._auto:
            self.canvas.after_cancel(self._auto); self._auto = None; self.b_auto.configure(text="▶")
        elif self.doc.has_seq():
            self.b_auto.configure(text="⏸"); self._auto_step()

    def _auto_step(self):
        self.doc.tick(1)
        self._auto = self.canvas.after(int(1000 / self.hz / 2), self._auto_step) if self.doc.has_seq() else None

    def next_hz(self):
        hzs = [1, 2, 4, 8, 16, 32]; self.hz = hzs[(hzs.index(self.hz) + 1) % len(hzs)] if self.hz in hzs else 2
        self.b_hz.configure(text=f"{self.hz} Hz")

    def reset_sim(self):
        if self._auto: self.toggle_auto()
        self.doc.reset_sim()

    def draw(self):
        self._draw()
        for f in list(getattr(self, "draw_hooks", ())): f()

    def _draw(self):
        c, d, P = self.canvas, self.doc, self.ctx.P
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 20 or H < 20: return
        if d.layout is None or d.circuit is None:
            msg = d.layout_error or ("\n".join(d.errors[:3]) if d.errors else "")
            c.create_text(W / 2, H / 2, text="No circuit to draw yet.\n\n" + msg, fill=P["muted"], font=self.ctx.f_body, justify="center", width=W - 40)
            return
        blank = not d.circuit.inputs and not d.circuit.outputs and not d.circuit.components
        if blank and d.valid:
            self.fit_view = (1.0, 0, 0); self.scale, self.org = 1.0, (0, 0)
            step = 20
            if self.ctx.cfg.get("grid", True):
                for gx in range(0, W, step):
                    for gy in range(0, H, step): c.create_rectangle(gx, gy, gx + 1, gy + 1, fill=P["dot"], outline="")
            c.create_text(W / 2, H / 2, text="Empty circuit\n\nRight-click here to add an input, a part or an output,\nor use Parts… / the JSON box. Both stay in sync.", fill=P["muted"], font=self.ctx.f_body, justify="center")
            self.status.configure(text="Blank circuit: right-click to start building")
            return
        x0, y0, x1, y1 = extent(d.layout)
        pad = 24; s = min((W - 2 * pad) / max(1, x1 - x0), (H - 2 * pad) / max(1, y1 - y0), 1.6)
        ox = (W - (x1 - x0) * s) / 2 - x0 * s; oy = (H - (y1 - y0) * s) / 2 - y0 * s
        self.fit_view = (s, ox, oy)
        if self.view:
            vs, vx, vy = self.view                                                  # a picture that was set aside (an other circuit was opened): show everything again
            if (x1 * vs + vx < 0 or x0 * vs + vx > W or y1 * vs + vy < 0 or y0 * vs + vy > H): self.view = None
            else: s, ox, oy = self.view
        self.scale, self.org = s, (ox, oy)
        extra = (f"  ·  tick {d.tick_n}" + ("  ·  OSCILLATING: a feedback loop never settles" if d.oscillating else "")) if d.has_seq() else ""
        self.status.configure(text=(f"Zoom {round(s * 100)}%  ·  mouse wheel zooms, drag empty space to move, double-click to fit" if self.view else
                              f"Whole circuit shown ({round(s * 100)}%)  ·  mouse wheel zooms in, drag to move") + extra)
        if getattr(d.layout, "rough", False): self.status.configure(text="Large circuit: wires are drawn as simple guide lines (they may overlap); the logic and results are exact.  ·  " + self.status.cget("text"))
        step = 20 * s
        if step >= 8 and self.ctx.cfg.get("grid", True):
            gx = ox % step
            while gx < W:
                gy = oy % step
                while gy < H:
                    c.create_rectangle(gx, gy, gx + 1, gy + 1, fill=P["dot"], outline=""); gy += step
                gx += step
        r = TkRenderer(c, P, self.ctx.sans, s, ox, oy)
        CircuitPainter(r).paint(d.layout, d.circuit, d.values(), d.invals)
        for sid in list(self.sels):
            pl = next((q for q in d.layout.parts if q.comp.id == sid), None)
            if pl is None: self.sels.discard(sid); self.sel = None if self.sel == sid else self.sel
            else:
                x0, y0, x1, y1 = pl.comp.bounds()
                c.create_rectangle(ox + (pl.x + x0 - 6) * s, oy + (pl.y + y0 - 6) * s, ox + (pl.x + x1 + 6) * s, oy + (pl.y + y1 + 6) * s, outline=P["accent"], dash=(4, 3), width=2, tags="sel")
        for kind, name in list(self.psel):                                        # selected circuit pins
            tup = next((t for t in (d.layout.inputs if kind == "in" else d.layout.outputs) if t[0].name == name), None)
            if tup is None: self.psel.discard((kind, name)); continue
            pin, px, py = tup; wd = pin_box_width(pin.width)
            xa, xb = (px - wd - 60, px + 6) if kind == "in" else (px - 6, px + wd + 60)
            c.create_rectangle(ox + xa * s, oy + (py - 16) * s, ox + xb * s, oy + (py + 16) * s, outline=P["accent"], dash=(4, 3), width=2, tags="sel")
        for net, piece in list(self.wsel):                                       # selected wire pieces
            if not any(tuple(w[:4]) == piece and w[4] == net for w in d.layout.wires): self.wsel.discard((net, piece)); continue
            a, b, e2, f2 = piece
            c.create_line(ox + a * s, oy + b * s, ox + e2 * s, oy + f2 * s, fill=P["accent"], width=max(4, 4 * s), capstyle="round", tags="sel")
            for qx, qy in ((a, b), (e2, f2)): c.create_rectangle(ox + qx * s - 4, oy + qy * s - 4, ox + qx * s + 4, oy + qy * s + 4, fill=P["accent"], outline="", tags="sel")
        if not d.valid:
            c.create_rectangle(0, 0, W, 22, fill=P["badbg"], outline="")
            c.create_text(10, 11, anchor="w", text="The JSON has a problem, so this is the last good version. Fix the JSON to update it.", fill=P["bad"] if "bad" in P else P["text"], font=self.ctx.f_body)

    # ---------------------------------------------------------------- zoom and pan
    def fit(self): self.view = None; self.draw()

    def zoom_at(self, f, px, py):
        s, ox, oy = self.view or getattr(self, "fit_view", (1, 0, 0)); ns = max(0.12, min(6.0, s * f)); f = ns / s
        self.view = (ns, px - (px - ox) * f, py - (py - oy) * f); self.draw()

    def zoom_by(self, f): self.zoom_at(f, self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)

    def wheel(self, e, f):
        st = getattr(e, "state", 0); s, ox, oy = self.view or getattr(self, "fit_view", (1, 0, 0))
        if st & 1: self.view = (s, ox, oy + (60 if f > 1 else -60)); self.draw()               # Shift + wheel: up / down
        elif st & 4: self.view = (s, ox + (60 if f > 1 else -60), oy); self.draw()             # Ctrl + wheel: left / right
        else: self.zoom_at(f, e.x, e.y)

    def pan_start(self, e):
        s, ox, oy = self.view or getattr(self, "fit_view", (1, 0, 0)); self._pan = (e.x - ox, e.y - oy); self.canvas.focus_set()

    def pan_drag(self, e):
        if self._pan: s = (self.view or self.fit_view)[0]; self.view = (s, e.x - self._pan[0], e.y - self._pan[1]); self.draw()

    def pan_move(self, e):
        if self._pan is None:
            if self.hit(e): self._pan = False; return
            s, ox, oy = self.view or getattr(self, "fit_view", (1, 0, 0)); self._pan = (e.x - ox, e.y - oy)
        if self._pan:
            s = (self.view or self.fit_view)[0]; self.view = (s, e.x - self._pan[0], e.y - self._pan[1]); self.draw()

    # ---------------------------------------------------------------- hit testing
    def hit(self, e):
        """Returns tags (kind, a, b) of what is under the pointer, preferring small things (pins) over bodies."""
        c = self.canvas; best = None
        for item in reversed(c.find_overlapping(e.x - 4, e.y - 4, e.x + 4, e.y + 4)):
            for tg in c.gettags(item):
                p = tg.split(":")
                rank = {"pin": 0, "opin": 0, "indot": 0, "outdot": 0, "inpin": 1, "outpin": 1, "comp": 2, "wire": 3}.get(p[0]) if len(p) > 1 else None
                if rank is not None and (best is None or rank < best[0]): best = (rank, p)
        return best[1] if best else None

    def on_move(self, e):
        if self.tool: return self.tool_ghost(e)
        h = self.hit(e); self.canvas.configure(cursor="hand2" if h and h[0] in ("inpin", "pin", "wire", "opin", "indot", "outdot") else {"edit": "arrow", "wire": "pencil", "poke": "hand2"}[self.mode])

    def on_double(self, e):
        h = self.hit(e)
        if not h: return self.fit()
        if h[0] in ("comp", "pin") and self.doc.valid:
            comp = self.doc.circuit.component(h[1])
            if comp is not None and getattr(comp, "is_sub", False) and comp.inner() is not None: self.doc.switch(comp.attrs["circuit"])     # open the circuit inside (Logisim: double-click a subcircuit)
            elif comp is not None and comp.type_name == "RAM" and comp.id in self.doc.sim:
                from vibesimulation.workspaces.logisim.circuit.memory_editor import MemoryEditor
                dlg = MemoryEditor(self.ctx, f"RAM {comp.id}: contents now", dict(self.doc.sim[comp.id].get("mem", {})), comp.attrs["addr"], comp.attrs["width"]); dlg.wait_window()
                if dlg.result is not None: self.doc.set_memory(comp.id, dlg.result)
            elif comp is not None and any(a.kind == "map" for a in comp.attrs_spec): self.props(comp)        # ROM: open its contents

    def on_right(self, e):
        h = self.hit(e); self.canvas.focus_set()
        if self.tool: return self.set_tool(None)
        if not h: return self.menu_here(e)
        m = self.ctx.menu(); d = self.doc; c = d.circuit
        if h[0] in ("comp", "pin"):
            comp = c.component(h[1]); self.select(comp.id)
            m.add_command(label=f"{comp.type_name} {comp.id}", state="disabled")
            m.add_command(label="Turn clockwise  (R)", command=lambda: self.turn(1))
            m.add_command(label="Turn counter-clockwise  (L)", command=lambda: self.turn(-1))
            fm = self.ctx.menu()
            for f in ("east", "south", "west", "north"): fm.add_command(label=f.capitalize() + ("  ✓" if comp.facing == f else ""), command=lambda f=f: self.run(C.RotatePart(comp.id, facing=f)))
            m.add_cascade(label="Facing", menu=fm); m.add_separator()
            if comp.attrs_spec: m.add_command(label="Properties…", command=lambda: self.props(comp))
            if isinstance(comp, Gate):
                sub = self.ctx.menu()
                for name in sorted(k.type_name for k in R.by_category().get("Gates", []) if issubclass(k, Gate)):
                    sub.add_command(label=name, command=lambda n=name: self.run(C.ChangeGateType(comp.id, n)))
                m.add_cascade(label="Change gate type", menu=sub)
            for p in comp.out_ports():
                if p.optional and comp.outs.get(p.name) is None:
                    m.add_command(label=f"Use output {p.name}", command=lambda p=p: self.run(C.SetOutputSignal(comp.id, p.name, f"{comp.id}_{p.name}")))
            outs = [s for s in comp.outs.values() if s]
            if outs: m.add_command(label="Rename signal…", command=lambda: self.rename(outs[0]))
            if comp.pos: m.add_command(label="Put back in automatic place", command=lambda: self.run(C.ClearPositions(comp.id)))
            m.add_separator(); m.add_command(label="Delete part", command=lambda: self.run(C.DeleteComponent(comp.id)))
        elif h[0] == "wire":
            net = d.layout.wires[int(h[1])][4]
            m.add_command(label=f"Wire {net}", state="disabled")
            if net in c.wires: m.add_command(label="Put wire back in automatic route", command=lambda: self.run(C.SetWire(net, None)))
            m.add_command(label="Delete this piece of wire", command=lambda: (self.pick_wire(net, tuple(d.layout.wires[int(h[1])][:4])), self.delete_wires()))
            m.add_command(label="Drag: move a piece  ·  drag a corner  ·  Shift+drag: new bend", state="disabled")
        elif h[0] == "inpin":
            m.add_command(label="Rename…", command=lambda: self.rename(h[1]))
            m.add_command(label="Set width…", command=lambda: self.width(h[1]))
            m.add_command(label="Delete input", command=lambda: self.run(C.DeleteInput(h[1])))
        elif h[0] == "outpin":
            m.add_command(label="Rename…", command=lambda: self.rename(h[1]))
            m.add_command(label="Show a different signal…", command=lambda: self.pick_signal(e, lambda s: self.run(C.ChangeOutput(h[1], s))))
            m.add_command(label="Delete output", command=lambda: self.run(C.ChangeOutput(h[1], None)))
        m.tk_popup(e.x_root, e.y_root)

    # ---------------------------------------------------------------- building from empty space
    def menu_here(self, e):
        """Right-click on empty space: add something right there (Logisim: pick a tool, click the canvas)."""
        if not self.doc.valid and self.doc.circuit is not None:
            return self.run(C.AddInput())            # shows the "fix the JSON first" message
        at = (snap(self.lpos(e)[0]), snap(self.lpos(e)[1]))
        m = self.ctx.menu()
        m.add_command(label="Add input here", command=lambda: self.run(C.AddInput(pos=at)))
        m.add_command(label="Add output here", command=lambda: self.add_output(at))
        gm = self.ctx.menu()
        for name in ("AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"):
            gm.add_command(label=name, command=lambda n=name: self.run(C.AddComponent(n, pos=at)))
        m.add_cascade(label="Add gate here", menu=gm)
        others = [n for n in __import__("vibesimulation.workspaces.logisim.core.project", fromlist=["x"]).placeable()]
        if others:
            sm = self.ctx.menu()
            for n in others: sm.add_command(label=n, command=lambda n=n: self.run(C.AddComponent("Circuit", {"circuit": n}, pos=at)))
            m.add_cascade(label="Add circuit here", menu=sm)
        if getattr(self.ctx, "clipboard_parts", None): m.add_command(label="Paste here  (Ctrl+V)", command=lambda: self.paste(at))
        m.add_command(label="Add part here…", command=lambda: self.parts(at))
        m.add_separator(); m.add_command(label="Show the whole circuit", command=self.fit)
        m.tk_popup(e.x_root, e.y_root)

    # ---------------------------------------------------------------- tools (Logisim: pick a part in the explorer, then click where it goes)
    def set_tool(self, tool, label=""):
        self.tool = tool; self.canvas.delete("tip")
        self.canvas.configure(cursor="crosshair" if tool else "arrow")
        names = {None: "edit", ("in",): "in", ("out",): "out"}; cur = names.get(tool) or (tool[1] if tool[0] == "part" else None)
        for k, b in self.tool_btns.items():
            kind = "primary" if k == (cur or "none") else "secondary"
            if b.kind != kind: b.kind = kind; b.paint()
        if tool: self.status.configure(text=f"Click in the circuit to place {label or tool[-1]}  ·  Shift+click keeps the tool  ·  Esc or right-click cancels")
        else: self.draw()
        if self.main is not None and hasattr(self.main, "side") and self.main.side.view() is not None and hasattr(self.main.side.view(), "sync_tool"): self.main.side.view().sync_tool()
        self.canvas.focus_set()

    def place(self, e):
        if not self.doc.valid: return self.run(C.AddInput())
        at = (snap(self.lpos(e)[0]), snap(self.lpos(e)[1])); t = self.tool; keep = bool(getattr(e, "state", 0) & 1)
        self._freeze(); lay = self.doc.layout; pin = self._pin_all() if lay is not None else None
        if lay is not None:                                                        # a part dropped on top of another one is moved to the nearest free place
            at = self._free_spot(t, at)
            if at is None: return self.status.configure(text="There is no free place near there. Try an emptier spot.")
        def go(cmd):
            full = C.Batch([pin, cmd]) if pin is not None else cmd
            if self.doc.valid:
                cand = self.doc.circuit.copy(); full.apply(cand)
                if self._try(cand) is None: return self.status.configure(text="Not here: the wires could not be drawn around a part in that place. Try another spot.")
            self.run(full)
        if t[0] == "in": go(C.AddInput(pos=at))
        elif t[0] == "out": go(C.AddOutput(None, pos=at))
        elif t[0] == "circuit": go(C.AddComponent("Circuit", {"circuit": t[1]}, pos=at, wired=False))
        else: go(C.AddComponent(t[1], pos=at, wired=False))
        if not keep: self.set_tool(None)
        self.status.configure(text="Placed. Use the pins' dots to draw wires; Ctrl+Z undoes.")

    def _free_spot(self, t, at):
        """The grid point nearest to `at` where the tool's thing overlaps no part and no pin (None when there is none close by)."""
        from vibesimulation.workspaces.logisim.components.registry import ComponentRegistry as Reg
        if t[0] in ("in", "out"):
            from vibesimulation.workspaces.logisim.core.model import IOPin
            pin = IOPin("X", 1); rect = lambda x, y: self._pin_rect(t[0], pin, x, y)
        else:
            try: comp = Reg.create("Circuit" if t[0] == "circuit" else t[1], "tmp", {"circuit": t[1]} if t[0] == "circuit" else {})
            except Exception: return at
            rect = lambda x, y: self._rect(comp, x, y)
        if not self._hits(rect(*at), None): return at
        offs = sorted(((dx, dy) for dx in range(-300, 301, 10) for dy in range(-200, 201, 10)), key=lambda o: o[0] * o[0] + o[1] * o[1])
        for dx, dy in offs:
            if not self._hits(rect(at[0] + dx, at[1] + dy), None): return (at[0] + dx, at[1] + dy)
        return None

    def tool_ghost(self, e):
        c = self.canvas; c.delete("tip")
        if self.tool is None: return
        x, y = e.x, e.y; c.create_rectangle(x - 22, y - 16, x + 22, y + 16, outline=self.ctx.P["accent"], dash=(3, 3), width=2, tags="tip")
        c.create_text(x, y + 28, text={"in": "Input pin", "out": "Output pin"}.get(self.tool[0], self.tool[-1]), fill=self.ctx.P["accent"], font=self.ctx.f_small, tags="tip")

    def select(self, cid):
        self.sel = cid; self.sels = {cid} if cid else set(); self.wsel = set(); self.psel = set(); self.draw()

    def toggle(self, cid):
        self.sels ^= {cid}; self.sel = next(iter(self.sels)) if len(self.sels) == 1 else None; self.draw()

    def select_all(self):
        if self.doc.valid and self.doc.layout is not None:
            lay = self.doc.layout
            self.sels = {c.id for c in self.doc.circuit.components}; self.sel = next(iter(self.sels)) if len(self.sels) == 1 else None
            self.psel = {("in", p.name) for p, _, _ in lay.inputs} | {("out", p.name) for p, _, _ in lay.outputs}
            self.wsel = {(w[4], tuple(w[:4])) for w in lay.wires}; self.draw()
            self.status.configure(text=f"{len(self.sels)} part(s), {len(self.psel)} pin(s) and {len(self.wsel)} wire piece(s) selected")

    # ---------------------------------------------------------------- copy / cut / paste (Logisim: Edit menu)
    def copy(self):
        if not self.doc.valid or not self.sels: return False
        lay = self.doc.layout
        pls = {p.comp.id: p for p in lay.parts if p.comp.id in self.sels}
        parts = [pls[c.id].comp.to_dict() for c in self.doc.circuit.components if c.id in pls]
        for d in parts: d.pop("pos", None)
        self.ctx.clipboard_parts = {"parts": parts, "places": {i: (p.x, p.y) for i, p in pls.items()}, "facings": {i: p.comp.facing for i, p in pls.items()}, "n": 0}
        self.status.configure(text=f"Copied {len(parts)} part(s). Ctrl+V pastes them (right-click empty space: Paste here)."); return True

    def cut(self):
        if self.copy(): self.delete_selected()

    def paste(self, at=None):
        clip = getattr(self.ctx, "clipboard_parts", None)
        if not clip or not self.doc.valid: return
        clip["n"] += 1; lay = self.doc.layout
        xs = [p[0] for p in clip["places"].values()]; ys = [p[1] for p in clip["places"].values()]
        if at: dx, dy = snap(at[0] - min(xs)), snap(at[1] - min(ys))
        else: dx = dy = 30 * clip["n"]
        self.run(C.PasteParts(clip["parts"], clip["places"], clip["facings"], dx, dy))
        new = self.doc.circuit.components[-len(clip["parts"]):] if self.doc.valid else []
        self.sels = {c.id for c in new}; self.sel = next(iter(self.sels)) if len(self.sels) == 1 else None; self.draw()

    def turn(self, steps):
        if self.sel and self.doc.valid: self.run(C.RotatePart(self.sel, steps))

    def delete_selected(self):
        if not self.doc.valid: return
        if self.psel or (self.wsel and (self.sels or len(self.wsel) > 1)):          # a mixed selection: parts, pins and wire pieces go together
            cmds = []; ids = list(self.sels)
            if ids: cmds.append(C.DeleteMany(ids))
            for kind, name in sorted(self.psel):
                cmds.append(C.DeleteInput(name) if kind == "in" else C.ChangeOutput(name, None))
            self.sel, self.sels, self.psel, self.wsel = None, set(), set(), set()
            return self.run(C.Batch(cmds)) if cmds else None
        if self.wsel: return self.delete_wires()
        if len(self.sels) > 1 and self.doc.valid:
            ids, self.sel, self.sels = list(self.sels), None, set(); self.run(C.DeleteMany(ids))
        elif self.sel and self.doc.valid:
            cid, self.sel, self.sels = self.sel, None, set(); self.run(C.DeleteComponent(cid))

    # ---------------------------------------------------------------- actions
    def run(self, cmd):
        if not self.doc.valid:
            self.ctx.say("Circuit", "The JSON has a problem right now. Fix it in the JSON box first (the circuit shows the last good version)."); return
        try: self.doc.run(cmd)
        except Exception as ex: self.ctx.say("Could not do that", str(ex))

    def signals(self):
        c = self.doc.circuit; return c.signals()

    def pick_signal(self, e, fn, width=None, extra=None):
        m = self.ctx.menu()
        for s, w in self.signals().items():
            if width is None or w == width: m.add_command(label=f"{s}  ({w} bit{'s' if w > 1 else ''})", command=lambda s=s: fn(s))
        for label, f in (extra or []): m.add_separator(); m.add_command(label=label, command=f)
        m.tk_popup(e.x_root, e.y_root)

    def signal_menu(self, e, cid, port):
        comp = self.doc.circuit.component(cid); p = comp.port(port)
        extra = [("Disconnect this pin", lambda: self.run(C.Rewire(cid, port, None)))] if p.optional else None
        self.pick_signal(e, lambda s: self.run(C.Rewire(cid, port, s)), p.width, extra)

    def rename(self, old):
        new = self.ctx.ask_string("Rename signal", f"New name for '{old}':", old)
        if new and new.strip() and new != old: self.run(C.RenameSignal(old, new.strip()))

    def width(self, name):
        v = self.ctx.ask_string("Input width", f"Number of bits for '{name}' (1-64):", "1")
        if v:
            try: self.run(C.SetInputWidth(name, int(v)))
            except ValueError: self.ctx.say("Input width", "Please type a whole number.")

    def props(self, comp):
        dlg = PropsDialog(self.ctx, comp); dlg.wait_window()
        if dlg.result: self.run(C.SetAttrs(comp.id, dlg.result))

    def add_output(self, at=None):
        """A loose output pin; draw a wire to it (or drop a wire on it) to show a signal."""
        if not self.doc.valid: return self.run(C.AddOutput(None))
        self._freeze(); self.run(C.Batch([self._pin_all(), C.AddOutput(None, pos=at)]))

    def add_gate(self):
        self.run(C.AddComponent("AND"))

    def parts(self, at=None):
        dlg = PaletteDialog(self.ctx); dlg.wait_window()
        r = dlg.result
        if not r: return
        if r[0] == "part":
            self.run(C.AddComponent(r[1], r[2], pos=at))
        else:
            piece, replace = r[1], r[2]
            if replace or not self.doc.valid: self.doc.set_circuit(piece); self.doc.set_inputs({})
            else: self.doc.set_circuit(merge(self.doc.circuit.copy(), piece))

    def download(self):
        if self.main is not None and hasattr(self.main, "actions"): return self.main.actions.circ()
        d = self.doc
        if not d.valid: self.ctx.say("Download", "There is no valid circuit to export yet."); return
        p = self.ctx.choose_file("save", "Save Logisim circuit", [".circ"], "circuit.circ")
        if not p: return
        if not p.lower().endswith(".circ"): p += ".circ"
        try:
            with open(p, "w", encoding="utf-8") as f: f.write(d.circ_text())
            self.status.config(text=f"Saved {p}  -  open it with Logisim-evolution (File > Open).")
        except Exception as ex: self.ctx.say("Download", str(ex))
