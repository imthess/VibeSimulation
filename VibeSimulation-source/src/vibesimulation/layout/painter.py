"""Draws a Layout through any Renderer (screen or PDF) - the Bridge between drawing code and output device."""
from ..components.base import DrawContext
from ..core.bits import fmt
from ..core.render import BAD, FILL, LABEL, MUTED, OFF, ON, OUTLINE, Renderer


def pin_box_width(width):
    return 30 if width == 1 else 12 + 7 * width


def extent(layout):
    """Rectangle (x0, y0, x1, y1) that contains everything drawn."""
    xs, ys = [], []
    for pin, x, y in layout.inputs:
        xs += [x - pin_box_width(pin.width) - 60, x]; ys += [y - 14, y + 14]
    for pin, x, y in layout.outputs:
        xs += [x, x + pin_box_width(pin.width) + 60]; ys += [y - 14, y + 14]
    for p in layout.parts:
        x0, y0, x1, y1 = p.comp.bounds()
        xs += [p.x + x0, p.x + x1]; ys += [p.y + y0 - 14, p.y + y1 + 4]
    for w in layout.wires:
        xs += [w[0], w[2]]; ys += [w[1], w[3]]
    return min(xs), min(ys), max(xs), max(ys)


def _state(v):
    return BAD if v is None else (ON if v else OFF)


class CircuitPainter:
    def __init__(self, renderer: Renderer):
        self.r = renderer

    def paint(self, layout, circuit, values, invals=None, junctions=True):
        r, invals = self.r, invals or {}
        widths = circuit.signals()
        for k, (a, b, c, d, net) in enumerate(layout.wires):
            r.line([(a, b), (c, d)], 2 if widths.get(net, 1) == 1 else 3.5, _state(values.get(net)), ("wire", f"wire:{k}"))
        if junctions:
            self._junctions(layout, values)
        for pl in layout.parts:
            comp = pl.comp
            ctx = DrawContext(values, ("comp", "comp:" + comp.id))
            comp.draw(r, pl.x, pl.y, ctx)
            outs = [s for s in comp.outs.values() if s]
            x0, y0, x1, y1 = comp.body()
            label = outs[0] if len(outs) == 1 else comp.id
            r.text(pl.x + (x0 + x1) / 2, pl.y + comp.bounds()[1] - 3, label, 8, MUTED, False, "s", ("comp", "comp:" + comp.id))
            for p in comp.active_ports():
                sig = (comp.ins if p.direction == "in" else comp.outs).get(p.name)
                if p.direction == "in":
                    if sig is not None: r.circle(pl.x + p.dx, pl.y + p.dy, 4, _state(values.get(sig)), FILL, 1.5, ("pin", f"pin:{comp.id}:{p.name}"))
                    else: r.circle(pl.x + p.dx, pl.y + p.dy, 4, FILL, MUTED, 1.5, ("pin", f"pin:{comp.id}:{p.name}"))
                elif sig is not None:
                    r.circle(pl.x + p.dx, pl.y + p.dy, 3, _state(values.get(sig)), None, 0, ("opin", f"opin:{comp.id}:{p.name}"))
        for pin, x, y in layout.inputs:
            self._pin(pin, x - pin_box_width(pin.width), x, y, values.get(pin.name), "in", ("inpin", "inpin:" + pin.name))
        for pin, x, y in layout.outputs:
            self._pin(pin, x, x + pin_box_width(pin.width), y, values.get(pin.name), "out", ("outpin", "outpin:" + pin.name))

    def _pin(self, pin, xa, xb, y, v, kind, tags):
        r = self.r
        on = bool(v)
        r.rect(xa, y - 10, xb, y + 10, ON if on else FILL, ON if on else OUTLINE, 1.5, tags)
        r.text((xa + xb) / 2, y, fmt(v, pin.width), 11, FILL if on else MUTED, True, "c", tags)
        if kind == "in": r.text(xa - 6, y, pin.name, 11, LABEL, True, "e", tags)
        else: r.text(xb + 6, y, pin.name, 11, LABEL, True, "w", tags)

    def _junctions(self, layout, values):
        r = self.r
        by = {}
        for w in layout.wires:
            by.setdefault(w[4], []).append(w)
        for net, segs in by.items():
            pts = {(w[0], w[1]) for w in segs} | {(w[2], w[3]) for w in segs}
            for (px, py) in pts:
                ends = sum(1 for w in segs if (w[0], w[1]) == (px, py) or (w[2], w[3]) == (px, py))
                inner = any(w[0] <= px <= w[2] and w[1] <= py <= w[3] and (w[0], w[1]) != (px, py) and (w[2], w[3]) != (px, py) for w in segs)
                if ends >= 3 or (inner and ends >= 1):
                    r.circle(px, py, 3.4, _state(values.get(net)), None, 0)
