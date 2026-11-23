"""The X-ray view: every package drawn as the datasheet draws it, opened up so you can see the gates (or the function
blocks) inside and which signal arrives on every pin.  Every pin is clickable (tag ``pin:REF:N``) so the wiring can be
changed; rewired pins get an orange ring.  Figures such as "Digital gates in IC packages" (7400, 7402, 7404 ... 7486) and
the 7483 pin sheet are drawn from the same catalogue data, so what you see is what the mapper uses.
"""
from vibesimulation.common.render import MUTED, OUTLINE
from vibesimulation.workspaces.logisim.ic.mapper import GND, VCC

PW = 34                     # pin pitch
MARGIN = 18
GATE_FUNCS = ("AND", "NAND", "OR", "NOR", "XOR", "XNOR", "NOT", "BUF")
BODY, EDGE = "#f5f1e6", "#3f3a2c"
GATE_FILL, GATE_EDGE = "#e8e2cf", "#4b4636"
WIRE_USED, WIRE_UNUSED = "#0f766e", "#b8b2a0"
INK, SOFT = "#1f2937", "#6b7280"
PIN_IN, PIN_OUT, PIN_VCC, PIN_GND, PIN_NC = "#ffffff", "#99f6e4", "#fca5a5", "#93c5fd", "#e5e7eb"
HOT, EDITED = "#facc15", "#f97316"


def _kind(func):
    for k in sorted(GATE_FUNCS, key=len, reverse=True):
        if func.startswith(k) and func[len(k):].isdigit() or func == k: return k
    return None


def is_gate_chip(cat):
    return bool(cat.units) and all(_kind(u.func) for u in cat.units)


def size(ch):
    cat = ch.chip; half = cat.pins // 2
    return half * PW + 2 * MARGIN, (350 if is_gate_chip(cat) and cat.units[0].func != "NAND8" else 290)


# ---------------------------------------------------------------- gate symbols
def _arc(cx, cy, rx, ry, a0, a1, n=12):
    import math
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _bez(p0, p1, p2, n=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def gate_height(n): return max(36, 11 * n + 8)


def draw_gate(r, kind, n, x, y, w=46):
    """Draw a gate with its top-left corner at (x, y).  Returns ([input points], output point)."""
    h = gate_height(n if kind not in ("NOT", "BUF") else 1) if kind not in ("NOT", "BUF") else 32
    inv = kind in ("NAND", "NOR", "XNOR", "NOT")
    body_w = w - (7 if inv else 0)
    xo = x + body_w
    if kind in ("AND", "NAND"):
        pts = [(x, y), (x + body_w * 0.5, y)] + _arc(x + body_w * 0.5, y + h / 2, body_w * 0.5, h / 2, -90, 90) + [(x, y + h)]
    elif kind in ("OR", "NOR", "XOR", "XNOR"):
        off = 6 if kind in ("XOR", "XNOR") else 0
        a = x + off
        pts = _bez((a, y), (a + body_w * 0.55, y), (xo, y + h / 2)) + _bez((xo, y + h / 2), (a + body_w * 0.55, y + h), (a, y + h))[1:] + _bez((a, y + h), (a + body_w * 0.28, y + h / 2), (a, y))[1:]
        if off: r.line(_bez((x, y), (x + body_w * 0.28, y + h / 2), (x, y + h)), 1.6, GATE_EDGE)
    else:
        pts = [(x, y), (xo, y + h / 2), (x, y + h)]
    r.polygon(pts, GATE_FILL, GATE_EDGE, 1.6)
    out = xo
    if inv: r.circle(xo + 3.5, y + h / 2, 3.5, "#ffffff", GATE_EDGE, 1.4); out = xo + 7
    ins = [(x + (6 if kind in ("XOR", "XNOR") else 0) * 0, y + h * (i + 1) / (n + 1)) for i in range(n)] if kind not in ("NOT", "BUF") else [(x, y + h / 2)]
    for ix, iy in ins: r.line([(ix - 7, iy), (ix + (4 if kind in ("OR", "NOR", "XOR", "XNOR") else 0), iy)], 1.6, GATE_EDGE)
    return [(ix - 7, iy) for ix, iy in ins], (out, y + h / 2), h


# ---------------------------------------------------------------- the package
def draw_chip(r, plan, ch, x, y, hot=None, hover=None):
    """Draw one package with its top-left corner at (x, y). ``hot``: net to highlight."""
    cat = ch.chip; n = cat.pins; half = n // 2
    W, H = size(ch)
    top_net, bot_net = y + 78, y + H - 78                  # y of the pin squares' centres
    yb0, yb1 = y + 64, y + H - 64                          # body
    r.text(x + MARGIN, y + 10, f"{ch.ref}  {cat.part}", 12, OUTLINE, True, "w")
    r.text(x + MARGIN, y + 26, cat.title if len(cat.title) < 60 else cat.title[:58] + "…", 8.5, MUTED, False, "w")
    r.rect(x + MARGIN - 8, yb0 + 10, x + W - MARGIN + 8, yb1 - 10, BODY, EDGE, 2)
    r.polygon(_arc(x + MARGIN - 8, (yb0 + yb1) / 2, 9, 9, -90, 90), "#d9d3c0", EDGE, 1.5)            # the notch on the left
    px = {}
    for p in range(1, n + 1):
        px[p] = x + MARGIN + ((p - 0.5) * PW if p <= half else (n - p + 0.5) * PW)
    py = lambda p: (bot_net if p <= half else top_net)

    used_in = {}                                           # pin -> unit used?
    for i, u in enumerate(cat.units):
        live = i < len(ch.slots) and ch.slots[i] is not None
        for role, pin in u.pins:
            for q in (pin if isinstance(pin, tuple) else (pin,)): used_in[q] = live
    for role, pin in cat.common: used_in[pin] = any(s is not None for s in ch.slots) if ch.slots else True

    # ---- inside: gates, or one function block
    if is_gate_chip(cat): _gates(r, cat, ch, px, py, x, W, yb0 + 10, yb1 - 10, used_in)
    else: _block(r, cat, ch, px, py, x, W, yb0 + 10, yb1 - 10, used_in)

    # ---- pins, their numbers and the signals on them
    for p in range(1, n + 1):
        kind = cat.pin_kind(p); net = ch.pins.get(p)
        top = p > half
        cy = top_net if top else bot_net
        fill = PIN_VCC if kind == "vcc" else PIN_GND if kind == "gnd" else PIN_NC if kind == "nc" else PIN_OUT if kind in ("out", "io") else PIN_IN
        same = hot is not None and net == hot and net not in (VCC, GND, None)
        ring = (ch.ref, p) in plan.edited
        tags = ("pin", f"pin:{ch.ref}:{p}")
        edge = EDITED if ring else HOT if same else EDGE
        r.rect(px[p] - 11, cy - 10, px[p] + 11, cy + 10, HOT if same else fill, edge, 3 if (ring or same) else 1.3, tags)
        r.text(px[p], cy, str(p), 9, INK, True, "c", tags)
        label = "NC" if kind == "nc" else "–" if net is None else "+5V" if net == VCC else "GND" if net == GND else plan.name(net)
        if kind == "nc": label = ""
        label = label if len(label) <= 8 else label[:7] + "…"
        off = 16 + (0 if p % 2 else 11)
        ty = cy - 10 - off if top else cy + 10 + off
        col = "#b91c1c" if net == VCC else "#1d4ed8" if net == GND else EDITED if ring else INK
        r.text(px[p], ty, label, 8, col, True, "c", tags)
    return W, H


def _gates(r, cat, ch, px, py, x0, W, ytop, ybot, used_in):
    n = cat.pins; half = n // 2
    rows = {"top": [], "bot": []}
    for i, u in enumerate(cat.units):
        d = dict(u.pins); ins = d["in"]; out = d["out"]
        pins = list(ins) + [out]
        side = "bot" if sum(1 for p in pins if p <= half) * 2 >= len(pins) else "top"
        rows[side].append((i, u, ins, out, sum(px[p] for p in pins) / len(pins)))
    for side, items in rows.items():
        items.sort(key=lambda t: t[4])
        cy = (ybot - 70) if side == "bot" else (ytop + 70)
        placed = []
        for i, u, ins, out, gx in items:
            kind = _kind(u.func); nin = 1 if kind in ("NOT", "BUF") else len(ins)
            gw = 46; gx = max(gx - gw / 2, (placed[-1] + 84) if placed else x0 + MARGIN + 36)
            placed.append(gx)
            h = 32 if nin == 1 else gate_height(nin)
            gy = cy - h / 2
            live = i < len(ch.slots) and ch.slots[i] is not None
            col = WIRE_USED if live else WIRE_UNUSED
            ipts, opt, _h = draw_gate(r, kind, nin, gx, gy, gw)
            # leads to the pins: in -> gate input, gate output -> pin
            for k, p in enumerate(ins if nin == len(ins) else ins[:1]):
                _lead(r, px[p], py(p), ipts[k], "in", side, k, col, p > half)
            _lead(r, px[out], py(out), opt, "out", side, 0, col, out > half)
            r.text(gx + gw / 2 - 3, gy - 7, f"{u.func}  #{i + 1}", 7, SOFT if live else "#a3a3a3", False, "c")
            if not live: r.text(gx + gw / 2 - 3, gy + h + 9, "unused", 7, "#a3a3a3", False, "c")
            else:
                c = ch.slots[i]
                if c.origin: r.text(gx + gw / 2 - 3, gy + h + 9, "for " + c.origin, 7, WIRE_USED, True, "c")


def _lead(r, pxp, pyp, pt, kind, side, k, col, pin_top):
    """Orthogonal lead between a pin square (centre pxp, pyp) and a gate terminal pt: out of the pin, along a lane, round to the gate."""
    start = pyp + 10 if pin_top else pyp - 10
    lane = (pyp + 20 + 5 * k) if pin_top else (pyp - 20 - 5 * k)
    xl = pt[0] - 8 - 4 * k if kind == "in" else pt[0] + 8 + 4 * k
    pts = [(pxp, start), (pxp, lane), (xl, lane), (xl, pt[1]), pt]
    r.line(pts, 2, col)


def _block(r, cat, ch, px, py, x0, W, ytop, ybot, used_in):
    """Functional block (counter, adder, flip-flop ...): lines from the pins into a box with the pin functions written inside."""
    bx0, bx1 = x0 + MARGIN, x0 + W - MARGIN
    by0, by1 = ytop + 30, ybot - 30
    r.rect(bx0, by0, bx1, by1, "#ffffff", EDGE, 1.6)
    half = cat.pins // 2
    r.text((bx0 + bx1) / 2, (by0 + by1) / 2 - 8, cat.part, 16, INK, True, "c")
    subtitle = cat.title if len(cat.title) < 48 else cat.title[:46] + "…"
    r.text((bx0 + bx1) / 2, (by0 + by1) / 2 + 12, subtitle, 9, SOFT, False, "c")
    for p in range(1, cat.pins + 1):
        kind = cat.pin_kind(p)
        if kind == "nc": continue
        top = p > half
        live = used_in.get(p, True)
        col = WIRE_USED if live else WIRE_UNUSED
        y_pin = ytop if top else ybot
        y_blk = by0 if top else by1
        r.line([(px[p], y_pin), (px[p], y_blk)], 2, col)
        r.text(px[p], y_blk + (11 if top else -11), cat.pin_name(p), 7.5, INK, False, "c")


def to_png(plan, cols=2, scale=1.6, hot=None):
    """Pillow image with every package opened up."""
    from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
    chips = plan.chips
    if not chips: return None
    cols = max(1, min(cols, len(chips))); gap = 16
    rows = [chips[i:i + cols] for i in range(0, len(chips), cols)]
    colw = max(size(c)[0] for c in chips)
    heights = [max(size(c)[1] for c in row) for row in rows]
    im, d, tf = canvas((0, 0, cols * (colw + gap) + gap, sum(heights) + gap * (len(rows) + 1)), scale, 6, "#ffffff")
    r = PilRenderer(d, tf, scale, LIGHT); y = gap
    for row, h in zip(rows, heights):
        for i, ch in enumerate(row): draw_chip(r, plan, ch, gap + i * (colw + gap), y, hot)
        y += h + gap
    return im


# ================================================================ inside a chip of the circuit (the X-ray view of the whole circuit)
class _Flip:
    """Draws through another renderer with x turned about ``cx`` (a gate that faces left)."""
    def __init__(self, r, cx): self.r, self.cx = r, cx

    def _p(self, pts): return [(2 * self.cx - x, y) for x, y in pts]

    def line(self, pts, width=2, role=OUTLINE, tags=()): self.r.line(self._p(pts), width, role, tags)

    def polygon(self, pts, fill=None, outline=OUTLINE, width=2, tags=()): self.r.polygon(self._p(pts), fill, outline, width, tags)

    def circle(self, cx, cy, rad, fill=None, outline=OUTLINE, width=2, tags=()): self.r.circle(2 * self.cx - cx, cy, rad, fill, outline, width, tags)


UNUSED_WIRE = "#f8fafc"                    # the inside of a gate that is not used is drawn in white


def _wire_col(value, net):
    from vibesimulation.workspaces.logisim.ic.schematic import net_color
    if net is None: return UNUSED_WIRE
    if net == VCC: return "#ef4444"
    if net == GND: return "#60a5fa"
    v = value(net)
    return net_color(v) if v is not None else "#3b82f6"


def draw_inside(r, sch, n, value):
    """The gates (or the function block) inside chip node ``n``, wired to its pins the way the datasheet draws them.
    A lead is coloured by the live value of the signal on its pin; units that are not used are grey."""
    ch = n.chip; cat = ch.chip
    if is_gate_chip(cat): _inside_gates(r, sch, n, value)
    else: _inside_block(r, sch, n, value)


def _inside_gates(r, sch, n, value):
    ch, cat = n.chip, n.chip.chip
    x0, x1 = n.x, n.x + n.w; cx = (x0 + x1) / 2
    ypin = {int(p.key): n.y + p.dy for p in n.pins}
    left = {int(p.key): p.side == "L" for p in n.pins}
    netof = {int(p.key): p.net for p in n.pins}
    for i, u in enumerate(cat.units):
        d = dict(u.pins); ins, out = list(d["in"]), d["out"]
        live = i < len(ch.slots) and ch.slots[i] is not None
        kind = _kind(u.func); nin = 1 if kind in ("NOT", "BUF") else len(ins)
        used = ins if nin == len(ins) else ins[:1]
        mirror = sum(1 for p in used if not left[p]) * 2 > len(used)          # most inputs sit on the right side: the gate faces left
        pins = list(used) + [out]
        gy_c = sum(ypin[p] for p in pins) / len(pins)
        h = 32 if nin == 1 else gate_height(nin)
        gcx = (x1 - 64) if mirror else (x0 + 64)                             # the gates of the left pins sit in the left half, those of the right pins in the right half
        gx = gcx - 26
        sink = _Flip(r, gcx) if mirror else r
        ipts, opt, _h = draw_gate(sink, kind, nin, gx, gy_c - h / 2, 46)
        fx = (lambda x: 2 * gcx - x) if mirror else (lambda x: x)
        ipts = [(fx(x), y) for x, y in ipts]; opt = (fx(opt[0]), opt[1])
        near_left = not mirror
        gtop, gbot = gy_c - h / 2, gy_c + h / 2
        sgn = 1 if near_left else -1                                         # direction from the gate towards its input side
        def edge(pin): return x0 if left[pin] else x1
        # inputs: straight in from the near side; from the far side round above the gate
        for k, (p, ip) in enumerate(zip(used, ipts)):
            col = _wire_col(value, netof[p]) if live else UNUSED_WIRE
            lane = ip[0] - sgn * (6 + 4 * k)
            pts = [(edge(p), ypin[p])]
            if left[p] == near_left: pts += [(lane, ypin[p]), (lane, ip[1]), ip]
            else:
                yd = gtop - 7 - 4 * k
                far = x1 - 14 - 4 * k if near_left else x0 + 14 + 4 * k
                pts += [(far, ypin[p]), (far, yd), (lane, yd), (lane, ip[1]), ip]
            r.line(pts, 1.8, col)
        col = _wire_col(value, netof[out]) if live else UNUSED_WIRE
        oy = opt[1]; lane = opt[0] - sgn * -(8)
        pts = [opt]
        if left[out] != near_left: pts += [(lane, oy), (lane, ypin[out]), (edge(out), ypin[out])]
        else:
            yb = gbot + 8
            far = (ipts[0][0] - sgn * (6 + 4 * len(used) + 6))
            pts += [(lane, oy), (lane, yb), (far, yb), (far, ypin[out]), (edge(out), ypin[out])]
        r.line(pts, 1.8, col)
        if live: r.text(cx, gy_c, ch.slots[i].origin or f"#{i + 1}", 8, "#e5e7eb", True, "c")


def _inside_block(r, sch, n, value):
    cat = n.chip.chip
    x0, x1 = n.x, n.x + n.w
    bx0, bx1 = x0 + 46, x1 - 46
    by0, by1 = n.y + n.top + 8, n.y + n.bot - 8
    r.rect(bx0, by0, bx1, by1, "#f5f1e6", EDGE, 1.6)
    r.text((bx0 + bx1) / 2, (by0 + by1) / 2 - 8, cat.part, 15, INK, True, "c")
    r.text((bx0 + bx1) / 2, (by0 + by1) / 2 + 10, cat.title if len(cat.title) < 30 else cat.title[:28] + "…", 7.5, SOFT, False, "c")
    for p in n.pins:
        pin = int(p.key)
        if cat.pin_kind(pin) == "nc": continue
        y = n.y + p.dy; left = p.side == "L"
        r.line([(x0 if left else x1, y), (bx0 if left else bx1, y)], 1.8, _wire_col(value, p.net))
        r.text(bx0 + 4 if left else bx1 - 4, y, cat.pin_name(pin), 6.5, INK, False, "w" if left else "e")
