"""Multisim box 1: the schematic. Drag parts to move them, right-click to edit, PDF / .cir download icons."""
import tkinter as tk
from tkinter import ttk

from ...analog import components as AC
from ...analog.layout import SchematicBuilder, pin_xy
from ...analog.painter import paint_schematic
from ...analog.solver import is_ground
from ...analog.units import fmt_si
from ...core.render import BAD, LABEL, MUTED, OUTLINE
from ..canvas_renderer import TkRenderer
from ..views.base import View
from ..widgets import Btn

class SchematicView(View):
    number, title, hint = None, "Schematic", "drag parts and wires; right-click to edit"

    def build(self):
        ctx = self.ctx; self.main = None
        self.b_redo = Btn(ctx, self.tools, "↷", lambda: self.main.redo(), "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Redo (Ctrl+Y)")
        self.b_undo = Btn(ctx, self.tools, "↶", lambda: self.main.undo(), "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Undo (Ctrl+Z)")
        self.b_redo.pack(side="right"); self.b_undo.pack(side="right")
        Btn(ctx, self.tools, "⬇", lambda: self.main.actions_for("multisim").cir(), "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Download .cir (SPICE netlist, import it in Multisim)").pack(side="right", before=self.b_redo)
        Btn(ctx, self.tools, "PDF", lambda: self.main.actions_for("multisim").pdf(), "ghost", padx=8, pady=0, font=ctx.f_small).tip("Download PDF (schematic + DC results)").pack(side="right", before=self.b_redo)
        b = self.body; b.rowconfigure(0, weight=1)
        self.group_btns = {}                                                      # the component database is in the side bar and the Place menu
        self.canvas = tk.Canvas(b, highlightthickness=0, bd=0); self.canvas.grid(row=0, column=0, sticky="nsew")
        self.status = tk.Label(b, text="", font=ctx.f_small, anchor="w", width=1); self.status.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.canvas.bind("<Configure>", lambda e: self.draw()); self._drag = None; self.L = None; self.sc = (1, 0, 0)
        self.canvas.bind("<Button-1>", self.press); self.canvas.bind("<B1-Motion>", self.motion); self.canvas.bind("<ButtonRelease-1>", self.release)
        self.sel, self.wsel = None, set()
        for key in ("<Key-Delete>", "<Key-BackSpace>"): self.canvas.bind(key, lambda e: self.delete_selected())
        self.canvas.bind("<Key-Escape>", lambda e: self.clear_selection())
        for ev in ("<Button-3>", "<Button-2>", "<Control-Button-1>", "<Double-Button-1>"): self.canvas.bind(ev, self.on_right)
        ctx.themed.append(self._paint); self._paint()

    def _paint(self):
        P = self.ctx.P; self.status.configure(bg=P["card"], fg=P["muted"]); self.canvas.configure(bg=P["canvas"]); self.draw()

    def on_doc(self, kind):
        if kind == "changed": self.b_undo.set_enabled(self.doc.can_undo()); self.b_redo.set_enabled(self.doc.can_redo())
        self.draw()

    # ---- drawing: wired ladder schematic (analog/layout.py)
    def draw(self, ctx_unused=None):
        c, d, P = self.canvas, self.doc, self.ctx.P; c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 20 or H < 20: return
        if d.netlist is None or not d.netlist.parts or d.errors:
            c.create_text(W / 2, H / 2, text="No circuit yet.\n\n" + "\n".join(d.errors[:3]), fill=P["muted"], font=self.ctx.f_body, justify="center", width=W - 40); return
        L = SchematicBuilder().build(d.netlist); x0, y0, x1, y1 = L.extent()
        s = min((W - 24) / (x1 - x0), (H - 24) / (y1 - y0), 1.6); ox = (W - (x1 - x0) * s) / 2 - x0 * s; oy = (H - (y1 - y0) * s) / 2 - y0 * s
        self.L, self.sc = L, (s, ox, oy)
        r = TkRenderer(c, P, self.ctx.sans, s, ox, oy); dg = int(self.ctx.cfg.get("digits", 4))
        paint_schematic(r, L, d.volts if d.valid else None, dg, results=d.results if d.valid else None)
        self._overlay(r)
        self.status.config(text=(f"⚠ Incomplete: {len(d.netlist.floating())} terminal(s) not connected (red rings). Drag from a terminal to another terminal or wire." if d.netlist.floating() else "Click a part or a wire to select it, Delete removes it. Drag from a terminal to wire it to another terminal or wire; right-click a part to edit it.") if d.valid else (d.layout_error or ""))

    def _overlay(self, r):
        c, P = self.canvas, self.ctx.P; s, ox, oy = self.sc
        pl = next((q for q in self.L.parts if q.part.id == self.sel), None)
        if self.sel and pl is None: self.sel = None
        if pl is not None:
            hw, hh = self._half(pl); c.create_rectangle(ox + (pl.cx - hw) * s, oy + (pl.cy - hh) * s, ox + (pl.cx + hw) * s, oy + (pl.cy + hh) * s, outline=P["accent"], dash=(4, 3), width=2, tags="sel")
        from ...layout.routing import norm
        fl = {(p.id, k) for p, k in self.doc.netlist.floating()}
        for q in self.L.parts:                                                    # unconnected terminals: red ring (the circuit is not complete)
            for k in range(q.part.nterm):
                if (q.part.id, k) in fl:
                    px, py = pin_xy(q, k); c.create_oval(ox + px * s - 7, oy + py * s - 7, ox + px * s + 7, oy + py * s + 7, outline=P["bad"], width=2, tags="sel")
        have = {(norm(w[:2], w[2:4]), w[4]) for w in self.L.wires}
        for piece, net in list(self.wsel):
            if (piece, net) not in have: self.wsel.discard((piece, net)); continue
            a, b, e2, f2 = piece
            c.create_line(ox + a * s, oy + b * s, ox + e2 * s, oy + f2 * s, fill=P["accent"], width=max(4, 4 * s), capstyle="round", tags="sel")
            for qx, qy in ((a, b), (e2, f2)): c.create_rectangle(ox + qx * s - 4, oy + qy * s - 4, ox + qx * s + 4, oy + qy * s + 4, fill=P["accent"], outline="", tags="sel")

    def clear_selection(self):
        if self.sel or self.wsel: self.sel, self.wsel = None, set(); self.draw()

    def select_part(self, cid):
        self.sel, self.wsel = cid, set(); self.draw()
        self.status.config(text=f"{cid} selected: Delete removes it, drag it to move it, right-click to edit")

    def pick_wire(self, k, add=False):
        from ...layout.routing import norm
        w = self.L.wires[k]; key = (norm(w[:2], w[2:4]), w[4])
        self.sel = None
        if add: self.wsel ^= {key}
        else: self.wsel = {key}
        self.draw(); self.status.config(text="Wire selected: Delete removes it (the terminals it joined are left unplugged), drag it to move it")

    # ---- mouse editing: drag parts, wire pieces, wire corners (Shift+drag a wire adds a bend); drag from one terminal to another joins their nets
    def _tag(self, e, prefix):
        for item in reversed(self.canvas.find_overlapping(e.x - 4, e.y - 4, e.x + 4, e.y + 4)):
            for tg in self.canvas.gettags(item):
                if tg.startswith(prefix): return tg[len(prefix):]
        return None

    def hit_wire(self, e):
        k = self._tag(e, "wire:"); return None if k is None else int(k)

    def lpos(self, e):
        s, ox, oy = self.sc; return (e.x - ox) / s, (e.y - oy) / s

    def press(self, e):
        from ...layout.routing import norm, on_seg
        from ...layout.wire_edit import snap10
        self._drag = None; self.canvas.focus_set()
        if self.L is None or not self.doc.valid: return
        g = {"x": e.x, "y": e.y, "on": False, "dx": 0, "dy": 0, "ok": True}
        t = self._tag(e, "term:")
        if t:
            pid, k = t.rsplit(":", 1); g.update(kind="conn", pid=pid, k=int(k)); self._drag = g; return
        cid = self.hit(e)
        if cid:
            if self.sel != cid or self.wsel: self.select_part(cid)                 # redraws, so take the part from the new picture
            pl = next((q for q in self.L.parts if q.part.id == cid), None)
            if pl: g.update(kind="part", id=cid, pl=pl); self._drag = g
            return
        k = self.hit_wire(e)
        if k is None:
            self.clear_selection(); return
        w = self.L.wires[k]; was = (norm(w[:2], w[2:4]), w[4]) in self.wsel
        self.pick_wire(k, bool(getattr(e, "state", 0) & 4))
        lx, ly = self.lpos(e); ports = {(x, y) for x, y, _ in self.L.terminals()}
        ends = [(w[0], w[1]), (w[2], w[3])]; near = min(ends, key=lambda p: abs(p[0] - lx) + abs(p[1] - ly))
        g.update(wire=k, net=w[4])
        if abs(near[0] - lx) + abs(near[1] - ly) <= 14 and near not in ports: g.update(kind="vertex", V=near)
        elif getattr(e, "state", 0) & 1:
            Q = (snap10(lx), snap10(ly)); wn = (min(w[0], w[2]), min(w[1], w[3]), max(w[0], w[2]), max(w[1], w[3]))
            if on_seg(wn, Q) and Q not in ends: g.update(kind="vertex", V=Q, split=Q)
            else: g.update(kind="wire")
        elif not was:                                                                 # a wire that was not selected: pulling from its middle draws a new wire from that point
            nw = norm(w[:2], w[2:4])
            Q = (min(max(snap10(lx), nw[0]), nw[2]), nw[1]) if nw[1] == nw[3] else (nw[0], min(max(snap10(ly), nw[1]), nw[3]))
            g.update(kind="branch", Q=Q)
        else: g.update(kind="wire")
        self._drag = g

    def motion(self, e):
        g = self._drag
        if not g: return
        if not g["on"]:
            if abs(e.x - g["x"]) + abs(e.y - g["y"]) < 6: return
            g["on"] = True; self.canvas.configure(cursor="fleur"); self._start(g)
        getattr(self, "_move_" + g["kind"])(e, g)

    def _start(self, g):
        from ...layout.routing import norm
        from ...layout.wire_edit import split_at
        if g["kind"] in ("wire", "vertex"):
            idx = [j for j, t in enumerate(self.L.wires) if t[4] == g["net"]]
            pieces = [norm(self.L.wires[j][:2], self.L.wires[j][2:4]) for j in idx]
            if g.get("split"): pieces = split_at(pieces, g["split"])
            g["pieces"], g["i"], g["ports"] = pieces, idx.index(g["wire"]), {(x, y) for x, y, _ in self.L.terminals()}

    def _lines(self, pieces):
        s, ox, oy = self.sc
        for t in pieces: self.canvas.create_line(ox + t[0] * s, oy + t[1] * s, ox + t[2] * s, oy + t[3] * s, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")

    def _move_wire(self, e, g):
        from ...layout.wire_edit import move_segment, snap10
        s = self.sc[0]; dx = snap10((e.x - g["x"]) / s); dy = snap10((e.y - g["y"]) / s)
        if (dx, dy) == (g["dx"], g["dy"]): return
        g["dx"], g["dy"] = dx, dy; self.canvas.delete("ghost"); g["new"] = move_segment(g["pieces"], g["i"], dx, dy, g["ports"])
        if g["new"] is None: return
        self._lines(g["new"]); self.status.config(text="Release to put the wire here")

    def _move_vertex(self, e, g):
        from ...layout.wire_edit import move_vertex, snap10
        lx, ly = self.lpos(e); V2 = (snap10(lx), snap10(ly))
        if V2 == g.get("V2"): return
        g["V2"] = V2; self.canvas.delete("ghost")
        g["new"] = None if V2 in g["ports"] else move_vertex(g["pieces"], g["V"], V2, g["ports"])
        if g["new"] is None: self.status.config(text="A wire end cannot sit on a part terminal."); return
        self._lines(g["new"]); self.status.config(text="Release to move the corner here")

    def _move_conn(self, e, g):
        s, ox, oy = self.sc; pl = next(q for q in self.L.parts if q.part.id == g["pid"])
        px, py = pin_xy(pl, g["k"])
        self.canvas.delete("ghost")
        self.canvas.create_line(ox + px * s, oy + py * s, e.x, e.y, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")
        self.status.config(text="Drop on another terminal or a wire to connect this terminal to that net; drop on empty space to unplug it")

    def _move_branch(self, e, g):
        s, ox, oy = self.sc; qx, qy = g["Q"]; self.canvas.delete("ghost")
        self.canvas.create_line(ox + qx * s, oy + qy * s, e.x, e.y, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")
        self.status.config(text="Drop on a terminal or another wire to connect them; drop on empty space to leave the wire end there")

    def _target_net(self, e):
        """The net under the pointer: a terminal's or a wire's (None on empty space)."""
        from ...analog.layout import canon
        nl = self.doc.netlist; t = self._tag(e, "term:"); wk = self.hit_wire(e)
        if t: tp, tk = t.rsplit(":", 1); return canon(nl.part(tp).nodes[int(tk)]), (tp, int(tk))
        if wk is not None: return canon(self.L.wires[wk][4]), None
        return None, None

    def _drop_branch(self, e, g):
        from ...analog.layout import canon
        net = canon(g["net"]); target, _ = self._target_net(e)
        if target is None: return self._stub(g["net"], g["Q"], e)
        if target == net: return self.draw()
        if self.edit_checked(lambda n: (n.merge_nets(net, target), n.tidy_floating())): self.status.config(text=f"Nets {net} and {target} are now one net (Ctrl+Z undoes).")

    def _stub(self, net, Q, e, base=None):
        """Leave the end of a wire where it was dropped: the net's route gets a new piece from Q to the pointer."""
        from ...layout.routing import norm
        from ...layout.wire_edit import snap10, tidy
        lx, ly = self.lpos(e); P = (snap10(lx), snap10(ly))
        if P == Q: return self.draw()
        pieces = base if base is not None else [norm(w[:2], w[2:4]) for w in self.L.wires if w[4] == net]
        bend = (P[0], Q[1]); new = [norm(Q, bend), norm(bend, P)]
        route = [list(t) for t in tidy(pieces + [t for t in new if t[:2] != t[2:]])]
        self._commit_route(net, route, "The wire end cannot go there (it would touch another net or a part).")

    def _move_part(self, e, g):
        c = self.canvas; s, ox, oy = self.sc
        dx = round((e.x - g["x"]) / s / 10) * 10; dy = round((e.y - g["y"]) / s / 10) * 10
        if (dx, dy) == (g["dx"], g["dy"]): return
        c.move("comp:" + g["id"], (dx - g["dx"]) * s, (dy - g["dy"]) * s)
        for k in range(g["pl"].part.nterm):
            for i in c.find_withtag(f"term:{g['id']}:{k}"): c.move(i, (dx - g["dx"]) * s, (dy - g["dy"]) * s)
        g["dx"], g["dy"] = dx, dy
        pl = g["pl"]; hw, hh = self._half(pl)
        g["ok"] = not any(abs(q.cx - pl.cx - dx) < hw + self._half(q)[0] and abs(q.cy - pl.cy - dy) < hh + self._half(q)[1] for q in self.L.parts if q is not pl)
        c.delete("ghost")
        c.create_rectangle(ox + (pl.cx + dx - hw) * s, oy + (pl.cy + dy - hh) * s, ox + (pl.cx + dx + hw) * s, oy + (pl.cy + dy + hh) * s,
                           outline=self.ctx.P["accent"] if g["ok"] else self.ctx.P["bad"], dash=(4, 3), width=2, tags="ghost")
        self.status.config(text="Release to drop the part here" if g["ok"] else "Not here: it would overlap another part")

    @staticmethod
    def _half(pl): return (36, 50) if pl.vertical else ((55, 65) if pl.part.nterm != 2 else (50, 36))       # half width / height of a part with its labels' room

    def release(self, e):
        g, self._drag = self._drag, None
        if not g: return
        self.canvas.configure(cursor="arrow"); self.canvas.delete("ghost")
        if not g["on"]:
            if g["kind"] == "part": self.toggle_switch(g["id"])
            return
        getattr(self, "_drop_" + g["kind"])(e, g)

    def _refuse(self, text): self.draw(); self.status.config(text=text)

    def _commit_route(self, net, route, text):
        try:
            nl = self.doc.netlist.copy(); nl.wires[net] = route; ok = net in SchematicBuilder().build(nl).fixed
        except Exception: ok = False
        if not ok: return self._refuse(text)
        self.edit(lambda n: n.wires.__setitem__(net, route))

    def _drop_wire(self, e, g):
        from ...layout.wire_edit import tidy
        if not g.get("new"): return self.draw()
        self._commit_route(g["net"], [list(t) for t in tidy(g["new"])], "The wire cannot go there (it would touch another net or a part), so it stayed where it was.")

    def _drop_vertex(self, e, g):
        from ...layout.wire_edit import tidy
        if not g.get("new") or g.get("V2") == g["V"]: return self.draw()
        self._commit_route(g["net"], [list(t) for t in tidy(g["new"])], "The corner cannot go there (the wire would touch another net or a part), so it stayed where it was.")

    def delete_piece(self, k):
        """Delete one piece of wire if the net's terminals stay connected without it."""
        from ...layout.routing import norm
        from ...layout.wire_edit import tidy
        w = self.L.wires[k]; net = w[4]
        pieces = [norm(t[:2], t[2:4]) for t in self.L.wires if t[4] == net]; pieces.remove(norm(w[:2], w[2:4]))
        if not pieces: return self._refuse(f"This is the only piece of wire of {net}. Use 'Put wire back in automatic route' instead.")
        self._commit_route(net, [list(t) for t in tidy(pieces)], f"This piece is needed to connect the terminals of {net}, so it was not deleted.")

    def _drop_conn(self, e, g):
        """The dragged terminal leaves its net and joins the net it is dropped on (another terminal or a wire); on empty space it is left unplugged."""
        from ...analog.layout import canon
        nl = self.doc.netlist; pid, k = g["pid"], g["k"]; cur = canon(nl.part(pid).nodes[k]); t = self._tag(e, "term:"); wk = self.hit_wire(e)
        if t:
            tp, tk = t.rsplit(":", 1)
            if tp == pid and int(tk) == k: return self.draw()
            target = canon(nl.part(tp).nodes[int(tk)])
        elif wk is not None: target = canon(self.L.wires[wk][4])
        else: target = None
        if target is None:
            pin = pin_xy(next(q for q in self.L.parts if q.part.id == pid), k)
            if cur.startswith("~"): return self._stub(cur, pin, e)
            from ...layout.routing import norm
            from ...layout.wire_edit import move_vertex, snap10, tidy
            lx, ly = self.lpos(e); P = (snap10(lx), snap10(ly)); pieces = [norm(w[:2], w[2:4]) for w in self.L.wires if w[4] == cur]
            route = [list(t) for t in tidy(move_vertex(pieces, pin, P))] if pieces and P != pin else None
            def go(n):
                n.part(pid).nodes[k] = f"~{pid}.{k + 1}"
                if route: n.wires[cur] = route
                n.tidy_floating()
            msg = f"Terminal {k + 1} of {pid} is unplugged, the wire end stays where you dropped it (Ctrl+Z puts it back)."
        else:
            if target == cur: return self.draw()
            go, msg = (lambda n: (n.part(pid).nodes.__setitem__(k, target), n.tidy_floating())), f"Terminal {k + 1} of {pid} is now on net {target}."
        if self.edit_checked(go): self.status.config(text=msg)

    def edit_checked(self, fn):
        """Like edit(), but a change that would make the circuit invalid is refused (nothing changes) and the reason is shown."""
        try:
            nl = self.doc.netlist.copy(); fn(nl); errs = nl.validate()
        except Exception as ex: errs = [str(ex)]
        if errs: self._refuse("Not done: " + errs[0]); return False
        self.edit(fn); return True

    def delete_selected(self):
        if not self.doc.valid or self.doc.netlist is None: return
        if self.wsel: return self.delete_wires()
        if self.sel:
            cid = self.sel; self.sel = None
            if self.edit_checked(lambda nl: (nl.parts.remove(nl.part(cid)), nl.tidy_floating())): self.status.config(text=f"{cid} deleted (Ctrl+Z brings it back); the terminals it joined are left unplugged")

    def delete_wires(self):
        """Delete the selected pieces of wire: the part of the net that has the most terminals stays, the terminals that were only reachable through the deleted pieces are unplugged."""
        from ...analog.layout import canon
        from ...layout.routing import norm, on_seg
        from ...layout.wire_edit import reach, tidy
        L = self.L; by = {}
        for piece, net in self.wsel: by.setdefault(net, set()).add(piece)
        plan = {}
        for net, gone in by.items():
            segs = [norm(t[:2], t[2:4]) for t in L.wires if t[4] == net]; left = [s for s in segs if s not in gone]
            terms = [(pl.part.id, kk, pin_xy(pl, kk)) for pl in L.parts for kk in range(pl.part.nterm) if canon(pl.part.nodes[kk]) == net]
            comps, rest = [], set(range(len(left)))
            while rest:
                i = min(rest); a = left[i]; grp = reach(left, [(a[0], a[1]), (a[2], a[3])]) | {i}; comps.append(grp); rest -= grp
            def score(grp): return sum(1 for _, _, p in terms if any(on_seg(left[i], p) for i in grp))
            keep = max(comps, key=score) if comps else set()
            kept = [left[i] for i in sorted(keep)]
            plan[net] = ([list(t) for t in tidy(kept)] if kept else None, [(pid, kk) for pid, kk, p in terms if not any(on_seg(s2, p) for s2 in kept)])
        def go(nl, keep_routes=True):
            for net, (route, unplug) in plan.items():
                for pid, kk in unplug: nl.part(pid).nodes[kk] = f"~{pid}.{kk + 1}"
                if route and keep_routes: nl.wires[net] = route
                else: nl.wires.pop(net, None)
            nl.tidy_floating()
        try:
            nl = self.doc.netlist.copy(); go(nl); ok = all(net in SchematicBuilder().build(nl).fixed for net, (r, u) in plan.items() if r and net in nl.wires)
        except Exception: ok = False
        n = sum(len(u) for r, u in plan.values()); self.wsel = set()
        if self.edit_checked(go if ok else (lambda nl: go(nl, False))):
            self.status.config(text=(f"Wire deleted: {n} terminal(s) unplugged" if n else "Wire piece deleted") + "  (Ctrl+Z undoes)")

    def _drop_part(self, e, g):
        if (g["dx"], g["dy"]) == (0, 0): return self.draw()
        if not g["ok"]: return self._refuse("That spot overlaps another part, so the part stayed where it was.")
        cid = g["id"]; old = self.doc.netlist.part(cid).pos or (0, 0); new = (old[0] + g["dx"], old[1] + g["dy"])
        pl, dx, dy = g["pl"], g["dx"], g["dy"]
        from ...analog.layout import canon
        from ...layout.wire_edit import stretch_end
        if pl.part.nterm == 2:
            d0 = {0: (-60, 0), 90: (0, -60), 180: (60, 0), 270: (0, 60)}[pl.angle]
            pins = [((pl.cx + d0[0], pl.cy + d0[1]), canon(pl.part.nodes[0])), ((pl.cx - d0[0], pl.cy - d0[1]), canon(pl.part.nodes[1]))]
        else: pins = []
        def go(nl):
            nl.part(cid).pos = new
            for (x, y), net in pins:                                   # hand-drawn routes on this part's pins stretch along
                if net in nl.wires:
                    nl.wires[net] = [list(t) for t in stretch_end([tuple(t) for t in nl.wires[net]], (x, y), (x + dx, y + dy), pl.vertical)]
        self.edit(go)

    # ---- editing
    def hit(self, e):
        for item in reversed(self.canvas.find_overlapping(e.x - 3, e.y - 3, e.x + 3, e.y + 3)):
            for tg in self.canvas.gettags(item):
                if tg.startswith("comp:"): return tg[5:]
        return None

    def edit(self, fn):
        try: self.doc.edit(fn)
        except Exception as ex: self.ctx.say("Could not do that", str(ex))

    def group_menu(self, group, btn):
        from .parts_bin import fill_group_menu
        if self.doc.netlist is None: self.main.actions_for("multisim").new()
        m = self.ctx.menu(); fill_group_menu(m, self.ctx, group, self.place)
        m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def place(self, cls): self.add(cls)

    def tidy(self): self.edit(lambda nl: ([setattr(p, "pos", None) for p in nl.parts], nl.wires.clear()))

    def add_menu(self):
        if self.doc.netlist is None: self.main.actions_for("multisim").new()
        m = self.ctx.menu()
        groups = [("Passive", (AC.Resistor, AC.Potentiometer, AC.Capacitor, AC.Inductor, AC.Transformer)), ("Sources", (AC.VoltageSource, AC.CurrentSource)),
                  ("Diodes", (AC.Diode, AC.Zener, AC.LED)), ("Transistors", (AC.NPN, AC.PNP, AC.NMOS, AC.PMOS, AC.NJFET, AC.PJFET, AC.IGBT)), ("Amplifier", (AC.OpAmp,)),
                  ("Controlled sources", (AC.VCVS, AC.VCCS, AC.CCVS, AC.CCCS)), ("Switch, meters", (AC.Switch, AC.Ammeter, AC.Voltmeter))]
        for gi, (gname, classes) in enumerate(groups):
            if gi: m.add_separator()
            for cls in classes: m.add_command(label=cls.type_name, command=lambda c=cls: self.add(c))
        m.tk_popup(self.canvas.winfo_rootx() + 10, self.canvas.winfo_rooty() + 4)

    def add(self, cls):
        def go(nl):
            pre = cls.idp or cls.letter; n = 1
            while nl.part(f"{pre}{n}"): n += 1
            used = nl.nets(); k = 1
            while f"n{k}" in used: k += 1
            fixed = {str(p.nodes[0]).strip() for p in nl.parts if p.branch and not p.nodes[0] in ("0",)}
            free = [u for u in used if u not in fixed] or used
            if cls is AC.OpAmp: nodes = ["0", "0", (free or used)[-1] if used else f"n{k}"]                         # output on the last free net (an output on ground would be a source across ground)
            elif cls.nterm != 2: nodes = [(free or used)[-1] if used else f"n{k}"] + ["0"] * (cls.nterm - 1)      # first terminal on the last free net, the others on ground: drag terminals to rewire
            elif cls.letter == "I" and used: nodes = ["0", used[-1]]
            elif cls.letter in "RCLDSEGHFV" or cls in (AC.Ammeter, AC.Voltmeter): nodes = [(free or used)[-1], "0"] if used else [f"n{k}", "0"]   # goes in parallel with the last free net: stays wired
            else: nodes = [f"n{k}", "0"]                                                           # a new source starts its own net; wire parts to it
            extra = {}
            if issubclass(cls, AC.Dependent):
                if cls.current_controlled:
                    src = next((q.id for q in nl.parts if q.branch and q.type_name in ("VoltageSource", "Ammeter")), None)
                    extra["control"] = src or "V1"
                else: extra["control"] = [used[0] if used else "n1", "0"]
            nl.parts.append(cls(f"{pre}{n}", nodes, cls.default, **extra))
        self.edit(go)

    def toggle_switch(self, cid):
        nl = self.doc.netlist; p = nl.part(cid) if nl else None
        if isinstance(p, AC.Switch): self.edit(lambda n: n.part(cid).extra.__setitem__("state", "open" if p.is_closed() else "closed"))

    def on_right(self, e):
        cid = self.hit(e)
        if not cid and self.doc.netlist is not None and self.L is not None:
            k = self.hit_wire(e)
            if k is not None:
                net = self.L.wires[k][4]; m = self.ctx.menu(); m.add_command(label=f"Wire {net}", state="disabled")
                m.add_command(label="Delete this piece of wire", command=lambda: (self.pick_wire(k), self.delete_wires()))
                if net in self.doc.netlist.wires: m.add_command(label="Put wire back in automatic route", command=lambda: self.edit(lambda nl: nl.wires.pop(net, None)))
                else: m.add_command(label="Drag: move a piece  ·  drag a corner  ·  Shift+drag: new bend", state="disabled")
                m.tk_popup(e.x_root, e.y_root)
            return
        if not cid or self.doc.netlist is None: return
        p = self.doc.netlist.part(cid); m = self.ctx.menu()
        m.add_command(label=f"{p.type_name} {p.id}", state="disabled")
        if p.default is not None: m.add_command(label="Edit value…", command=lambda: self.value(p))
        if isinstance(p, AC.Waveform): m.add_command(label="Edit source (DC, AC, frequency, wave)…", command=lambda: self.source(p))
        if isinstance(p, AC.Switch): m.add_command(label="Open / close the switch (or just click it)", command=lambda: self.toggle_switch(cid))
        if p.extras and not isinstance(p, (AC.Switch, AC.Waveform)): m.add_command(label="Edit settings…", command=lambda: self.settings(p))
        m.add_command(label="Change connections…", command=lambda: self.nodes(p))
        m.add_command(label="Rename…", command=lambda: self.rename(p))
        if p.pos: m.add_command(label="Put back in automatic place", command=lambda: self.edit(lambda nl: setattr(nl.part(cid), "pos", None)))
        m.add_separator(); m.add_command(label="Delete part", command=lambda: (self.select_part(cid), self.delete_selected()))
        m.tk_popup(e.x_root, e.y_root)

    def value(self, p):
        v = self.ctx.ask_string("Value", f"Value of {p.id} ({p.unit or 'no unit'}). Examples: 100, 4.7k, 10meg, 220n:", str(p.value))
        if v and v.strip():
            from ...analog.units import parse_value
            try: parse_value(v)
            except ValueError as ex: self.ctx.say("Value", str(ex)); return
            self.edit(lambda nl: setattr(nl.part(p.id), "value", v.strip()))

    def source(self, p):
        """One box for a source: its DC level and the AC / waveform part."""
        from ...analog.units import parse_value
        fields = [("value", f"DC level ({p.unit})", p.value, None), ("ac", f"AC amplitude, peak ({p.unit}); 0 = none", p.extra["ac"], None), ("freq", "Frequency (Hz)", p.extra["freq"], None),
                  ("phase", "Phase (degrees)", p.extra["phase"], None), ("wave", "Waveform", p.extra["wave"], AC.Waveform.WAVES), ("duty", "Square-wave duty (0..1)", p.extra["duty"], None)]
        def check(v):
            for k in ("value", "ac", "freq", "phase", "duty"):
                try: parse_value(v[k])
                except ValueError as ex: return f"{k}: {ex}"
            if parse_value(v["ac"]) != 0 and parse_value(v["freq"]) <= 0: return "The frequency must be greater than 0."
        r = self.ctx.ask_form(f"Source {p.id}", "Examples: 5, 4.7k, 100m. The AC part is a sine (or square / triangle) of the given peak amplitude added to the DC level.", fields, check)
        if not r: return
        def go(nl):
            q = nl.part(p.id); q.value = r["value"]
            for k in ("ac", "freq", "phase", "wave", "duty"): q.extra[k] = r[k]
        self.edit(go)

    def settings(self, p):
        """Extra settings: a Zener's breakdown voltage, what a controlled source is controlled by."""
        from ...analog.units import parse_value
        if not isinstance(p, AC.Dependent):
            names = {"is": "is (saturation current, A)", "bf": "bf (forward beta)", "br": "br (reverse beta)", "vaf": "vaf (Early voltage, V)", "cbe": "cbe (base-emitter capacitance, F)", "cbc": "cbc (base-collector capacitance, F)",
                     "vto": "vto (threshold / pinch-off, V)", "kp": "kp (A/V²)", "beta": "beta (A/V²)", "lambda": "lambda (1/V)", "cgs": "cgs (gate-source capacitance, F)", "cgd": "cgd (gate-drain capacitance, F)",
                     "gain": "gain (open loop)", "vpos": "vpos (output limit, V)", "vneg": "vneg (output limit, V)", "gbw": "gbw (gain-bandwidth, Hz; 0 = none)", "ratio": "ratio (turns secondary / primary)", "k": "k (coupling, 0..1)", "vz": "vz (breakdown, V)"}
            fields = [(k, names.get(k, k), p.extra[k], None) for k in p.extras]
            def check(v):
                for k in v:
                    try: parse_value(v[k])
                    except ValueError as ex: return f"{k}: {ex}"
            r = self.ctx.ask_form(f"{p.type_name} {p.id}", p.summary, fields, check)
            if r: self.edit(lambda nl: [nl.part(p.id).extra.__setitem__(k, r[k]) for k in r])
            return
        for k, dv in p.extras.items():
            cur = p.extra[k]
            if k == "control" and not p.current_controlled:
                v = self.ctx.ask_string("Control", f"Two net names whose voltage controls {p.id} (first, second):", ", ".join(map(str, cur or [])))
                if not v: continue
                ns = [x.strip() for x in v.split(",") if x.strip()]
                if len(ns) != 2: self.ctx.say("Control", "Please give exactly two net names."); return
                val = ns
            elif k == "control":
                v = self.ctx.ask_string("Control", f"Id of the voltage source or ammeter whose current controls {p.id}:", str(cur or ""))
                if not v or not v.strip(): continue
                val = v.strip()
            else:
                v = self.ctx.ask_string(k, f"{k} of {p.id} (volts for a Zener). Examples: 5.1, 3.3:", str(cur))
                if not v or not v.strip(): continue
                try: parse_value(v)
                except ValueError as ex: self.ctx.say(k, str(ex)); return
                val = v.strip()
            self.edit(lambda nl, k=k, val=val: nl.part(p.id).extra.__setitem__(k, val))

    def nodes(self, p):
        names = ", ".join(p.terminals) if p.terminals else "first, second"
        v = self.ctx.ask_string("Connections", f"{p.nterm} net names for {p.id}, separated by commas ({names}). Use 0 for ground:", ", ".join(map(str, p.nodes)))
        if v:
            ns = [x.strip() for x in v.split(",") if x.strip()]
            if len(ns) != p.nterm: self.ctx.say("Connections", f"Please give exactly {p.nterm} net names."); return
            self.edit(lambda nl: setattr(nl.part(p.id), "nodes", ns))

    def rename(self, p):
        v = self.ctx.ask_string("Rename", f"New name for {p.id}:", p.id)
        if v and v.strip() and v.strip() != p.id: self.edit(lambda nl: setattr(nl.part(p.id), "id", v.strip()))
