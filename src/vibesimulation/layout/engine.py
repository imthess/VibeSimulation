"""Places components in columns and routes the wires (Facade over the two routing strategies).

Components are placed left to right by "level" (how many parts the signal passed through), and
vertically near the signals that feed them. Wires then connect each driving pin to every pin that uses
the signal. All coordinates are Logisim grid units (multiples of 10).
"""
import random
import time
from dataclasses import dataclass, field

from ..components.gates.gate_base import Gate
from .painter import pin_box_width
from .routing import norm, MazeRouter, RailRouter, check_connectivity, merge_collinear, touch
from .wire_edit import valid_route

IN_X, IN_Y0, IN_DY = 130, 120, 40
GAP_TRIES = (70, 110, 170, 250)
ROUGH_ABOVE = 150      # more parts than this: the wire router would take minutes, so wires are drawn as simple guide lines
ROOMY = ((100, 20), (140, 20), (100, 10), (70, 10), (110, 10), (170, 10), (250, 10))   # (column gap, wire-lane spacing): roomiest first
SIDE_STEP = {"left": (-10, 0), "right": (10, 0), "top": (0, -10), "bottom": (0, 10)}


@dataclass
class Placed:
    comp: object
    x: int
    y: int
    level: int = 0

    def pin(self, p):
        return (self.x + p.dx, self.y + p.dy)


@dataclass
class Layout:
    inputs: list = field(default_factory=list)     # (IOPin, x, y)
    outputs: list = field(default_factory=list)    # (IOPin, x, y)
    parts: list = field(default_factory=list)      # Placed
    wires: list = field(default_factory=list)      # (x1, y1, x2, y2, net)
    fixed: set = field(default_factory=set)        # signals whose wires are the user's own route
    rough: bool = False                            # big circuit: wires are straight guide lines (may overlap), not a clean Logisim routing

    def extent(self):
        xs, ys = [], []
        for pin, x, y in self.inputs + self.outputs:
            xs += [x - 40, x + 40]; ys += [y - 10, y + 10]
        for p in self.parts:
            x0, y0, x1, y1 = p.comp.bounds()
            xs += [p.x + x0, p.x + x1]; ys += [p.y + y0, p.y + y1]
        for w in self.wires:
            xs += [w[0], w[2]]; ys += [w[1], w[3]]
        return min(xs), min(ys), max(xs), max(ys)


def _edges(comp):
    """(has pins on the top edge, has pins on the bottom edge) - those need free space for their wires."""
    sides = {p.side for p in comp.active_ports()}
    return ("top" in sides, "bottom" in sides)


VGAP = 40       # clear space kept between two parts stacked in one column


def _gap(lower_has_bottom, upper_has_top):
    """Clearance needed between one part's bottom and the next part's top."""
    return VGAP + 20 * bool(lower_has_bottom) + 20 * bool(upper_has_top)


class LayoutEngine:
    def build(self, circuit):
        """Draw the circuit. A hand-made wire route that no longer fits (a part was moved ...) is quietly ignored."""
        if circuit.wires:
            try: return self._build_all(circuit, True)
            except ValueError: pass
        return self._build_all(circuit, False)

    def _build_all(self, circuit, use_wires):
        circuit.sync(); self.use_wires = use_wires
        parts = circuit.order()
        if parts is None:
            raise ValueError("Circuit contains a loop")
        tidy = all(isinstance(c, Gate) for c in parts) and not any(c.pos or c.facing != "east" for c in parts) and not any(p.pos for p in circuit.inputs + circuit.outputs) and not (use_wires and circuit.wires)     # dragged parts need the flexible router
        if len(parts) > ROUGH_ABOVE: return self._build(circuit, parts, 100, True, None, rough=True)
        err, end = None, time.time() + 1.5
        if tidy and len(parts) <= 12:                                   # roomiest layout first (readable); tighten only if wires cannot be routed
            for gap, step in ROOMY:
                try: return self._build(circuit, parts, gap, False, end, step)
                except ValueError as e: err = e
                if time.time() > end: break
        budget = time.time() + (5 if len(parts) > 40 else 40)          # a big circuit gets one overall time budget, then guide lines
        for gap in (100, 140, 180, 250, 400):             # slower, more flexible maze router
            if time.time() > budget and len(parts) > 40: break
            try: return self._build(circuit, parts, gap, True, min(time.time() + 8, budget) if len(parts) > 40 else time.time() + 8)
            except ValueError as e: err = e
        if len(parts) > 40: return self._build(circuit, parts, 100, True, None, rough=True)
        raise ValueError(str(err))

    # ------------------------------------------------------------------ placement
    def _build(self, c, parts, gap, maze, deadline, step=10, rough=False):
        ins, n_in = c.inputs, len(c.inputs)
        src_y, level = {}, {}
        for i, p in enumerate(ins):
            src_y[p.name] = IN_Y0 + IN_DY * i
            level[p.name] = 0
        placed, by_level, floor = [], {}, {}
        for comp in parts:
            sig_ins = [(p, comp.ins[p.name]) for p in comp.in_ports() if comp.ins.get(p.name) is not None]
            L = 1 + max([level[s] for _, s in sig_ins if s in level], default=0)         # (a signal fed back from a later part is not known yet)
            wants = [src_y[s] - p.dy for p, s in sig_ins if s in src_y]
            y = int(round((sum(wants) / len(wants)) / 10)) * 10 if wants else IN_Y0 + IN_DY * n_in
            x0, y0, x1, y1 = comp.bounds()
            mine = _edges(comp)
            if rough:                                           # big circuit: each column simply grows downwards (checking every earlier part would take minutes)
                fl = floor.get(L)
                if fl is not None: y = max(y, fl[0] + _gap(fl[1], mine[0]) - y0)
                floor[L] = (y + y1, mine[1])
            else:
                while any(not (y + y1 + _gap(mine[1], oe[0]) <= oy + ob[1] or oy + ob[3] + _gap(oe[1], mine[0]) <= y + y0)
                          for _, oy, ob, oe in by_level.get(L, [])):
                    y += 10
            pl = Placed(comp, 0, y, L)
            placed.append(pl)
            by_level.setdefault(L, []).append((pl, y, (x0, y0, x1, y1), mine))
            for p in comp.out_ports():
                s = comp.outs.get(p.name)
                if s is not None:
                    src_y[s] = y + p.dy; level[s] = L
        M = max((p.level for p in placed), default=0)
        # ---- columns
        left, right, ox = {}, {0: IN_X}, {}
        for L in range(1, M + 1):
            cols = [p.comp.bounds() for p in placed if p.level == L]
            need_l, need_r = -(-max(-b[0] for b in cols) // 10) * 10, -(-max(b[2] for b in cols) // 10) * 10      # whole grid steps (turned parts can be 5 off)
            start = right[L - 1] + (gap + 10 * n_in if L == 1 else gap)
            ox[L] = (start + need_l + 9) // 10 * 10
            left[L], right[L] = ox[L] - need_l, ox[L] + need_r
        for p in placed: p.x = ox[p.level]
        out_gap = max(60, 40 + 10 * len(c.outputs))
        out_x = right[M] + out_gap
        left[M + 1] = out_x
        # ---- shift so nothing is above the top margin
        top = min([p.y + p.comp.bounds()[1] for p in placed] + [IN_Y0 - 20])
        shift = max(0, (70 - top + 9) // 10 * 10)
        if shift:
            for p in placed: p.y += shift
            src_y = {k: v + shift for k, v in src_y.items()}
        for pl in placed:                                                          # parts the user dragged keep their place
            if pl.comp.pos: pl.x, pl.y = pl.comp.pos
        # ---- pins and obstacles
        ports, rects, sources, sinks, reserved = {}, [], {}, [], {}
        ipos, opos = {}, {}
        for pin in ins:
            pos = pin.pos or (IN_X, src_y[pin.name]); ipos[pin.name] = pos; ports[pos] = pin.name; sources[pin.name] = (0, pos)
            rects.append(((pos[0] - pin_box_width(pin.width) - 60) // 10 * 10, pos[1] - 10, pos[0], pos[1] + 10))   # the pin box and its label
            for k in (10, 20): reserved[(pos[0] + k, pos[1])] = pin.name
        bottom = max([src_y[p.name] for p in ins], default=0)
        for pl in placed:
            x0, y0, x1, y1 = pl.comp.body()
            pt = pb = 10                                      # wires keep one grid step away from the top and bottom of a part...
            if pl.comp.facing != "east":                      # ...except where a turned part has a pin on that edge
                ps = pl.comp.all_ports()
                pt = 0 if any(p.dy <= y0 for p in ps) else 10; pb = 0 if any(p.dy >= y1 for p in ps) else 10
            rects.append(((pl.x + x0) // 10 * 10, (pl.y + y0 - pt) // 10 * 10, -(-(pl.x + x1) // 10) * 10, -(-(pl.y + y1 + pb) // 10) * 10))      # on the 10-grid (turned bodies can be 5 off)
            bottom = max(bottom, pl.y + pl.comp.bounds()[3])
            for p in pl.comp.all_ports():             # unused pins are obstacles too: a wire passing over one would join it
                pos = pl.pin(p)
                if (pl.comp.ins if p.direction == "in" else pl.comp.outs).get(p.name) is None:
                    ports.setdefault(pos, f"~{pl.comp.id}.{p.name}")
            for p in pl.comp.active_ports():
                pos = pl.pin(p)
                sig = (pl.comp.ins if p.direction == "in" else pl.comp.outs).get(p.name)
                if sig is None: continue
                ports[pos] = sig
                dx, dy = SIDE_STEP[p.side]
                for k in (1, 2): reserved.setdefault((pos[0] + dx * k, pos[1] + dy * k), sig)
                if p.direction == "out": sources[sig] = (pl.level, pos)
                else: sinks.append((sig, pl.level, pos))
        out_y, used = {}, []
        for o in c.outputs:
            y = src_y[o.name]
            while any(abs(y - u) < 40 for u in used): y += 10
            used.append(y); out_y[o.name] = y
            pos = o.pos or (out_x, y); opos[o.name] = pos; ports[pos] = o.name; sinks.append((o.name, M + 1, pos))
            rects.append((pos[0], pos[1] - 10, -(-(pos[0] + pin_box_width(o.width) + 60) // 10) * 10, pos[1] + 10))
            for k in (10, 20): reserved[(pos[0] - k, pos[1])] = o.name
        bottom = max([bottom] + used)
        lane0 = (bottom + 9) // 10 * 10 + 40
        topb = min([r[1] for r in rects] + [IN_Y0]) - 60
        bounds = (IN_X - 20, topb // 10 * 10, out_x + 40, lane0 + 150 + 6 * len(sinks))
        if any(pl.comp.pos or pl.comp.facing != "east" for pl in placed) or any(p.pos for p in ins + c.outputs):             # parts dragged outside the usual area: let the wires go around them
            bounds = (min(bounds[0], min(r[0] for r in rects) - 40) // 10 * 10, bounds[1], max(bounds[2], max(r[2] for r in rects) + 40) // 10 * 10, max(bounds[3], max(r[3] for r in rects) + 60))
        if rough:                                                    # guide lines: source -> channel left of the pin -> pin
            segs = []
            for net, col, dst in sinks:
                scol, spt = sources[net]; xc = max(spt[0] + 10, right.get(col - 1, IN_X) + 10) // 10 * 10
                for a, b in ((spt, (xc, spt[1])), ((xc, spt[1]), (xc, dst[1])), ((xc, dst[1]), dst)):
                    if a != b: segs.append(norm(a, b) + (net,))
            lay = Layout(parts=placed, wires=segs, rough=True)
            lay.inputs = [(p, *ipos[p.name]) for p in ins]; lay.outputs = [(o, *opos[o.name]) for o in c.outputs]
            return lay
        # ---- wires
        fixed = {}
        if self.use_wires:
            for net, segs in c.wires.items():
                segs = [tuple(x) for x in segs]
                if valid_route(net, segs, ports, rects) and not any(touch(a, b) for o in fixed.values() for a in segs for b in o): fixed[net] = segs
        router, last = None, ""
        for attempt in range(40 if not maze else 4):
            if deadline and time.time() > deadline: break
            order_ = list(sinks)
            if attempt: random.Random(attempt).shuffle(order_)
            try:
                if maze:
                    router = MazeRouter(ports, rects, bounds, deadline or time.time() + 8, reserved)
                    if len(sinks) > 120: router.hw = 3 if len(sinks) > 500 else 2          # big circuit: greedier search keeps the time reasonable
                else: router = RailRouter(ports, rects, step); router.deadline = deadline
                for net, segs in fixed.items():
                    for sg in segs: router._add(sg, net)
                for net, col, dst in order_:
                    if net in fixed: continue
                    scol, spt = sources[net]
                    router.route(net, spt, dst, right.get(col - 1, IN_X), left.get(scol + 1, out_x), lane0, asc=attempt % 2 == 1)
                router.segs = merge_collinear(router.segs)      # what Logisim will actually see
                check_connectivity(ports, router.segs)
                break
            except ValueError as e:
                router = None; last = str(e)
        if router is None:
            raise ValueError("Could not draw this circuit without ambiguous wires; try a smaller circuit" + (f" [{last}]" if last else ""))
        lay = Layout(parts=placed, wires=list(router.segs), fixed=set(fixed))
        lay.inputs = [(p, *ipos[p.name]) for p in ins]
        lay.outputs = [(o, *opos[o.name]) for o in c.outputs]
        return lay
