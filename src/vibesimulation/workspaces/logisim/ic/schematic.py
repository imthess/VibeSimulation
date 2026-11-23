"""The "IC view": the circuit redrawn the way you would build it from chips in Logisim - inputs on the left, the chips in
columns by logic depth, outputs on the right - with every wire placed automatically.

``layout(plan)`` places the chips and routes the wires, ``draw`` paints it through a ``Renderer`` (Tk canvas or Pillow), so
screen and PNG match.  Wire colours follow the live values like Logisim: bright green = 1, dark green = 0, blue = unknown.
"""
import math
from dataclasses import dataclass, field

from vibesimulation.common.render import OUTLINE

from vibesimulation.workspaces.logisim.ic.mapper import GND, TIES, VCC

PIN_DY = 26                  # distance between two pins of a chip (Logisim's chips use 20, too)
CHIP_W = 44                  # width of a chip body in the IC view (like Logisim's TTL chips)
XRAY_W = 210                 # width of a chip body in the X-ray view (room for the gates inside)
XRAY_DY = 34                 # pin distance in the X-ray view
BODY_W = 92                  # width of a function block (a part without a 74xx chip)
BLOCK_DY = 15
PAD = 24                     # space left and right of a body for the power ties
PINW = 4                     # half the size of a pin square
LANE = 7                     # distance between two vertical wires in a channel
ROW_GAP = 30
TOP = 30                     # space for the title above a chip
INK, SOFT = "#e5e7eb", "#9ca3af"
BODY, BODY_EDGE, PINC = "#4a4d55", "#15161a", "#d4d4d8"
ON, OFF, UNK = "#22c55e", "#15803d", "#3b82f6"
PWR_RED, PWR_BLUE = "#ef4444", "#60a5fa"


@dataclass
class Pin:
    key: str                  # chip pin number or external pin name
    side: str                 # "L" or "R"
    dy: float                 # offset from the top of the node
    net: object
    out: bool
    text: str = ""            # name written inside the body
    num: str = ""


@dataclass
class Node:
    kind: str                 # chip, block, in, out
    ref: str
    title: str
    w: float
    h: float
    pins: list
    col: int = 0
    x: float = 0
    y: float = 0
    ext: object = None        # the External (terminals, blocks)
    chip: object = None       # the ChipInst
    top: float = 0            # body top / bottom, measured from y
    bot: float = 0
    pitch: float = PIN_DY
    xray: bool = False


@dataclass
class Wire:
    net: object
    name: str
    nid: int
    segs: list                # polylines [(x, y), ...]
    dots: list                # junction dots


@dataclass
class Schematic:
    plan: object
    nodes: list
    wires: list
    pin_xy: dict              # (ref, pin key) -> stub end (x, y)
    width: float
    height: float
    nid_of: dict = field(default_factory=dict)
    xray: bool = False
    x0: float = 0
    y0: float = 0

    def extent(self): return (self.x0, self.y0, self.width, self.height)

    def node(self, ref): return next((n for n in self.nodes if n.ref == ref), None)


def _is_gate(cat):
    from vibesimulation.workspaces.logisim.ic import xray as X
    return X.is_gate_chip(cat)


def _chip_node(ch, xray=False):
    cat = ch.chip; n = cat.pins; half = n // 2
    pitch = (XRAY_DY if _is_gate(cat) else 24) if xray else PIN_DY
    w = XRAY_W if xray else CHIP_W
    pins = []
    for p in range(1, n + 1):
        left = p <= half
        dy = TOP + pitch / 2 + ((p - 1) if left else (n - p)) * pitch
        kind = cat.pin_kind(p)
        pins.append(Pin(str(p), "L" if left else "R", dy, ch.pins.get(p), kind in ("out", "io"), cat.pin_name(p), str(p)))
    return Node("chip", ch.ref, f"{ch.ref}", w, TOP + half * pitch + 20, pins, chip=ch, top=TOP, bot=TOP + half * pitch, pitch=pitch, xray=xray)


def _block_node(e):
    ins = [k for k in e.pins if k not in e.outs]; outs = [k for k in e.pins if k in e.outs]
    rows = max(len(ins), len(outs), 1)
    pins = []
    for i, k in enumerate(ins): pins.append(Pin(k, "L", TOP + 10 + i * BLOCK_DY, e.pins[k], False, k))
    for i, k in enumerate(outs): pins.append(Pin(k, "R", TOP + 10 + i * BLOCK_DY, e.pins[k], True, k))
    return Node("block", e.ref, e.label if len(e.label) < 26 else e.label[:24] + "…", BODY_W, TOP + 20 + rows * BLOCK_DY, pins, ext=e, top=TOP - 6, bot=TOP + 14 + rows * BLOCK_DY - 6, pitch=BLOCK_DY)


def layout(plan, xray=False, order=None, pos=None):
    """order: ref -> sort key (what the user dragged); chips of a column are stacked in that order."""
    order = order or {}
    nodes = [_chip_node(c, xray) for c in plan.chips] + [_block_node(e) for e in plan.externals if e.kind in ("block", "display_cc", "display_ca")]
    terms_in = [e for e in plan.externals if e.kind in ("switch", "clock")]
    terms_out = [e for e in plan.externals if e.kind == "led"]
    for e in terms_in:
        nodes.append(Node("in", e.ref, "clk" if e.kind == "clock" else e.label.replace("Input ", ""), 44, 20, [Pin("out", "R", 10, e.pins["out"], True)], col=-1, ext=e))
    for e in terms_out:
        nodes.append(Node("out", e.ref, e.label.replace("Output ", "").replace("LED ", ""), 44, 20, [Pin("anode", "L", 10, e.pins["anode"], False)], ext=e))
    body = [n for n in nodes if n.kind in ("chip", "block")]
    nets_of = {}
    for n in nodes:
        for p in n.pins:
            if p.net is not None and p.net not in TIES: nets_of.setdefault(p.net, []).append((n, p))

    # ---- columns: a chip sits one column right of the chips that drive it
    depth = {n.ref: 0 for n in body}
    drivers = {}
    for net, ends in nets_of.items():
        for n, p in ends:
            if p.out and n.kind in ("chip", "block"): drivers.setdefault(net, set()).add(n.ref)
    for _ in range(len(body) + 1):
        moved = False
        for n in body:
            for p in n.pins:
                if p.out or p.net not in drivers: continue
                d = max((depth[r] for r in drivers[p.net] if r != n.ref), default=-1) + 1
                if d > depth[n.ref] and d <= len(body): depth[n.ref] = d; moved = True
        if not moved: break
    ncols = max(depth.values(), default=0) + 1
    for n in body: n.col = depth[n.ref]
    for n in nodes:
        if n.kind == "out": n.col = ncols

    # ---- every pin's lead runs out into the channel beside its chip; a net that touches several channels is joined by a bus above
    def channel(n, p):
        if n.kind == "in": return -1
        if n.kind == "out": return ncols - 1
        return n.col - 1 if p.side == "L" else n.col
    groups = {}                                              # net -> {channel: [(node, pin)]}
    for net, ends in nets_of.items():
        if len(ends) < 2: continue
        g = {}
        for n, p in ends: g.setdefault(channel(n, p), []).append((n, p))
        groups[net] = g
    count = {}
    for net, g in groups.items():
        for ch in g: count[ch] = count.get(ch, 0) + 1
    multi = [net for net, g in groups.items() if len(g) > 1]
    bus_h = len(multi) * 6 + (14 if multi else 0)

    # ---- positions
    colw = {}
    for n in body: colw[n.col] = max(colw.get(n.col, 0), n.w)
    xs = {}; x = 14.0
    xs["in"] = x + 20; x += 44 + 40
    chan_x = {}
    for ch in range(-1, ncols):
        chan_x[ch] = x; x += count.get(ch, 0) * LANE + 36
        if ch < ncols - 1: xs[ch + 1] = x; x += colw.get(ch + 1, BODY_W) + 2 * PAD
    xs["out"] = x; x += 44 + 20
    width = x + 10
    cols = {}
    for n in nodes: cols.setdefault(n.col, []).append(n)
    height = 40.0
    for c, ns in cols.items():
        y = 24.0 + bus_h
        ns.sort(key=lambda n: order.get(n.ref, 1e9))          # (python's sort is stable: the automatic order stays where nothing was dragged)
        for n in ns:
            n.y = y; y += n.h + ROW_GAP
        height = max(height, y)
    for n in nodes:
        n.x = xs["in"] if n.kind == "in" else xs["out"] if n.kind == "out" else xs[n.col] + PAD
    for kind in ("in", "out"):                               # terminals keep the order of the circuit (A, B, C ...), top to bottom
        y = 24.0 + bus_h
        for n in [n for n in nodes if n.kind == kind]:
            n.y = y; y += 30
        height = max(height, y)
    height += 20

    # ---- wires
    pin_xy = {}
    for n in nodes:
        for p in n.pins:
            if n.kind == "in": pin_xy[(n.ref, p.key)] = (n.x + n.w + 10, n.y + p.dy)
            elif n.kind == "out": pin_xy[(n.ref, p.key)] = (n.x - 10, n.y + p.dy)
            else: pin_xy[(n.ref, p.key)] = ((n.x - PINW - 1) if p.side == "L" else (n.x + n.w + PINW + 1), n.y + p.dy)
    nid_of = {net: i for i, net in enumerate(sorted(nets_of, key=str))}
    lane_of = {}                                             # (channel, net) -> lane, ordered by height to cross as little as possible
    for ch in range(-1, ncols):
        here = [net for net, g in groups.items() if ch in g]
        here.sort(key=lambda net: sum(pin_xy[(n.ref, p.key)][1] for n, p in groups[net][ch]) / len(groups[net][ch]))
        for k, net in enumerate(here): lane_of[(ch, net)] = k
    bus_y = {net: 14 + k * 6 for k, net in enumerate(multi)}
    wires = []
    for net, g in groups.items():
        segs, dots, trunks = [], [], []
        for ch, ends in g.items():
            xt = chan_x[ch] + 18 + lane_of[(ch, net)] * LANE
            ys = [pin_xy[(n.ref, p.key)][1] for n, p in ends]
            lo, hi = min(ys), max(ys)
            if net in bus_y: lo = min(lo, bus_y[net])
            if hi > lo: segs.append([(xt, lo), (xt, hi)])
            for (n, p), y in zip(ends, ys):
                segs.append([(pin_xy[(n.ref, p.key)][0], y), (xt, y)])
                if lo < y < hi: dots.append((xt, y))
            trunks.append(xt)
        if net in bus_y and len(trunks) > 1:
            segs.append([(min(trunks), bus_y[net]), (max(trunks), bus_y[net])])
            for xt in sorted(trunks)[1:-1]: dots.append((xt, bus_y[net]))
        wires.append(Wire(net, plan.name(net), nid_of[net], segs, dots))
    sch = Schematic(plan, nodes, wires, pin_xy, width, height + 0, nid_of, xray)
    if pos: _apply_moves(sch, pos, nets_of)
    return sch


def _apply_moves(sch, pos, nets_of):
    """Chips and terminals the user dragged: they go where they were put, and every wire that touches one is routed again by a simple
    router (a lane beside the driving pin).  The other wires keep their tidy channel routes."""
    moved = set()
    for n in sch.nodes:
        if n.ref in pos:
            nx, ny = pos[n.ref]
            if (nx, ny) != (n.x, n.y):
                dx, dy = nx - n.x, ny - n.y; n.x, n.y = nx, ny; moved.add(n.ref)
                for p in n.pins:
                    x, y = sch.pin_xy[(n.ref, p.key)]; sch.pin_xy[(n.ref, p.key)] = (x + dx, y + dy)
    if not moved: return
    for i, w in enumerate(sch.wires):
        ends = nets_of.get(w.net, [])
        if not any(n.ref in moved for n, _p in ends): continue
        drv = next(((n, p) for n, p in ends if p.out), ends[0])
        dx0, dy0 = sch.pin_xy[(drv[0].ref, drv[1].key)]
        right = drv[1].side == "R" if drv[0].kind in ("chip", "block") else drv[0].kind == "in"
        tx = dx0 + (14 if right else -14) + 5 * (w.nid % 5) * (1 if right else -1)
        ys = [sch.pin_xy[(n.ref, p.key)][1] for n, p in ends]
        segs, dots = [], []
        if max(ys) > min(ys): segs.append([(tx, min(ys)), (tx, max(ys))])
        for (n, p), y in zip(ends, ys):
            segs.append([(sch.pin_xy[(n.ref, p.key)][0], y), (tx, y)])
            if min(ys) < y < max(ys): dots.append((tx, y))
        sch.wires[i] = Wire(w.net, w.name, w.nid, segs, dots)
    sch.x0 = min(0, min(n.x - 60 for n in sch.nodes)); sch.y0 = min(0, min(n.y - 30 for n in sch.nodes))
    sch.width = max(sch.width, max(n.x + n.w + 60 for n in sch.nodes)); sch.height = max(sch.height, max(n.y + n.h + 30 for n in sch.nodes))


def _want_y(n, nets_of):
    ys = []
    for p in n.pins:
        for o, q in nets_of.get(p.net, []):
            if o is not n and o.kind in ("chip", "block"): ys.append(o.y + q.dy)
    return sum(ys) / len(ys) if ys else n.y


# =====================================================================================================================
def net_color(v):
    return ON if v == 1 else OFF if v == 0 else UNK


def draw(r, sch, value=None, sel=None, hot=None):
    """value(net) -> 0 / 1 / None gives the live colour; sel is the number of the highlighted net; hot the net whose pins get a yellow ring."""
    value = value or (lambda net: None)
    for n in sch.nodes:
        if n.kind == "chip": _chip(r, sch, n, value, hot)
        elif n.kind == "block": _block(r, sch, n, value)
        else: _terminal(r, n, value)
    for w in sch.wires:
        v = value(w.net); col = net_color(v) if v is not None else UNK
        tags = ("wire", f"net:{w.nid}")
        hot_w = sel is not None and w.nid == sel
        for s in w.segs:
            if hot_w: r.line(s, 6, "#facc15", tags)
            r.line(s, 2.4, col, tags)
        for d in w.dots: r.circle(d[0], d[1], 2.8, col, col, 0.5, tags)
    for n in sch.nodes:                                                  # short leads on the pins of a chip
        if n.kind not in ("chip", "block"): continue
        for p in n.pins:
            if p.net is None or p.net in TIES: continue
            x, y = sch.pin_xy[(n.ref, p.key)]; edge = n.x if p.side == "L" else n.x + n.w
            r.line([(edge, y), (x, y)], 2.4, net_color(value(p.net)) if value(p.net) is not None else UNK)


def tie_paths(sch, n):
    """[(rail, polyline)]: every pin of chip n that is tied to VCC or GND is wired to the ONE VCC / GND pin of the chip (never a symbol per pin)."""
    ch = n.chip; out = []
    if ch is None: return out
    cat = ch.chip; body_top, body_bot = n.y + n.top - 7, n.y + n.bot + 7
    for rail, pin in ((VCC, cat.vcc), (GND, cat.gnd)):
        pw = next(p for p in n.pins if p.key == str(pin)); sx, sy = sch.pin_xy[(n.ref, pw.key)]
        def lane(side, k): return (n.x - PINW - 1 - 5 - k * 5) if side == "L" else (n.x + n.w + PINW + 1 + 5 + k * 5)
        k = 0 if rail == GND else 1
        for p in n.pins:
            if p.net != rail or p.key == pw.key: continue
            tx, ty = sch.pin_xy[(n.ref, p.key)]
            lx, px = lane(p.side, k), lane(pw.side, k)
            pts = [(tx, ty), (lx, ty)]
            if p.side != pw.side:                                       # round the top (VCC) or the bottom (GND) of the chip to the other side
                yv = body_top - 3 * k if rail == VCC else body_bot + 3 * k
                pts += [(lx, yv), (px, yv)]
            pts += [(px, sy), (sx, sy)]
            out.append((rail, pts))
    return out


def _vcc_gnd_marks(r, n, x0, x1):
    """Logisim's tiny VCC / GND marks beside the two power pins: one of each on the whole chip, nowhere else."""
    cat = n.chip.chip
    for text, pin in (("VCC", cat.vcc), ("GND", cat.gnd)):
        p = next(q for q in n.pins if q.key == str(pin))
        r.rtext(x0 + 7 if p.side == "L" else x1 - 7, n.y + p.dy, text, 5, "#d1d5db", False)


def _chip(r, sch, n, value, hot):
    """A chip drawn like Logisim's TTL parts: dark body, a notch at the top, a square on every pin, the part number turned on its side."""
    ch = n.chip; plan = sch.plan
    x0, x1, y0, y1 = n.x, n.x + n.w, n.y + n.top, n.y + n.bot
    r.rect(x0, y0, x1, y1, BODY, BODY_EDGE, 1.6, ("node", f"node:{n.ref}"))
    cx = x0 + n.w / 2
    r.polygon([(cx + 5 * math.cos(t * math.pi / 10), y0 + 5 * math.sin(t * math.pi / 10)) for t in range(0, 11)], "#15161a", "#15161a", 0.5)      # the notch
    r.text(x0 + n.w / 2, y0 - 8, n.title, 9, OUTLINE, True, "c")
    if not n.xray:
        r.rtext(x0 + n.w / 2, (y0 + y1) / 2, ch.part, 13, "#ffffff", True, ("node", f"node:{n.ref}"))
        _vcc_gnd_marks(r, n, x0, x1)
    else:
        from vibesimulation.workspaces.logisim.ic import xray as X
        X.draw_inside(r, sch, n, value)
        r.text(x0 + n.w / 2, y1 + 11, f"{ch.part}  ·  {ch.chip.title if len(ch.chip.title) < 44 else ch.chip.title[:42] + '…'}", 10, OUTLINE, True, "c")
    for p in n.pins:
        edge = x0 if p.side == "L" else x1; y = n.y + p.dy
        tie = p.net in TIES
        col = PWR_RED if p.net == VCC else PWR_BLUE if p.net == GND else None
        same = hot is not None and p.net == hot and not tie
        ring = (ch.ref, int(p.key)) in plan.edited
        r.rect(edge - PINW, y - PINW, edge + PINW, y + PINW, "#facc15" if same else (col if (tie and p.key not in (str(ch.chip.vcc), str(ch.chip.gnd))) else PINC),
               "#f97316" if ring else "#facc15" if same else "#6b7280", 2.2 if (ring or same) else 0.8, ("pin", f"pin:{ch.ref}:{p.key}"))
        if n.xray: r.text(edge + (9 if p.side == "L" else -9), y, p.key, 6.5, "#e5e7eb", True, "w" if p.side == "L" else "e", ("pin", f"pin:{ch.ref}:{p.key}"))
    if ch.used() < len(ch.slots):
        r.text(x0 + n.w / 2, y1 + (27 if n.xray else 12), f"{ch.used()}/{len(ch.slots)} gates used", 8.5, "muted", False, "n")


def _block(r, sch, n, value):
    x0, y0, x1, y1 = n.x, n.y + n.top, n.x + n.w, n.y + n.bot
    fill = "#fde68a" if n.ext.kind == "block" else "#e4e4e7"
    r.rect(x0, y0, x1, y1, fill, BODY_EDGE, 1.3, ("node", f"node:{n.ref}"))
    r.text((x0 + x1) / 2, y0 - 8, n.title, 8.5, OUTLINE, True, "c")
    for p in n.pins:
        edge = x0 if p.side == "L" else x1; x, y = sch.pin_xy[(n.ref, p.key)]
        r.rect(edge - 3.5, n.y + p.dy - 3.5, edge + 3.5, n.y + p.dy + 3.5, PINC, "#52525b", 0.8, ("pin", f"pin:{n.ref}:{p.key}"))
        r.text(edge + (6 if p.side == "L" else -6), n.y + p.dy, p.text, 6.5, "#111827", False, "w" if p.side == "L" else "e")


MUTED_LABEL = "#9ca3af"


def _terminal(r, n, value):
    e = n.ext; v = value(e.pins["out" if n.kind == "in" else "anode"])
    x0, y0, x1, y1 = n.x, n.y, n.x + n.w, n.y + n.h
    if n.kind == "in":
        r.rect(x0, y0, x1 - 6, y1, "#e4e4e7", "#52525b", 1.3, ("ext", f"ext:{n.ref}"))
        r.line([(x1 - 6, y0), (x1, y0 + 10), (x1 - 6, y1)], 1.3, "#52525b")
        r.text(x0 - 4, y0 + 10, n.title, 8.5, OUTLINE, True, "e")
    else:
        r.rect(x0 + 6, y0, x1, y1, "#e4e4e7", "#52525b", 1.3, ("ext", f"ext:{n.ref}"))
        r.line([(x0 + 6, y0), (x0, y0 + 10), (x0 + 6, y1)], 1.3, "#52525b")
        r.text(x1 + 4, y0 + 10, n.title, 8.5, OUTLINE, True, "w")
    r.text((x0 + x1) / 2 - (3 if n.kind == "in" else -3), y0 + 10, "—" if v is None else str(v), 9, ON if v == 1 else "#3f3f46", True, "c")


def to_png(sch, value=None, scale=1.5):
    from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
    im, d, tf = canvas(sch.extent(), scale, 12, "#f4f4f5")
    draw(PilRenderer(d, tf, scale, LIGHT), sch, value)
    return im
