"""The breadboard picture and the chip diagrams.

``layout(plan)`` decides where every chip sits on the breadboard and which wire joins which holes; ``draw`` paints it
through a ``Renderer`` (the Tk canvas on screen, Pillow for a PNG), so both look the same.

Breadboard geometry (one unit = 1/10 of the hole pitch of 2.54 mm): a chip straddles the centre gap, pin 1 at the
bottom left, pins 1..N/2 along the bottom row (f), the rest along the top row (e) from right to left.  The four free
holes above (a-d) and below (g-j) a pin share its column strip, so a wire plugs into the free hole next to the pin.
"""
from dataclasses import dataclass, field

from vibesimulation.common.render import MUTED, OUTLINE
from vibesimulation.workspaces.logisim.ic.mapper import GND, TIES, VCC

P = 10                                    # hole pitch
X0 = 64                                   # x of column 0
MAX_COLS = 60                             # columns per board row (a full-size breadboard has 63)
BOARD_H = 190                             # height of one board row
Y_RAIL_TOP = (0, 10)                      # outer (-) and inner (+) rail of the top side
Y_ROWS = {"a": 30, "b": 40, "c": 50, "d": 60, "e": 70, "f": 90, "g": 100, "h": 110, "i": 120, "j": 130}
Y_RAIL_BOT = (150, 160)                   # inner (-) and outer (+) rail of the bottom side
PANEL_H = 90                              # height of the switch / LED panels
ROW_GAP = 50

BOARD, BOARD_EDGE, HOLE, TXT = "#ebe6d6", "#b9b29a", "#8a846f", "#3b3a33"
CHIP, CHIP_EDGE, LEG = "#25262b", "#0d0d10", "#b8bcc6"
RED, BLUE = "#e11d48", "#2563eb"
WIRES = (("orange", "#f97316"), ("yellow", "#eab308"), ("green", "#16a34a"), ("blue", "#2563eb"), ("violet", "#7c3aed"),
         ("brown", "#92400e"), ("cyan", "#0891b2"), ("pink", "#db2777"), ("grey", "#6b7280"), ("lime", "#65a30d"))


@dataclass
class Wire:
    net: str
    name: str                      # display name of the net
    color: str                     # hex
    color_name: str
    a: tuple                       # endpoint description (kind, ref, pin / name)
    b: tuple
    pts: list                      # polyline in layout units
    holes: int = 0                 # rough length in holes
    nid: int = 0                   # number of the net (canvas tags cannot hold arbitrary net names)


@dataclass
class Board:
    plan: object
    chip_at: dict                  # ref -> (board row, first column)
    pin_xy: dict                   # (ref, pin) -> (x, y) of the pin
    ext_xy: dict                   # (ref, pin name) -> (x, y) of the lead
    ext_box: dict                  # ref -> (x, y) centre of the part
    wires: list
    rows: int
    cols: int
    width: float
    height: float
    top: float                     # y of the first board row
    row_y: list = field(default_factory=list)

    def extent(self): return (0, 0, self.width, self.height)


def _side(pin, n): return "bottom" if pin <= n // 2 else "top"


def layout(plan):
    chips = plan.chips
    chip_at, col, row = {}, 1, 0
    for ch in chips:
        w = ch.chip.pins // 2
        if col + w > MAX_COLS: row += 1; col = 1
        chip_at[ch.ref] = (row, col); col += w + 1
    rows = row + 1
    cols = min(MAX_COLS, max([c + plan.chip(r).chip.pins // 2 for r, (_, c) in chip_at.items()] or [10])) + 2
    def pw(e): return 36 if e.kind in ("switch", "clock", "led") else max(50, 12 + 11 * len(e.pins)) + 6
    need = max(sum(pw(e) for e in plan.externals if e.kind in g) for g in (("switch", "clock"), ("led", "display_cc", "display_ca", "block")))
    cols = max(cols, int(need / P) + 4)
    top = PANEL_H + 10
    row_y = [top + i * (BOARD_H + ROW_GAP) for i in range(rows)]
    width = X0 + cols * P + 40
    height = row_y[-1] + BOARD_H + PANEL_H + 20

    pin_xy = {}
    for ch in chips:
        r, c0 = chip_at[ch.ref]; n = ch.chip.pins; y0 = row_y[r]
        for p in range(1, n + 1):
            if p <= n // 2: x, y = X0 + (c0 + p - 1) * P, y0 + Y_ROWS["f"]
            else: x, y = X0 + (c0 + n - p) * P, y0 + Y_ROWS["e"]
            pin_xy[(ch.ref, p)] = (x, y)

    nets = plan.nets()
    # ---- external parts: switches and clocks above the first board row, LEDs / displays / blocks below the last one
    def want_x(e):
        xs = [pin_xy[(ref, p)][0] for net in e.pins.values() if net and net not in TIES for kind, ref, p in nets.get(net, []) if kind == "chip"]
        return sum(xs) / len(xs) if xs else X0
    ext_xy, ext_box = {}, {}
    for group, y_lead, y_box, sgn in ((("switch", "clock"), row_y[0] - 30, row_y[0] - 62, -1),
                                      (("led", "display_cc", "display_ca", "block"), row_y[-1] + BOARD_H + 30, row_y[-1] + BOARD_H + 62, 1)):
        es = sorted([e for e in plan.externals if e.kind in group], key=want_x)
        x = X0
        for e in es:
            w = pw(e) - 6
            x = max(x, want_x(e) - w / 2)
            cx = x + w / 2
            ext_box[e.ref] = (cx, y_box)
            names = list(e.pins)
            for k, nm in enumerate(names):
                ext_xy[(e.ref, nm)] = (cx - w / 2 + (k + 0.5) * w / len(names), y_lead)
            x += w + 6
        width = max(width, x + 30)

    # ---- wires
    used = {}                                  # (x, side) -> number of free holes in use
    wires, idx = [], [0]
    nid_of = {n: i for i, n in enumerate(sorted(nets, key=str))}

    def hole(x, y, side):
        k = used.get((x, side), 0); used[(x, side)] = k + 1
        return (x, y - P * (1 + k % 4)) if side == "top" else (x, y + P * (1 + k % 4))

    def rail_point(x, r, side, net):
        y0 = row_y[r]
        if side == "top": return (x, y0 + (Y_RAIL_TOP[1] if net == VCC else Y_RAIL_TOP[0]))
        return (x, y0 + (Y_RAIL_BOT[1] if net == VCC else Y_RAIL_BOT[0]))

    def add(net, color, cname, a, b, pa, pb, bulge):
        idx[0] += 1
        pts = [pa, pb] if bulge is None else _curve(pa, pb, bulge, idx[0])
        wires.append(Wire(net, plan.name(net), color, cname, a, b, pts, int(round(abs(pa[0] - pb[0]) / P + abs(pa[1] - pb[1]) / P)), nid_of.get(net, 0)))

    for ch in chips:                                                       # power and tied pins -> rails
        r, _ = chip_at[ch.ref]; n = ch.chip.pins
        for p in range(1, n + 1):
            net = ch.pins.get(p)
            if net not in TIES: continue
            x, y = pin_xy[(ch.ref, p)]; side = _side(p, n)
            h = hole(x, y, side)
            add(net, RED if net == VCC else "#4b5563", "red" if net == VCC else "black", ("chip", ch.ref, p), ("rail", net, ""), h, rail_point(x, r, side, net), None)
    ci = 0
    for net, ends in sorted(nets.items(), key=lambda kv: str(kv[0])):
        if net in TIES or len(ends) < 2: continue
        color, cname = WIRES[ci % len(WIRES)]; ci += 1
        pts = []
        for kind, ref, pin in ends:
            if kind == "chip":
                x, y = pin_xy[(ref, pin)]; side = _side(pin, plan.chip(ref).chip.pins)
                pts.append((x, y, side, ("chip", ref, pin), None))
            else:
                x, y = ext_xy[(ref, pin)]
                pts.append((x, y, "panel_top" if y < row_y[0] else "panel_bot", ("ext", ref, pin), (x, y)))
        pts.sort(key=lambda t: (t[0], t[1]))
        pos = []
        for x, y, side, desc, lead in pts:
            pos.append(lead if lead else hole(x, y, side))
        for k in range(len(pts) - 1):
            sa, sb = pts[k][2], pts[k + 1][2]
            bulge = -1 if (sa in ("top", "panel_top") and sb in ("top", "panel_top")) else 1 if (sa in ("bottom", "panel_bot") and sb in ("bottom", "panel_bot")) else 0
            add(net, color, cname, pts[k][3], pts[k + 1][3], pos[k], pos[k + 1], bulge)
    return Board(plan, chip_at, pin_xy, ext_xy, ext_box, wires, rows, cols, width, height, top, row_y)


def _curve(a, b, bulge, k, steps=14):
    """A jumper-wire shaped arc from a to b.  bulge -1: up, +1: down, 0: sideways."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0; dist = (dx * dx + dy * dy) ** 0.5 or 1.0
    h = min(45, 6 + 0.22 * dist) + (k % 5) * 2
    if bulge: cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + bulge * h
    else: cx, cy = (x0 + x1) / 2 + h * (dy / dist), (y0 + y1) / 2 - h * (dx / dist)
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1) for t in [i / steps for i in range(steps + 1)]]


# =====================================================================================================================
def draw(r, bd, states=None):
    """Paint the breadboard.  states: {external ref: 0/1} (switch positions, LEDs on) for the live view."""
    states = states or {}
    plan = bd.plan
    for i in range(bd.rows): _board(r, bd, i)
    _supply(r, bd)
    for w in bd.wires:                                                  # a dark edge first so a wire reads on any colour
        tags = ("wire", f"net:{w.nid}")
        r.line(w.pts, 5.2, "#1b1b1f", tags); r.line(w.pts, 3.4, w.color, tags)
    for ch in plan.chips: _chip(r, bd, ch)                              # chips on top: the wires stay visible where they end
    for e in plan.externals: _external(r, bd, e, states.get(e.ref))
    for w in bd.wires:
        for pt in (w.pts[0], w.pts[-1]): r.circle(pt[0], pt[1], 2.2, "#d4d4d8", "#1b1b1f", 0.8, ("wire", f"net:{w.nid}"))


def _board(r, bd, i):
    y0 = bd.row_y[i]; x1 = X0 + bd.cols * P
    r.rect(X0 - 28, y0 - 14, x1 + 4, y0 + BOARD_H - 14, BOARD, BOARD_EDGE, 1.5)
    r.rect(X0 - 4, y0 + Y_ROWS["e"] + 5, x1 - 20, y0 + Y_ROWS["f"] - 5, "#d6d0bb", "#d6d0bb", 0.5)          # centre gap
    for c in range(bd.cols - 1):
        x = X0 + c * P
        for key in "abcde": r.circle(x, y0 + Y_ROWS[key], 1.5, HOLE, HOLE, 0.1)
        for key in "fghij": r.circle(x, y0 + Y_ROWS[key], 1.5, HOLE, HOLE, 0.1)
        if c % 5 == 0 and c: r.text(x, y0 + Y_ROWS["a"] - 9, str(c), 5.5, TXT, False, "s")
    for yy, col in ((Y_RAIL_TOP[0], BLUE), (Y_RAIL_TOP[1], RED), (Y_RAIL_BOT[0], BLUE), (Y_RAIL_BOT[1], RED)):
        r.line([(X0 - 6, y0 + yy), (x1 - 14, y0 + yy)], 0.8, col)
        for c in range(0, bd.cols - 1):
            if c % 6 != 5: r.circle(X0 + c * P, y0 + yy, 1.4, HOLE, HOLE, 0.1)
        r.text(X0 - 14, y0 + yy, "−" if col == BLUE else "+", 7, col, True, "c")
    for key, y in Y_ROWS.items(): r.text(X0 - 14, y0 + y, key, 5.5, TXT, False, "c")
    r.text(x1, y0 - 16, f"breadboard {i + 1}/{bd.rows}" if bd.rows > 1 else "breadboard", 6.5, MUTED, False, "se")


def _supply(r, bd):
    """+5 V and GND terminals with the jumpers that join the rails of every board row."""
    for i in range(bd.rows):
        y0 = bd.row_y[i]; x = X0 - 24
        pts = ((Y_RAIL_TOP[1], Y_RAIL_BOT[1], RED, -1), (Y_RAIL_TOP[0], Y_RAIL_BOT[0], BLUE, -1))
        for k, (ya, yb, col, _s) in enumerate(pts):
            xx = x - 8 * k
            r.line([(X0 - 6, y0 + ya), (xx, y0 + ya), (xx, y0 + yb), (X0 - 6, y0 + yb)], 3, col)
        if i == 0:
            r.text(4, bd.row_y[0] - 30, "+5 V", 9, RED, True, "w"); r.text(4, bd.row_y[0] - 16, "GND", 9, BLUE, True, "w")
            r.line([(X0 - 32, y0 + Y_RAIL_TOP[1]), (X0 - 32, bd.row_y[0] - 30), (40, bd.row_y[0] - 30)], 1.2, RED)
            r.line([(X0 - 40, y0 + Y_RAIL_TOP[0]), (X0 - 40, bd.row_y[0] - 16), (40, bd.row_y[0] - 16)], 1.2, BLUE)
        if i > 0:
            yp = bd.row_y[i - 1]
            r.line([(X0 - 32, yp + Y_RAIL_BOT[1]), (X0 - 32, y0 + Y_RAIL_TOP[1])], 1.2, RED); r.line([(X0 - 40, yp + Y_RAIL_BOT[0]), (X0 - 40, y0 + Y_RAIL_TOP[0])], 1.2, BLUE)


def _chip(r, bd, ch):
    row, c0 = bd.chip_at[ch.ref]; n = ch.chip.pins; y0 = bd.row_y[row]
    x_a = X0 + c0 * P - 6; x_b = X0 + (c0 + n // 2 - 1) * P + 6
    ye, yf = y0 + Y_ROWS["e"], y0 + Y_ROWS["f"]
    for p in range(1, n + 1):
        x, y = bd.pin_xy[(ch.ref, p)]
        r.rect(x - 1.8, min(y, y + (4 if y == ye else -4)), x + 1.8, max(y, y + (4 if y == ye else -4)), LEG, LEG, 0.2)
        r.circle(x, y, 2.3, LEG, "#6b6f7a", 0.8)
    r.rect(x_a, ye + 4, x_b, yf - 4, CHIP, CHIP_EDGE, 1.2)
    r.circle(x_a + 2, (ye + yf) / 2, 2.6, "#0d0d10", "#52525b", 0.8)                              # the notch / pin-1 end
    r.circle(x_a + 8, yf - 8, 1.6, "#9ca3af", "#9ca3af", 0.1)                                      # pin-1 dot
    r.text((x_a + x_b) / 2 + 3, (ye + yf) / 2 - 3, ch.part, 7.5, "#e5e7eb", True, "c")
    r.text((x_a + x_b) / 2 + 3, (ye + yf) / 2 + 5, ch.ref, 6, "#9ca3af", False, "c")
    for p in range(1, n + 1):
        x, y = bd.pin_xy[(ch.ref, p)]
        r.text(x, y - 7 if y == ye else y + 7, str(p), 4.6, "#5b5a50", False, "c")


def _external(r, bd, e, state):
    cx, cy = bd.ext_box[e.ref]
    on = bool(state)
    if e.kind == "switch":
        tg = (f"ext:{e.ref}",)
        r.rect(cx - 12, cy - 9, cx + 12, cy + 9, "#e4e4e7", "#52525b", 1.2, tg)
        r.line([(cx, cy + 7), (cx, cy - 7)] if on else [(cx, cy - 7), (cx, cy + 7)], 3, "#16a34a" if on else "#71717a", tg)
        r.text(cx, cy - 12, e.label.replace("Input ", ""), 7, OUTLINE, True, "s"); r.text(cx, cy + 12, "1" if on else "0", 7, MUTED, False, "n")
    elif e.kind == "clock":
        r.rect(cx - 14, cy - 9, cx + 14, cy + 9, "#e4e4e7", "#52525b", 1.2)
        r.line([(cx - 10, cy + 4), (cx - 5, cy + 4), (cx - 5, cy - 4), (cx + 1, cy - 4), (cx + 1, cy + 4), (cx + 6, cy + 4), (cx + 6, cy - 4), (cx + 10, cy - 4)], 1.4, "#3f3f46")
        r.text(cx, cy - 12, "clock", 7, OUTLINE, True, "s")
    elif e.kind == "led":
        r.circle(cx, cy, 8, "#fb7185" if on else "#fecdd3", "#9f1239", 1.2)
        r.text(cx, cy + 12, e.label.replace("Output ", ""), 7, OUTLINE, True, "n")
    else:
        names = list(e.pins); w = max(46, 12 + 11 * len(names))
        r.rect(cx - w / 2, cy - 14, cx + w / 2, cy + 14, "#e4e4e7" if e.kind != "block" else "#fde68a", "#52525b", 1.2)
        r.text(cx, cy - 2, "8" if e.kind != "block" else "?", 14, "#3f3f46", True, "c")
        r.text(cx, cy + 20, e.label if len(e.label) < 22 else e.label[:20] + "…", 6.5, OUTLINE, False, "n")
        for k, nm in enumerate(names):
            x, y = bd.ext_xy[(e.ref, nm)]
            r.text(x, y + (7 if y < cy else -7), nm, 5.5, MUTED, False, "c")
    for (ref, nm), (x, y) in bd.ext_xy.items():
        if ref == e.ref: r.circle(x, y, 2.4, "#d4d4d8", "#52525b", 0.8)


# =====================================================================================================================
INK, SOFT = "#111827", "#64748b"                          # cards are always white, so their text colours do not follow the theme
CARD_W, ROW_H = 340, 15


def card_size(ch): return CARD_W, (ch.chip.pins // 2) * ROW_H + 46


def draw_chip_card(r, plan, ch, x, y):
    """One chip as the datasheet draws it: pins numbered round the package, with the signal on every pin."""
    cat = ch.chip; n = cat.pins; half = n // 2
    w, h = card_size(ch)
    r.rect(x, y, x + w, y + h, "#f8fafc" if False else "#ffffff", "#cbd5e1", 1)
    r.text(x + 8, y + 12, f"{ch.ref}  {ch.part}", 11, INK, True, "w")
    r.text(x + w - 8, y + 12, f"{ch.used()}/{len(ch.slots)} used" if len(ch.slots) > 1 else cat.family, 8, SOFT, False, "e")
    bx0, bx1 = x + w / 2 - 42, x + w / 2 + 42; by0 = y + 30; by1 = by0 + half * ROW_H
    r.rect(bx0, by0, bx1, by1, "#25262b", CHIP_EDGE, 1.2)
    r.circle((bx0 + bx1) / 2, by0, 5, "#ffffff", "#52525b", 1)                                       # the notch at the top
    r.text((bx0 + bx1) / 2, (by0 + by1) / 2, ch.part, 9, "#e5e7eb", True, "c")
    for p in range(1, n + 1):
        left = p <= half
        yy = by0 + ROW_H * ((p - 1) if left else (n - p)) + ROW_H / 2
        xx = bx0 if left else bx1
        r.line([(xx, yy), (xx - 12, yy)] if left else [(xx, yy), (xx + 12, yy)], 2.4, "#94a3b8")
        r.text(xx + (7 if left else -7), yy, str(p), 6.5, "#e5e7eb", False, "w" if left else "e")
        net = ch.pins.get(p); kind = cat.pin_kind(p)
        pname = cat.pin_name(p)
        if net is None: sig, role = ("–" if kind != "nc" else "NC"), SOFT
        elif net == VCC: sig, role = "VCC (+5 V)", "#e11d48"
        elif net == GND: sig, role = "GND", "#2563eb"
        else: sig, role = plan.name(net), "#0f766e" if kind in ("out", "io") else INK
        sig = sig if len(sig) <= 15 else sig[:14] + "…"
        if left:
            r.text(bx0 - 16, yy, pname, 7, SOFT, False, "e"); r.text(x + 8, yy, sig, 8, role, True, "w")
        else:
            r.text(bx1 + 16, yy, pname, 7, SOFT, False, "w"); r.text(x + w - 8, yy, sig, 8, role, True, "e")
    return h


# =====================================================================================================================
def to_png(bd, states=None, scale=1.6):
    """Pillow image of the breadboard picture."""
    from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
    im, d, tf = canvas(bd.extent(), scale, 12, "#f4f4f5")
    draw(PilRenderer(d, tf, scale, LIGHT), bd, states)
    return im


def cards_png(plan, cols=3, scale=2.0):
    """Pillow image with the pin diagram of every chip."""
    from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
    chips = plan.chips or []
    if not chips: return None
    gap = 14; cols = max(1, min(cols, len(chips)))
    rows = [chips[i:i + cols] for i in range(0, len(chips), cols)]
    heights = [max(card_size(c)[1] for c in row) for row in rows]
    W = cols * (CARD_W + gap) + gap; H = sum(heights) + gap * (len(rows) + 1)
    im, d, tf = canvas((0, 0, W, H), scale, 6, "#e5e7eb")
    r = PilRenderer(d, tf, scale, LIGHT); y = gap
    for row, h in zip(rows, heights):
        for i, ch in enumerate(row): draw_chip_card(r, plan, ch, gap + i * (CARD_W + gap), y)
        y += h + gap
    return im
