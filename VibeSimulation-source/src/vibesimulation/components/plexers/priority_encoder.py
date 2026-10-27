"""Priority encoder (Logisim: Plexers > Priority Encoder): the number of the highest active input."""
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


@register
class PriorityEncoder(Component):
    type_name = "ENCODER"
    aliases = ('Priority Encoder', 'Encoder')
    logisim_name = "Priority Encoder"
    library, category = "Plexers", "Plexers"
    handles_error = True
    summary = "Encoder: Out = number of the highest-numbered input that is 1. GS = 1 when any input is 1."
    attrs_spec = (Attr("select", "int", 2, "Output bits", 1, 5),)

    @property
    def n(self):
        return 1 << self.attrs["select"]

    def y0(self):
        return -5 * (self.n - 2)

    def body(self):
        return (-40, self.y0() - 10, 0, self.y0() + 10 * (self.n - 1) + 10)

    def all_ports(self):
        b, n = self.body(), self.n
        ports = [make_port(f"In{i}", "in", 1, -40, self.y0() + 10 * i, b, str(i)) for i in range(n)]
        ports.append(make_port("EI", "in", 1, -20, b[3], b, "", optional=True, default=1))
        ports.append(make_port("Out", "out", self.attrs["select"], 0, 0, b, ""))
        ports.append(make_port("GS", "out", 1, 0, 10, b, "", optional=True))
        ports.append(make_port("EO", "out", 1, -20, b[1], b, "", optional=True))
        return ports

    def evaluate(self, v):
        if v.get("EI", 1) == 0:
            return {"Out": 0, "GS": 0, "EO": 0}
        for i in reversed(range(self.n)):
            if v[f"In{i}"]:
                return {"Out": i, "GS": 1, "EO": 0}
        return {"Out": None, "GS": 0, "EO": 1}     # Logisim leaves Out undefined when nothing is active

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + (x0 + x1) / 2, ay + (y0 + y1) / 2 + 3, "Pri", 11, OUTLINE, True, "c", ctx.body_tags)
        r.text(ax + x0 + 3, ay + self.y0(), "0", 8, MUTED, False, "w", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"select": self.attrs["select"]}
