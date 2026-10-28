"""Wired schematic layout for analog circuits ("ladder" style).

Every non-ground net is a horizontal rail. Parts that go from a net to ground hang down from the rail
(shunt parts) to one common ground rail at the bottom. Parts between two nets sit on the rail line and split
it into segments (series parts); extra branches drop down to a new row. Loops (parts that close a cycle) are
drawn as an arc above the circuit. Wires of one net never touch another net's wires except by crossing.
"""
import math
from dataclasses import dataclass, field

from ..core.render import Renderer
from .components import VoltageSource
from .solver import is_ground

SLOT, SERIES, ROW_H, SHUNT_H, TOP, X0, LANE_H = 130, 120, 190, 210, 90, 80, 50


def canon(n): return "0" if is_ground(n) else str(n).strip()


def up10(v): return int(math.ceil(v / 10.0) * 10)


def pin_xy(pl, k):
    """Absolute position of terminal k of a placed part."""
    p = pl.part
    if p.nterm != 2: dx, dy = p.PINS[k]; return pl.cx + dx, pl.cy + dy
    d = {0: (-60, 0), 90: (0, -60), 180: (60, 0), 270: (0, 60)}[pl.angle]; sg = 1 if k == 0 else -1
    return pl.cx + sg * d[0], pl.cy + sg * d[1]


def pin_dir(part, k):
    """Unit direction a pin points away from the symbol (for its net label)."""
    dx, dy = part.PINS[k]
    return (1 if dx > 0 else -1, 0) if abs(dx) >= 30 else (0, 1 if dy > 0 else -1)


@dataclass
class Placed:
    part: object
    cx: int
    cy: int
    angle: int            # direction of the first terminal: 0 left, 90 top, 180 right, 270 bottom

    @property
    def vertical(self): return self.angle in (90, 270)


@dataclass
class SchematicLayout:
    parts: list = field(default_factory=list)
    wires: list = field(default_factory=list)       # (x1, y1, x2, y2, net)
    grounds: list = field(default_factory=list)     # (x, y) of ground symbols
    rails: list = field(default_factory=list)       # (net, x, y) where to write the net name
    fixed: set = field(default_factory=set)         # nets whose wires are the user's own route
    labels: list = field(default_factory=list)      # (x, y, net, (ux, uy)): net name written at a pin of a transistor / op-amp / transformer (they are joined by name, not by wires)

    def extent(self):
        xs, ys = [], []
        for p in self.parts:
            w = 80 if p.part.nterm == 2 else 90; xs += [p.cx - w, p.cx + w]; ys += [p.cy - 80, p.cy + (80 if p.part.nterm == 2 else 90)]
        for w in self.wires: xs += [w[0], w[2]]; ys += [w[1], w[3]]
        for x, y in self.grounds: xs.append(x); ys += [y + 30]
        return (min(xs) - 20, min(ys) - 30, max(xs) + 90, max(ys) + 20) if xs else (0, 0, 100, 100)

    def terminals(self):
        """(x, y, net) of every part terminal."""
        out = []
        for pl in self.parts:
            for k in range(pl.part.nterm):
                x, y = pin_xy(pl, k); out.append((x, y, canon(pl.part.nodes[k])))
        return out

    def junctions(self):
        """Points where 3+ wire/part ends meet, or an end touches the middle of a wire of the same net."""
        by, out = {}, []
        for w in self.wires: by.setdefault(w[4], []).append(w)
        terms = {}
        for x, y, n in self.terminals(): terms.setdefault(n, []).append((x, y))
        for net, segs in by.items():
            pts = {(w[0], w[1]) for w in segs} | {(w[2], w[3]) for w in segs}
            extra = terms.get(net, [])
            for (px, py) in pts:
                ends = sum(1 for w in segs if (w[0], w[1]) == (px, py) or (w[2], w[3]) == (px, py)) + sum(1 for t in extra if t == (px, py))
                inner = any(min(w[0], w[2]) <= px <= max(w[0], w[2]) and min(w[1], w[3]) <= py <= max(w[1], w[3])
                            and (w[0], w[1]) != (px, py) and (w[2], w[3]) != (px, py) for w in segs)
                if ends >= 3 or (inner and ends >= 1): out.append((px, py))
        return out


def apply_offsets(L):
    """Move every part the user dragged (part.pos = (dx, dy)) and stretch its wires with it: a wire that ended on a moved
    terminal now ends on the terminal's new place, with one right-angle bend so that it still leaves along the part's axis."""
    moved = [pl for pl in L.parts if pl.part.pos and tuple(pl.part.pos) != (0, 0)]
    if not moved: return L
    mv = {}
    for pl in moved:
        if pl.part.nterm != 2: dx, dy = pl.part.pos; pl.cx += dx; pl.cy += dy; continue       # joined by name: nothing to stretch
        dx, dy = pl.part.pos; d = {0: (-60, 0), 90: (0, -60), 180: (60, 0), 270: (0, 60)}[pl.angle]
        for tx, ty, net in ((pl.cx + d[0], pl.cy + d[1], canon(pl.part.nodes[0])), (pl.cx - d[0], pl.cy - d[1], canon(pl.part.nodes[1]))):
            mv[(tx, ty, net)] = (tx + dx, ty + dy, pl.vertical)
        pl.cx += dx; pl.cy += dy
    out = []
    for x1, y1, x2, y2, net in L.wires:
        a, b = mv.get((x1, y1, net)), mv.get((x2, y2, net))
        if not a and not b: out.append((x1, y1, x2, y2, net)); continue
        A, B = (a[0], a[1]) if a else (x1, y1), (b[0], b[1]) if b else (x2, y2)
        if A == B: continue
        if A[0] == B[0] or A[1] == B[1]: out.append(A + B + (net,)); continue
        if a: bend = (A[0], B[1]) if a[2] else (B[0], A[1])
        else: bend = (B[0], A[1]) if b[2] else (A[0], B[1])
        out.append(A + bend + (net,)); out.append(bend + B + (net,))
    L.wires = out
    return L


def apply_wire_overrides(L, wires):
    """Replace the automatic wires of a net by the route the user dragged, if that route still joins exactly the net's terminals."""
    from ..layout.routing import net_joined, on_seg
    terms = L.terminals()
    for net, segs in wires.items():
        try: segs = [tuple(int(v) for v in x) for x in segs]
        except (TypeError, ValueError): continue
        if not segs or any(len(s) != 4 or s[0] > s[2] or s[1] > s[3] or (s[0] != s[2] and s[1] != s[3]) for s in segs): continue
        if not net_joined([s + (net,) for s in segs]): continue
        if any(n == net and not any(on_seg(s, (x, y)) for s in segs) for x, y, n in terms): continue
        if any(n != net and any(on_seg(s, (x, y)) for s in segs) for x, y, n in terms): continue
        if not any(w[4] == net for w in L.wires) and not any(n == net for _, _, n in terms): continue
        L.wires = [w for w in L.wires if w[4] != net] + [s + (net,) for s in segs]; L.fixed.add(net)
        hs = [s for s in segs if s[1] == s[3] and s[0] != s[2]]
        if hs and net == "0":                                       # the ground symbol follows the ground wire
            s0 = max(hs, key=lambda s: (s[1], -s[0])); L.grounds = [(s0[0], s0[1])]
        elif hs:                                                    # so does the net's name label
            s0 = min(hs, key=lambda s: (s[0], s[1])); L.rails = [(n, s0[0], s0[1]) if n == net else (n, x, y) for n, x, y in L.rails]
    return L


class _Island:
    def __init__(self): self.row = 0


class SchematicBuilder:
    def build(self, nl):
        self.shunts, self.adj, self.series, order = {}, {}, [], []
        for p in nl.parts:
            if p.nterm != 2 or len(p.nodes) != 2: continue
            a, b = canon(p.nodes[0]), canon(p.nodes[1])
            if a == b: continue
            if a == "0" or b == "0":
                net = b if a == "0" else a
                self.shunts.setdefault(net, []).append((p, a == net)); order.append(net)
            else:
                e = (p, a, b); self.series.append(e); self.adj.setdefault(a, []).append(e); self.adj.setdefault(b, []).append(e); order += [a, b]
        self.seen, self.rails, self.placed = set(), {}, set()
        self.i_shunt, self.i_leg, self.i_series = [], [], []
        roots = [n for n in dict.fromkeys(order) if any(isinstance(s[0], VoltageSource) for s in self.shunts.get(n, []))] + list(dict.fromkeys(order))
        x, max_row = X0, 0
        for r in roots:
            if r in self.seen: continue
            isl = _Island(); far = self.lay(r, 0, x, None, isl)
            x = up10(far + SLOT); max_row = max(max_row, isl.row)
        arcs = [e for e in self.series if id(e[0]) not in self.placed]
        top_y = TOP + LANE_H * len(arcs)
        Y = lambda row: top_y + row * ROW_H
        yg = Y(max_row) + SHUNT_H
        L = SchematicLayout()
        W = lambda x1, y1, x2, y2, net: L.wires.append((x1, y1, x2, y2, net)) if (x1, y1) != (x2, y2) else None
        gx = []
        for net, row, x, p, a_top in self.i_shunt:
            yr = Y(row); cy = (yr + yg) // 2 // 10 * 10
            L.parts.append(Placed(p, x, cy, 90 if a_top else 270)); W(x, yr, x, cy - 60, net); W(x, cy + 60, x, yg, "0"); gx.append(x)
        for p, r1, r2, x, a_top in self.i_leg:
            y1, y2 = Y(r1), Y(r2); cy = (y1 + y2) // 2 // 10 * 10
            net_top = canon(p.nodes[0]) if a_top else canon(p.nodes[1]); net_bot = canon(p.nodes[1]) if a_top else canon(p.nodes[0])
            L.parts.append(Placed(p, x, cy, 90 if a_top else 270)); W(x, y1, x, cy - 60, net_top); W(x, cy + 60, x, y2, net_bot)
        for p, row, xa, a_left in self.i_series:
            L.parts.append(Placed(p, xa + SERIES // 2, Y(row), 0 if a_left else 180))
        for net, (row, xs, xr) in self.rails.items():
            W(xs, Y(row), xr, Y(row), net); L.rails.append((net, xs, Y(row)))
        for k, (p, a, b) in enumerate(arcs):                      # loops: arc above the circuit
            ra, rb = self.rails[a], self.rails[b]
            if ra[1] > rb[1]: a, b, ra, rb = b, a, rb, ra; a_left = False
            else: a_left = True
            xl, xr_ = ra[1], max(rb[2], ra[1] + SERIES + 40)
            lane = top_y - 50 - LANE_H * k; cx = (xl + xr_) // 2 // 10 * 10
            W(xl, Y(ra[0]), xl, lane, a); W(xl, lane, cx - 60, lane, a); W(cx + 60, lane, xr_, lane, b); W(xr_, lane, xr_, Y(rb[0]), b)
            L.parts.append(Placed(p, cx, lane, 0 if (canon(p.nodes[0]) == a) else 180))
        if gx:
            W(min(gx), yg, max(gx), yg, "0"); L.grounds.append((min(gx), yg))
        multi = [p for p in nl.parts if p.nterm != 2 and len(p.nodes) == p.nterm]
        if multi:                                                  # transistors, op-amps, transformers: a row of symbols below the circuit, joined by net names
            x0, y0, x1, y1 = L.extent() if L.parts or L.wires else (0, 0, X0 * 2, 0)
            row_y = max(y1 + 90, TOP + 90); x = max(X0, x0 + 60); per = 0
            for p in multi:
                wd = 260 if p.nterm == 4 else 220
                if per and x + wd > max(x1, X0 + 900): row_y += 200; x = max(X0, x0 + 60); per = 0
                L.parts.append(Placed(p, x + wd // 2 - 50, row_y + 60, 0)); x += wd; per += 1
        L = apply_wire_overrides(apply_offsets(L), getattr(nl, "wires", {}))
        for pl in L.parts:
            if pl.part.nterm != 2:
                for k in range(pl.part.nterm): x, y = pin_xy(pl, k); L.labels.append((x, y, canon(pl.part.nodes[k]), pin_dir(pl.part, k)))
        return L

    def lay(self, net, row, xs, via, isl):
        """Place net's rail starting at x=xs on `row`; returns the right-most x used."""
        self.seen.add(net)
        slots = sorted(self.shunts.get(net, []), key=lambda s: 0 if isinstance(s[0], VoltageSource) else 1)
        xe = xs + SLOT * (len(slots) - 1) if slots else xs
        rail = [row, xs, xe]; self.rails[net] = rail
        for i, (p, a_top) in enumerate(slots): self.i_shunt.append((net, row, xs + i * SLOT, p, a_top))
        edges = [e for e in self.adj.get(net, []) if id(e[0]) != via]
        reach, far = xe, xe + (SLOT // 2 if slots else 0)
        next_leg = xe + SLOT if slots else xe
        for p, a, b in edges[:-1]:                               # branches go down to new rows
            o = b if a == net else a
            if o in self.seen: continue
            isl.row += 1; r2 = isl.row; x = up10(max(next_leg, far if far > xe else next_leg))
            sub = self.lay(o, r2, x, id(p), isl)
            self.i_leg.append((p, row, r2, x, a == net)); self.placed.add(id(p))
            reach = max(reach, x); far = max(far, sub); next_leg = up10(sub + SLOT // 2)
        if edges:
            p, a, b = edges[-1]; o = b if a == net else a
            if o not in self.seen:                               # the chain continues to the right on the same row
                xa = up10(max(reach, far)); rail[2] = xa
                self.i_series.append((p, row, xa, a == net)); self.placed.add(id(p))
                far = max(far, self.lay(o, row, xa + SERIES, id(p), isl))
        rail[2] = max(rail[2], reach)
        return max(far, rail[2])


class Rot(Renderer):
    """Draws a part that was written horizontally (first terminal on the left) at any of the four orientations."""
    def __init__(self, r, cx, cy, angle): self.r, self.cx, self.cy, self.a = r, cx, cy, angle

    def T(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        dx, dy = {0: (dx, dy), 90: (-dy, dx), 180: (-dx, -dy), 270: (dy, -dx)}[self.a]
        return self.cx + dx, self.cy + dy

    def line(self, pts, width=2, role="outline", tags=()): self.r.line([self.T(*p) for p in pts], width, role, tags)
    def polygon(self, pts, fill="fill", outline="outline", width=2, tags=()): self.r.polygon([self.T(*p) for p in pts], fill, outline, width, tags)
    def circle(self, cx, cy, r, fill="fill", outline="outline", width=2, tags=()): self.r.circle(*self.T(cx, cy), r, fill, outline, width, tags)
    def rect(self, x0, y0, x1, y1, fill="fill", outline="outline", width=2, tags=()): self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width, tags)
    def text(self, x, y, s, size=10, role="muted", bold=False, anchor="c", tags=()):
        X, Y = self.T(x, y); self.r.text(X, Y, s, size, role, bold, anchor, tags)
