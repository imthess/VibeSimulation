"""Mouse editing of the Logisim circuit, like Logisim's own: drag a part, a circuit pin, a wire piece or a wire corner;
Shift+drag on a wire adds a bend; Ctrl+drag (or drag from a part's output pin) onto another pin draws a new connection.

Every edit keeps all other wires exactly as they are (they are saved as "wires" in the JSON) and is checked by drawing
the whole circuit first; if the result would be wrong (overlap, short circuit, a wire through a part) nothing changes.
"""
from ...core import commands as C
from ...layout.engine import LayoutEngine
from ...layout.painter import pin_box_width
from ...layout.wire_edit import cut_pieces, move_segment, move_vertex, split_at, stretch_end, tidy
from ...layout.routing import norm, on_seg

SNAP = 10


def snap(v): return int(round(v / SNAP)) * SNAP


class DragMixin:
    """Methods of CircuitView that handle the mouse (mixed in so the view file stays about drawing)."""

    # ---------------------------------------------------------------- helpers
    def lpos(self, e):
        ox, oy = self.org; return (e.x - ox) / self.scale, (e.y - oy) / self.scale

    def _frozen(self):
        """Every signal's wires as they are drawn now: {signal: [(x1, y1, x2, y2), ...]}."""
        out = {}
        for w in self.doc.layout.wires: out.setdefault(w[4], []).append(tuple(w[:4]))
        return out

    def _ports_of(self):
        """Every pin position of the circuit with its signal name."""
        lay = self.doc.layout; ports = {}
        for pin, x, y in lay.inputs + lay.outputs: ports[(x, y)] = pin.name
        for pl in lay.parts:
            for p in pl.comp.all_ports():
                sig = (pl.comp.ins if p.direction == "in" else pl.comp.outs).get(p.name)
                ports[(pl.x + p.dx, pl.y + p.dy)] = sig if sig is not None else f"~{pl.comp.id}.{p.name}"
        return ports

    @staticmethod
    def _rect(comp, x, y):
        x0, y0, x1, y1 = comp.bounds(); return x + x0 - 10, y + y0 - 10, x + x1 + 10, y + y1 + 10

    @staticmethod
    def _pin_rect(kind, pin, x, y):
        w = pin_box_width(pin.width)
        return (x - w - 60, y - 14, x, y + 14) if kind == "in" else (x, y - 14, x + w + 60, y + 14)

    def _obstacles(self, skip=None):
        """Rectangles that a dragged part or pin must not overlap: (key, rect)."""
        lay = self.doc.layout; out = []
        for q in lay.parts: out.append((("part", q.comp.id), self._rect(q.comp, q.x, q.y)))
        for pin, px, py in lay.inputs: out.append((("in", pin.name), self._pin_rect("in", pin, px, py)))
        for pin, px, py in lay.outputs: out.append((("out", pin.name), self._pin_rect("out", pin, px, py)))
        return [(k, r) for k, r in out if k != skip]

    def _hits(self, rect, skip):
        a = rect
        return any(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3] for _, b in self._obstacles(skip))

    def _try(self, circuit):
        """Draw the circuit as the engine would; returns the Layout or None."""
        try: return LayoutEngine().build(circuit)
        except ValueError: return None

    def _ghost_rect(self, rect, ok):
        s = self.scale; ox, oy = self.org; c = self.canvas
        c.create_rectangle(ox + rect[0] * s, oy + rect[1] * s, ox + rect[2] * s, oy + rect[3] * s, outline=self.ctx.P["accent"] if ok else self.ctx.P["bad"],
                           dash=(4, 3), width=2, tags="ghost")

    def _ghost_lines(self, pieces):
        s = self.scale; ox, oy = self.org
        for t in pieces: self.canvas.create_line(ox + t[0] * s, oy + t[1] * s, ox + t[2] * s, oy + t[3] * s, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")

    # ---------------------------------------------------------------- press
    def on_click(self, e):
        h = self.hit(e); self._drag = None; self.canvas.focus_set()
        if self.tool: return self.place(e)
        st = getattr(e, "state", 0); ctrl, shift = bool(st & 4), bool(st & 1)
        if h is None or h[0] != "wire":
            if self.wsel and not ctrl: self.wsel = set(); self.draw()                  # a click anywhere else lets go of the selected wire
        if not h:
            if shift and self.doc.valid and self.doc.layout is not None:           # Shift+drag on empty space: rubber band selection
                self._drag = {"x": e.x, "y": e.y, "on": False, "dx": 0, "dy": 0, "ok": True, "kind": "band"}; return
            if self.sel or self.sels: self.select(None)
            return
        d = self.doc; ok = d.valid and d.layout is not None
        g = {"x": e.x, "y": e.y, "on": False, "dx": 0, "dy": 0, "ok": True}
        if h[0] == "pin":
            if not ok: self.signal_menu(e, h[1], h[2]); return
            comp = d.circuit.component(h[1]); pl = next(p for p in d.layout.parts if p.comp.id == h[1]); pt = comp.port(h[2])
            g.update(kind="sink", cid=h[1], port=h[2], sig=comp.ins.get(h[2]), at=(pl.x + pt.dx, pl.y + pt.dy), e=e); self._drag = g; return
        if not ok: return
        if h[0] == "opin":
            comp = d.circuit.component(h[1]); sig = comp.outs.get(h[2]); pl = next(p for p in d.layout.parts if p.comp.id == h[1]); pt = comp.port(h[2])
            if sig is not None: g.update(kind="conn", sig=sig, src=(pl.x + pt.dx, pl.y + pt.dy)); self._drag = g
        elif h[0] in ("inpin", "outpin"):
            kind = "in" if h[0] == "inpin" else "out"
            lay = d.layout; pin, x, y = next(t for t in (lay.inputs if kind == "in" else lay.outputs) if t[0].name == h[1])
            g.update(kind="conn" if (ctrl and kind == "in") else "pin", io=kind, name=h[1], pin=pin, at=(x, y), sig=h[1], src=(x, y)); self._drag = g
        elif h[0] == "comp":
            if ctrl: self.toggle(h[1]); return                                    # Ctrl+click adds / removes a part from the selection
            if h[1] in self.sels and len(self.sels) > 1: g.update(kind="group", id=h[1]); self._drag = g; return
            g.update(kind="part", id=h[1], items=None); self._drag = g
            if self.sel != h[1] or len(self.sels) != 1: self.select(h[1])
        elif h[0] == "wire":
            k = int(h[1]); w = d.layout.wires[k]; lx, ly = self.lpos(e); ports = self._ports_of()
            was = (w[4], tuple(w[:4])) in self.wsel
            self.pick_wire(w[4], tuple(w[:4]), ctrl)
            ends = [(w[0], w[1]), (w[2], w[3])]; near = min(ends, key=lambda p: abs(p[0] - lx) + abs(p[1] - ly))
            g.update(wire=k, net=w[4])
            if abs(near[0] - lx) + abs(near[1] - ly) <= 14 and near not in ports: g.update(kind="vertex", V=near)
            elif shift:
                Q = (snap(lx), snap(ly))
                if on_seg(w[:4], Q) and Q not in ends: g.update(kind="vertex", V=Q, split=Q)
                else: g.update(kind="wire")
            elif not was and not ctrl:                                   # a wire that was not selected: pulling from its middle draws a new wire from that point (Logisim)
                Q = (min(max(snap(lx), w[0]), w[2]), w[1]) if w[1] == w[3] else (w[0], min(max(snap(ly), w[1]), w[3]))
                g.update(kind="conn", sig=w[4], src=Q, branch=True)
            else: g.update(kind="wire")
            self._drag = g

    # ---------------------------------------------------------------- move
    def motion(self, e):
        g = self._drag
        if not g: return self.pan_move(e)
        if not g["on"]:
            if abs(e.x - g["x"]) + abs(e.y - g["y"]) < 6: return
            g["on"] = True; self.canvas.configure(cursor="fleur"); self._start(g)
        getattr(self, "_move_" + g["kind"])(e, g)

    def _start(self, g):
        c, lay = self.canvas, self.doc.layout; k = g["kind"]
        if k == "part":
            cid = g["id"]; g["pl"] = next(p for p in lay.parts if p.comp.id == cid)
            g["items"] = [i for i in c.find_all() if any(t == "comp:" + cid or t.startswith(f"pin:{cid}:") or t.startswith(f"opin:{cid}:") for t in c.gettags(i))]
        elif k == "group":
            ids = set(self.sels); g["ids"] = ids; g["pls"] = [p for p in lay.parts if p.comp.id in ids]
            g["items"] = [i for i in c.find_all() if any(t.startswith("comp:") and t[5:] in ids or t.startswith(("pin:", "opin:")) and t.split(":")[1] in ids for t in c.gettags(i))]
        elif k == "pin":
            g["items"] = [i for i in c.find_all() if any(t.startswith(("inpin:", "outpin:")) and t.split(":", 1)[1] == g["name"] and t.split(":")[0] == ("inpin" if g["io"] == "in" else "outpin") for t in c.gettags(i))]
        elif k in ("wire", "vertex"):
            net = g["net"]; idx = [j for j, w in enumerate(lay.wires) if w[4] == net]
            pieces = [tuple(lay.wires[j][:4]) for j in idx]
            if k == "vertex" and g.get("split"): pieces = split_at(pieces, g["split"])
            g["pieces"] = pieces; g["i"] = idx.index(g["wire"]); g["ports"] = self._ports_of()

    def _move_part(self, e, g):
        s = self.scale; dx = snap((e.x - g["x"]) / s); dy = snap((e.y - g["y"]) / s)
        if (dx, dy) == (g["dx"], g["dy"]): return
        for i in g["items"]: self.canvas.move(i, (dx - g["dx"]) * s, (dy - g["dy"]) * s)
        g["dx"], g["dy"] = dx, dy; pl = g["pl"]; rect = self._rect(pl.comp, pl.x + dx, pl.y + dy)
        g["ok"] = not self._hits(rect, ("part", pl.comp.id)); self.canvas.delete("ghost"); self._ghost_rect(rect, g["ok"])
        self.status.configure(text="Release to drop the part here" if g["ok"] else "Not here: it would overlap another part or pin")

    def _move_band(self, e, g):
        self.canvas.delete("ghost")
        self.canvas.create_rectangle(g["x"], g["y"], e.x, e.y, outline=self.ctx.P["accent"], dash=(4, 3), width=2, tags="ghost")
        self.status.configure(text="Release to select the parts inside the rectangle")

    def _drop_band(self, e, g):
        x0, x1 = sorted((g["x"], e.x)); y0, y1 = sorted((g["y"], e.y)); ox, oy = self.org; s = self.scale
        r = ((x0 - ox) / s, (y0 - oy) / s, (x1 - ox) / s, (y1 - oy) / s); hit = set()
        for pl in self.doc.layout.parts:
            bx0, by0, bx1, by1 = pl.comp.bounds()
            if pl.x + bx0 < r[2] and r[0] < pl.x + bx1 and pl.y + by0 < r[3] and r[1] < pl.y + by1: hit.add(pl.comp.id)
        self.sels = hit; self.sel = next(iter(hit), None) if len(hit) == 1 else None; self.draw()
        self.status.configure(text=f"{len(hit)} part(s) selected: drag one to move them all, Ctrl+C copy, Delete removes")

    def _move_group(self, e, g):
        s = self.scale; dx = snap((e.x - g["x"]) / s); dy = snap((e.y - g["y"]) / s)
        if (dx, dy) == (g["dx"], g["dy"]): return
        for i in g["items"]: self.canvas.move(i, (dx - g["dx"]) * s, (dy - g["dy"]) * s)
        g["dx"], g["dy"] = dx, dy; self.canvas.delete("ghost"); ok = True
        others = [r for k, r in self._obstacles(None) if not (k[0] == "part" and k[1] in g["ids"])]
        for pl in g["pls"]:
            rect = self._rect(pl.comp, pl.x + dx, pl.y + dy)
            bad = any(rect[0] < b[2] and b[0] < rect[2] and rect[1] < b[3] and b[1] < rect[3] for b in others); ok = ok and not bad
            self._ghost_rect(rect, not bad)
        g["ok"] = ok; self.status.configure(text="Release to drop the parts here" if ok else "Not here: a part would overlap another part or pin")

    def _drop_group(self, e, g):
        dx, dy = g["dx"], g["dy"]
        if (dx, dy) == (0, 0): return self.draw()
        if not g["ok"]: return self._refuse("That spot overlaps another part, so the parts stayed where they were.")
        places = {pl.comp.id: (pl.x + dx, pl.y + dy) for pl in g["pls"]}
        touched = {sg for pl in g["pls"] for sg in list(pl.comp.ins.values()) + list(pl.comp.outs.values()) if sg}
        wires = {k: [list(t) for t in v] for k, v in self._frozen().items() if k not in touched}
        c = self.doc.circuit.copy()
        for cid, p in places.items(): c.component(cid).pos = p
        c.wires = wires
        if self._try(c) is None:
            wires = {}; c.wires = {}
            if self._try(c) is None: return self._refuse("The wires could not be drawn with the parts there, so they stayed where they were.")
        self.run(C.MoveParts(places, wires))

    def _move_pin(self, e, g):
        s = self.scale; dx = snap((e.x - g["x"]) / s); dy = snap((e.y - g["y"]) / s)
        if (dx, dy) == (g["dx"], g["dy"]): return
        for i in g["items"]: self.canvas.move(i, (dx - g["dx"]) * s, (dy - g["dy"]) * s)
        g["dx"], g["dy"] = dx, dy; x, y = g["at"]; rect = self._pin_rect(g["io"], g["pin"], x + dx, y + dy)
        g["ok"] = not self._hits(rect, (g["io"], g["name"])); self.canvas.delete("ghost"); self._ghost_rect(rect, g["ok"])
        self.status.configure(text="Release to drop the pin here" if g["ok"] else "Not here: it would overlap a part or another pin")

    def _move_wire(self, e, g):
        s = self.scale; dx = snap((e.x - g["x"]) / s); dy = snap((e.y - g["y"]) / s)
        if (dx, dy) == (g["dx"], g["dy"]): return
        g["dx"], g["dy"] = dx, dy; self.canvas.delete("ghost")
        g["new"] = move_segment(g["pieces"], g["i"], dx, dy, set(g["ports"]))
        if g["new"] is None: self.status.configure(text="Drag a piece of wire sideways to move it."); return
        self._ghost_lines(g["new"]); self.status.configure(text="Release to put the wire here")

    def _move_vertex(self, e, g):
        lx, ly = self.lpos(e); V2 = (snap(lx), snap(ly))
        if V2 == g.get("V2"): return
        g["V2"] = V2; self.canvas.delete("ghost")
        g["pin"] = self._sink_at(V2) if V2 in g["ports"] and g["ports"][V2] != g["net"] else None
        g["new"] = move_vertex(g["pieces"], g["V"], V2, set(g["ports"])) if V2 not in g["ports"] or g["ports"][V2] == g["net"] or g["pin"] else None
        if g["new"] is None: self.status.configure(text="A wire end cannot sit on another pin."); return
        self._ghost_lines(g["new"]); self.status.configure(text="Release to connect the wire to this pin" if g["pin"] else "Release to move the corner here")

    def _move_sink(self, e, g):
        """Dragging the end of a wire that sits on an input pin (Logisim: pull the wire end off the pin and drop it on another one)."""
        s = self.scale; ox, oy = self.org; self.canvas.delete("ghost"); x, y = g["at"]; ax, ay = x, y
        if g["sig"] is not None:                                                    # the wire stays fixed at its other end
            for w in self.doc.layout.wires:
                if w[4] == g["sig"] and (w[0], w[1]) == (x, y): ax, ay = w[2], w[3]; break
                if w[4] == g["sig"] and (w[2], w[3]) == (x, y): ax, ay = w[0], w[1]; break
        self.canvas.create_line(ox + ax * s, oy + ay * s, e.x, e.y, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")
        self.canvas.create_oval(e.x - 6, e.y - 6, e.x + 6, e.y + 6, outline=self.ctx.P["accent"], width=2, tags="ghost")
        self.status.configure(text="Drop on another input pin, a wire or an output to connect it there; drop on empty space to unplug this pin" if g["sig"] is not None
                              else "Drop on a wire or an output to connect this pin to it")

    def _drop_sink(self, e, g):
        d = self.doc; c = d.circuit; cid, port, sig = g["cid"], g["port"], g["sig"]; h = self.hit(e); me = c.component(cid).port(port)
        if h and h[0] == "pin" and (h[1], h[2]) == (cid, port): return self.draw()
        cmds = []
        def width_ok(s):
            if c.signals().get(s) == me.width: return True
            self._refuse(f"{s} has {c.signals().get(s)} bit(s) but pin {me.name} needs {me.width}."); return False
        if h and h[0] == "pin":                                                      # move the wire from this pin to that one
            if sig is None: return self._refuse("This pin has no wire to move: drop on a wire or an output instead.")
            q = c.component(h[1]).port(h[2])
            if q.width != me.width: return self._refuse(f"Pin {q.name} needs {q.width} bit(s) but {sig} has {me.width}.")
            cmds = [C.Rewire(h[1], h[2], sig), C.Rewire(cid, port, None), C.SetWire(sig, None)]
        elif h and h[0] in ("opin", "inpin", "wire"):
            if h[0] == "opin":
                comp2 = c.component(h[1]); tgt = comp2.outs.get(h[2]) or f"{h[1]}_{h[2]}"
                if comp2.outs.get(h[2]) is None: cmds.append(C.SetOutputSignal(h[1], h[2], tgt))
            elif h[0] == "inpin": tgt = h[1]
            else: tgt = d.layout.wires[int(h[1])][4]
            if not width_ok(tgt): return
            if tgt == sig: return self.draw()
            cmds += [C.Rewire(cid, port, tgt), C.SetWire(tgt, None)] + ([C.SetWire(sig, None)] if sig else [])
        elif h and h[0] == "outpin": return self._refuse("An output pin shows a signal; drop the wire on an input pin, a wire or an output instead.")
        else:                                                                         # empty space: unplug, and the wire end stays where it was dropped (like Logisim)
            if sig is None: return self.draw()
            lx, ly = self.lpos(e); P = (snap(lx), snap(ly)); V = g["at"]
            pieces = [tuple(w[:4]) for w in self.doc.layout.wires if w[4] == sig]
            if P != V and any(V in ((t[0], t[1]), (t[2], t[3])) for t in pieces): route = [list(t) for t in tidy(move_vertex(pieces, V, P, self._ports_of()))]
            elif P != V: route = [list(t) for t in tidy(pieces + [norm(V, (P[0], V[1])), norm((P[0], V[1]), P)])]
            else: route = None
            if route: self._commit_cmds([C.Rewire(cid, port, None)], sig, route, [C.SetWire(sig, None)])
            else: self.run(C.Batch([C.Rewire(cid, port, None), C.SetWire(sig, None)]))
            self.status.configure(text=f"Pin {port} of {cid} is unplugged and the wire end stays there (Ctrl+Z puts it back)")
            return
        self.run(C.Batch(cmds))

    def _move_conn(self, e, g):
        s = self.scale; ox, oy = self.org; self.canvas.delete("ghost"); x, y = g["src"]
        self.canvas.create_line(ox + x * s, oy + y * s, e.x, e.y, fill=self.ctx.P["accent"], width=3, dash=(5, 3), tags="ghost")
        self.status.configure(text=f"Drop on an input pin to connect signal {g['sig']} to it")

    # ---------------------------------------------------------------- release
    def release(self, e):
        g, self._drag, self._pan = self._drag, None, None
        if not g: return
        self.canvas.configure(cursor="arrow"); self.canvas.delete("ghost")
        if not g["on"]:
            if g.get("kind") == "sink": return self.signal_menu(g["e"], g["cid"], g["port"])           # a plain click on a pin: choose its signal
            if g.get("kind") == "pin" and g["io"] == "in":                           # a plain click on an input pin toggles it
                pin = g["pin"]; cur = self.doc.invals.get(pin.name, 0)
                self.doc.set_input(pin.name, (cur ^ 1) if pin.width == 1 else (cur + 1) % (1 << pin.width))
            return
        getattr(self, "_drop_" + g["kind"])(e, g)

    def _refuse(self, text):
        self.draw(); self.status.configure(text=text)

    def _drop_part(self, e, g):
        pl = g["pl"]; dx, dy = g["dx"], g["dy"]
        if (dx, dy) == (0, 0): return self.draw()
        if not g["ok"]: return self._refuse("That spot overlaps another part, so the part stayed where it was.")
        comp = pl.comp; wires = self._frozen(); mine = []
        for p in comp.all_ports():                                   # wires keep their shape; only the ones on this part's pins stretch along
            sig = (comp.ins if p.direction == "in" else comp.outs).get(p.name)
            if sig is None or sig not in wires: continue
            old = (pl.x + p.dx, pl.y + p.dy)
            wires[sig] = stretch_end(wires[sig], old, (old[0] + dx, old[1] + dy), p.side in ("top", "bottom")); mine.append(sig)
        ordered = self._order(wires, mine); nx, ny = pl.x + dx, pl.y + dy
        c = self.doc.circuit.copy(); c.component(comp.id).pos = (nx, ny); c.wires = ordered
        if self._try(c) is None:
            ordered = {}; c = self.doc.circuit.copy(); c.component(comp.id).pos = (nx, ny); c.wires = {}      # could not keep the old wires: draw them again automatically
            if self._try(c) is None: return self._refuse("The wires could not be drawn with the part there, so it stayed where it was.")
        self.run(C.MovePart(comp.id, nx, ny, ordered))

    def _drop_pin(self, e, g):
        dx, dy = g["dx"], g["dy"]
        if (dx, dy) == (0, 0): return self.draw()
        if not g["ok"]: return self._refuse("That spot overlaps another part or pin, so the pin stayed where it was.")
        name, io = g["name"], g["io"]; x, y = g["at"]; new = (x + dx, y + dy); wires = self._frozen()
        if name in wires: wires[name] = stretch_end(wires[name], (x, y), new, False)
        ordered = self._order(wires, [name])
        def cand(w):
            c = self.doc.circuit.copy(); pin = next(p for p in (c.inputs if io == "in" else c.outputs) if p.name == name); pin.pos = new; c.wires = w; return c
        if self._try(cand(ordered)) is None:
            ordered = {}
            if self._try(cand({})) is None: return self._refuse("The wires could not be drawn with the pin there, so it stayed where it was.")
        self.run(C.MovePin(io, name, new[0], new[1], ordered))

    @staticmethod
    def _order(wires, first):
        """The edited signals first (they win when two routes collide), then the rest; as plain lists for the JSON."""
        keys = list(dict.fromkeys(first)) + [k for k in wires if k not in first]
        return {k: [list(t) for t in wires[k]] for k in keys}

    def _commit_route(self, g, route, text):
        net = g["net"]; others = {k: [list(t) for t in v] for k, v in self._frozen().items() if k != net}
        c = self.doc.circuit.copy(); c.wires = dict({net: route}, **others); lay = self._try(c)
        if lay is None or net not in lay.fixed or not lay.fixed >= set(self.doc.layout.fixed):
            return self._refuse(text)
        self.run(C.SetWire(net, route, others))

    def _drop_wire(self, e, g):
        if not g.get("new"): return self.draw()
        self._commit_route(g, [list(t) for t in tidy(g["new"])], "The wire cannot go there (it would touch another wire, a pin or a part), so it stayed where it was.")

    def _sink_at(self, P):
        """The input pin of a part, or the output pin of the circuit, that sits at point P: ("part", id, port) / ("out", name) / None."""
        lay = self.doc.layout
        for pl in lay.parts:
            for p in pl.comp.all_ports():
                if p.direction == "in" and (pl.x + p.dx, pl.y + p.dy) == P: return ("part", pl.comp.id, p.name)
        for pin, x, y in lay.outputs:
            if (x, y) == P: return ("out", pin.name)
        return None

    def _drop_vertex(self, e, g):
        if not g.get("new") or g.get("V2") == g["V"]: return self.draw()
        if g.get("pin"):                                                       # a wire end dropped on an input pin connects the wire to it
            net = g["net"]; tgt = g["pin"]; c = self.doc.circuit; route = [list(t) for t in tidy(g["new"])]
            if tgt[0] == "part":
                comp = c.component(tgt[1]); old = comp.ins.get(tgt[2]); wd = comp.port(tgt[2]).width
                if c.signals().get(net) != wd: return self._refuse(f"{net} has {c.signals().get(net)} bit(s) but pin {tgt[2]} needs {wd}.")
                cmds = [C.Rewire(tgt[1], tgt[2], net)] + ([C.SetWire(old, None)] if old and old != net else [])
            else: cmds = [C.ChangeOutput(tgt[1], net)]
            return self._commit_cmds(cmds, net, route, [C.SetWire(net, None)])
        self._commit_route(g, [list(t) for t in tidy(g["new"])], "The corner cannot go there (the wire would touch another wire, a pin or a part), so it stayed where it was.")

    def _drop_conn(self, e, g):
        h = self.hit(e); sig = g["sig"]; lay = self.doc.circuit
        if h and h[0] == "pin":
            comp = lay.component(h[1]); port = comp.port(h[2])
            if lay.signals().get(sig) != port.width: return self._refuse(f"{sig} has {lay.signals().get(sig)} bit(s) but pin {port.name} needs {port.width}.")
            old = comp.ins.get(h[2])
            self.run(C.Batch([C.Rewire(h[1], h[2], sig)] + ([C.SetWire(old, None)] if old and old != sig else [])))
        elif h and h[0] == "outpin" and g.get("io") != "out":
            self.run(C.ChangeOutput(h[1], sig))
        elif h and h[0] in ("opin", "inpin", "outpin", "wire", "comp"):
            tgt = self.doc.layout.wires[int(h[1])][4] if h[0] == "wire" else None
            if tgt == sig: return self.draw()
            self._refuse("Two different signals cannot be joined by a wire. Drop on an input pin, or on empty space to leave the wire end there.")
        else: self._stub(sig, g["src"], e)

    def _stub(self, sig, Q, e, pieces=None):
        """Leave a wire end where it was dropped (Logisim keeps loose wires): the signal's route gets a new piece from Q to the pointer."""
        lx, ly = self.lpos(e); P = (snap(lx), snap(ly))
        if P == Q: return self.draw()
        pieces = list(pieces) if pieces is not None else [tuple(w[:4]) for w in self.doc.layout.wires if w[4] == sig]
        bend = (P[0], Q[1]); new = [norm(Q, bend), norm(bend, P)]
        route = [list(t) for t in tidy(pieces + [t for t in new if t[:2] != t[2:]])]
        self._commit_route({"net": sig}, route, "The wire end cannot go there (it would touch another wire, a pin or a part), so nothing changed.")
        self.status.configure(text="Wire end left there: drag it onto an input pin to connect it, or select it and press Delete")

    def _commit_cmds(self, cmds, net, route, fallback):
        """Run cmds and give `net` the hand-made route; when that route is not drawable, run the fallback commands instead."""
        others = {k: [list(t) for t in v] for k, v in self._frozen().items() if k != net}
        full = list(cmds) + [C.SetWire(net, route, others)]
        cand = self.doc.circuit.copy(); C.Batch(full).apply(cand); lay = self._try(cand)
        if lay is None or (route and net not in lay.fixed): full = list(cmds) + list(fallback)
        self.run(C.Batch(full))

    # ---------------------------------------------------------------- selecting and deleting wires (Logisim: click a wire, press Delete)
    def pick_wire(self, net, piece, add=False):
        key = (net, piece)
        if add: self.wsel ^= {key}
        else: self.wsel = {key}
        self.sel = None; self.sels = set(); self.draw()
        self.status.configure(text="Wire selected: Delete removes it, drag it to move it, drag its corner to bend it" if self.wsel else "")

    def _roles(self):
        """{net: (driver points, [(sink point, kind, id, port)])} from the picture as drawn now."""
        lay = self.doc.layout; c = self.doc.circuit; out = {}
        def put(sig, drv=None, snk=None):
            e = out.setdefault(sig, ([], []))
            if drv: e[0].append(drv)
            if snk: e[1].append(snk)
        for pin, x, y in lay.inputs: put(pin.name, drv=(x, y))
        for pin, x, y in lay.outputs: put(pin.name, snk=((x, y), "out", pin.name, None))
        for pl in lay.parts:
            for p in pl.comp.all_ports():
                sig = (pl.comp.ins if p.direction == "in" else pl.comp.outs).get(p.name)
                if sig is None: continue
                pos = (pl.x + p.dx, pl.y + p.dy)
                if p.direction == "in": put(sig, snk=(pos, "part", pl.comp.id, p.name))
                else: put(sig, drv=pos)
        return out

    def delete_wires(self):
        d = self.doc
        if not d.valid or d.layout is None: return
        lay = d.layout; roles = self._roles(); by = {}
        for net, piece in self.wsel: by.setdefault(net, set()).add(piece)
        routes, unplug, msgs = {}, [], []
        for net, gone in by.items():
            segs = [tuple(w[:4]) for w in lay.wires if w[4] == net]
            idx = {i for i, s in enumerate(segs) if s in gone}
            drv, snk = roles.get(net, ([], []))
            kept, lost = cut_pieces(segs, idx, drv, [x[0] for x in snk])
            for sk in snk:
                if sk[0] in lost:
                    if sk[1] == "out": return self._refuse(f"The wire to output {sk[2]} cannot be left unplugged (an output shows a signal): right-click the output pin to delete it instead.")
                    unplug.append((sk[2], sk[3]))
            routes[net] = [list(t) for t in tidy(kept)] if kept else None
            msgs.append(net)
        others = {k: [list(t) for t in v] for k, v in self._frozen().items() if k not in routes}
        cmd = C.CutWires(routes, unplug, others)
        cand = d.circuit.copy(); cmd.apply(cand)
        if self._try(cand) is None:                                                   # a kept hand-made route is not drawable: let the wire draw itself again
            cmd = C.CutWires({n: None for n in routes}, unplug, others)
        self.wsel = set(); self.run(cmd)
        self.status.configure(text=(f"Wire deleted: {len(unplug)} pin(s) unplugged" if unplug else "Wire piece deleted") + "  (Ctrl+Z undoes)")

    # ---------------------------------------------------------------- right-click helpers
    def delete_piece(self, k):
        """Delete one piece of wire if the signal's pins stay connected without it (clears dangling or doubled pieces)."""
        w = self.doc.layout.wires[k]; net = w[4]
        pieces = [tuple(x[:4]) for x in self.doc.layout.wires if x[4] == net]; pieces.remove(tuple(w[:4]))
        if not pieces: return self._refuse(f"This is the only piece of wire of {net}. Use 'Put wire back in automatic route' instead.")
        g = {"net": net}
        self._commit_route(g, [list(t) for t in tidy(pieces)], f"This piece is needed to connect the pins of {net}, so it was not deleted.")
