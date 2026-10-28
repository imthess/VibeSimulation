"""Constant value (Logisim: Wiring > Constant)."""
from ...core.model import Attr, Component, make_port
from ...core.bits import mask
from ...core.render import FILL, OUTLINE
from ..registry import register
from ..shapes import draw_pins


@register
class Constant(Component):
    type_name = "Constant"
    logisim_name = "Constant"
    library, category = "Wiring", "Wiring"
    summary = "A fixed value (for example 0, 1 or 5)."
    attrs_spec = (Attr("width", "int", 1, "Data bits", 1, 64), Attr("value", "int", 1, "Value", 0, 2 ** 64 - 1))

    def all_ports(self):
        return [make_port("Out", "out", self.attrs["width"], 0, 0, self.body(), "")]

    def body(self):
        return (-14, -8, 0, 8) if self.attrs["width"] <= 4 else (-6 - 8 * ((self.attrs["width"] + 3) // 4), -8, 0, 8)

    def evaluate(self, v):
        return {"Out": self.attrs["value"] & mask(self.attrs["width"])}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, FILL, 1, ctx.body_tags)
        r.text(ax + (x0 + x1) / 2, ay, format(self.attrs["value"] & mask(self.attrs["width"]), "X"), 10, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        a = {"width": self.attrs["width"], "value": hex(self.attrs["value"] & mask(self.attrs["width"]))}
        return {k: v for k, v in a.items() if not (k == "width" and v == 1)}

    def load_dict(self, d):
        super().load_dict(d)
