"""Draws a laid-out analog schematic on any Renderer (the Tk canvas or a PDF page): wires, junction dots, ground symbols,
net names with their voltages, and the parts with their names and values."""
from ..core.render import LABEL, MUTED, OUTLINE
from . import components as AC
from .layout import Rot, pin_xy
from .units import fmt_si


def paint_schematic(r, L, volts=None, digits=4, tagged=True, results=None):
    for k, (a, b, c, d, net) in enumerate(L.wires): r.line([(a, b), (c, d)], 2, OUTLINE, (("wire", f"wire:{k}") if tagged else ()))
    for (x, y) in L.junctions(): r.circle(x, y, 4, OUTLINE, None, 0)
    for gx, gy in L.grounds:
        r.line([(gx, gy), (gx, gy + 18)], 2, OUTLINE)
        for j, hw in enumerate((16, 10, 4)): r.line([(gx - hw, gy + 18 + 6 * j), (gx + hw, gy + 18 + 6 * j)], 2, OUTLINE)
    for net, x, y in L.rails:
        r.text(x + 8, y - 8, net + (f" = {fmt_si(volts.get(net), 'V', digits)}" if volts and net in volts else ""), 9, MUTED, False, "sw")
    if tagged:                                                       # small round ends on every part terminal: drag from one to another to join their nets
        for pl in L.parts:
            for k in range(pl.part.nterm):
                x, y = pin_xy(pl, k); r.circle(x, y, 4, "fill", OUTLINE, 1.5, ("term", f"term:{pl.part.id}:{k}"))
    for x, y, net, (ux, uy) in L.labels:                             # pins of multi-terminal parts: a short stub and the net name (joined by name, like a net label)
        ex, ey = x + 14 * ux, y + 14 * uy
        r.line([(x, y), (ex, ey)], 2, OUTLINE)
        if net == "0":
            if ux: r.line([(ex, ey), (ex, ey + 8)], 2, OUTLINE); ey += 8
            for j, hw in enumerate((9, 6, 3)): r.line([(ex - hw, ey + 3 + 4 * j), (ex + hw, ey + 3 + 4 * j)], 2, OUTLINE)
        else:
            val = f" = {fmt_si(volts.get(net), 'V', digits)}" if volts and net in volts else ""
            r.text(ex + 4 * ux, ey + 4 * uy, net + val, 9, MUTED, False, "w" if ux > 0 else "e" if ux < 0 else ("n" if uy > 0 else "s"))
    for pl in L.parts:
        p = pl.part; tags = ("comp", "comp:" + p.id) if tagged else ()
        if p.nterm != 2:
            if tagged: r.rect(pl.cx - 26, pl.cy - 30, pl.cx + 26, pl.cy + 30, "fill", "fill", 0, tags)      # something to click on in the middle of the symbol
            p.draw(r, pl.cx, pl.cy, tags); cap = p.caption(digits)
            if p.letter in "QMJ":                                      # the transistor's pins are above, below and left: name and value go to its right
                r.text(pl.cx + 30, pl.cy - 9, p.id, 11, LABEL, True, "w", tags)
                if cap: r.text(pl.cx + 30, pl.cy + 9, cap, 10, OUTLINE, False, "w", tags)
            else:
                r.text(pl.cx, pl.cy - 58, p.id, 11, LABEL, True, "s", tags)
                if cap: r.text(pl.cx, pl.cy + 58, cap, 10, OUTLINE, False, "n", tags)
            continue
        p.draw(Rot(r, pl.cx, pl.cy, pl.angle), pl.cx, pl.cy, tags)
        val = p.caption(digits)
        if results and p.id in results and isinstance(p, (AC.Ammeter, AC.Voltmeter)):          # a meter shows what it reads
            val = fmt_si(results[p.id][1] if isinstance(p, AC.Ammeter) else results[p.id][0], p.unit, digits)
        if pl.vertical:
            dx = 40 if isinstance(p, (AC.VoltageSource, AC.Dependent)) else 28
            r.text(pl.cx + dx, pl.cy - 9, p.id, 11, LABEL, True, "w", tags); r.text(pl.cx + dx, pl.cy + 10, val, 10, OUTLINE, False, "w", tags)
        else:
            r.text(pl.cx, pl.cy - 26, p.id, 11, LABEL, True, "s", tags); r.text(pl.cx, pl.cy + 26, val, 10, OUTLINE, False, "n", tags)
