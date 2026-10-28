"""Bit selector (Logisim: Plexers > Bit Selector): picks one group of bits out of a wide input."""
from ...core.bits import clog2, mask
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE
from ..registry import register
from ..shapes import draw_pins


@register
class BitSelector(Component):
    type_name = "BITSELECTOR"
    aliases = ('Bit Selector',)
    logisim_name = "BitSelector"
    library, category = "Plexers", "Plexers"
    summary = "Chooses which group of bits of a wide signal is sent to the output."
    attrs_spec = (Attr("width", "int", 8, "Input bits", 1, 64), Attr("group", "int", 1, "Output bits", 1, 64))

    def groups(self):
        return -(-self.attrs["width"] // self.attrs["group"])

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", self.attrs["width"], -30, 0, b, ""),
                make_port("Sel", "in", clog2(self.groups()), -10, 10, b, ""),
                make_port("Out", "out", self.attrs["group"], 0, 0, b, "")]

    def body(self):
        return (-30, -15, 0, 15)

    def check(self):
        return ["Output bits must be smaller than the input bits"] if self.attrs["group"] >= self.attrs["width"] else []

    def evaluate(self, v):
        g = self.attrs["group"]
        return {"Out": (v["In"] >> (g * v["Sel"])) & mask(g) if v["Sel"] < self.groups() else 0}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.polygon([(ax + x0, ay + y0), (ax + x1, ay + y0 + 5), (ax + x1, ay + y1 - 5), (ax + x0, ay + y1)], FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax - 14, ay - 1, "Sel", 9, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"width": self.attrs["width"], "group": self.attrs["group"]}
