"""Bit extender (Logisim: Wiring > Bit Extender): makes a signal wider or narrower."""
from ...core.bits import mask, to_signed
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE
from ..registry import register
from ..shapes import draw_pins


@register
class BitExtender(Component):
    type_name = "BitExtender"
    logisim_name = "Bit Extender"
    library, category = "Wiring", "Wiring"
    summary = "Changes the number of bits, filling new top bits with 0, 1 or the sign bit."
    attrs_spec = (Attr("in_width", "int", 8, "Input bits", 1, 64), Attr("out_width", "int", 16, "Output bits", 1, 64),
                  Attr("fill", "choice", "zero", "Fill with", choices=("zero", "one", "sign")))

    def body(self):
        return (-40, -20, 0, 20)

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", self.attrs["in_width"], -40, 0, b, ""), make_port("Out", "out", self.attrs["out_width"], 0, 0, b, "")]

    def evaluate(self, v):
        iw, ow, f = self.attrs["in_width"], self.attrs["out_width"], self.attrs["fill"]
        x = v["In"]
        if ow <= iw: return {"Out": x & mask(ow)}
        ext = {"zero": 0, "one": mask(ow) & ~mask(iw), "sign": (mask(ow) & ~mask(iw)) if x >> (iw - 1) & 1 else 0}[f]
        return {"Out": x | ext}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax - 20, ay, "extend", 9, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"in_width": self.attrs["in_width"], "out_width": self.attrs["out_width"],
                "type": {"zero": "zero", "one": "one", "sign": "sign"}[self.attrs["fill"]]}
