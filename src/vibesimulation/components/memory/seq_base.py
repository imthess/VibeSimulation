"""Shared base of the sequential parts (Template Method): state, clock handling and the classic Logisim look."""
from ...core.model import Attr, Component
from ...core.render import FILL, OUTLINE, MUTED, ON, OFF
from ...core.sim import edge
from ..shapes import draw_pins

EDGE = ("rising", "falling")
LEVEL = ("rising", "falling", "high", "low")


class Sequential(Component):
    """A part that remembers something between clock edges. Subclasses fill in init_state / outputs / step."""
    sequential = True
    show_optional = True
    handles_error = True
    library, category = "Memory", "Memory"

    def evaluate(self, v):            # not used: the simulator asks outputs()/step() instead
        return {}

    def evolution_ports(self):
        """Pin positions of Logisim-evolution's newer 'logisim_evolution' look (the importer needs them: files are usually in that look). None = same as classic."""
        return None

    def trigger(self):
        return self.attrs.get("trigger", "rising")

    def clocked(self, st, args):
        """True if the clock pin triggers this part now (remembers the clock value like Logisim's ClockState)."""
        return edge(st, args.get("Clk"), self.trigger())

    def logisim_attrs(self):
        a = {"appearance": "classic"}
        if "trigger" in self.attrs: a["trigger"] = self.attrs["trigger"]
        return a

    # ---- classic look
    def box(self, r, ax, ay, ctx, labels=(), clock="Clk", title="", title_at=None, size=9):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        for name, txt, where in labels:
            p = self.port(name)
            if p is None: continue
            x, y = ax + p.dx, ay + p.dy
            if where == "in": r.text(x + 4, y, txt, size, OUTLINE, True, "w", ctx.body_tags)
            elif where == "out": r.text(x - 4, y, txt, size, OUTLINE, True, "e", ctx.body_tags)
            elif where == "up": r.text(x, y + 3, txt, 8, MUTED, False, "n", ctx.body_tags)
            else: r.text(x, y - 3, txt, 8, MUTED, False, "s", ctx.body_tags)
        p = self.port(clock) if clock else None
        if p is not None:
            x, y = ax + p.dx, ay + p.dy
            tr = self.trigger()
            if tr in ("rising", "falling"): r.line([(x, y - 5), (x + 8, y), (x, y + 5)], 2, OUTLINE, ctx.body_tags)
            if tr in ("falling", "low"): r.circle(x - 4, y, 3.5, FILL, OUTLINE, 1.5, ctx.body_tags)
        if title:
            tx, ty = title_at or ((x0 + x1) / 2, (y0 + y1) / 2)
            r.text(ax + tx, ay + ty, title, 11, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def hexval(self, ctx, port, width=1):
        s = self.outs.get(port)
        v = ctx.val(s, 0) if s is not None else 0
        if v is None: return "E"
        digits = max(1, (width + 3) // 4)
        return f"{v:0{digits}X}"
