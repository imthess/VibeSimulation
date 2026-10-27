"""Probe (Logisim: Wiring > Probe): shows the value of a signal (display only)."""
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE
from ..registry import register
from ..shapes import draw_pins


@register
class Probe(Component):
    type_name = "Probe"
    logisim_name = "Probe"
    library, category = "Wiring", "Wiring"
    summary = "Shows the value of a signal (display only)."
    attrs_spec = (Attr("width", "int", 1, "Data bits", 1, 64),)
    handles_error = True

    def body(self):
        return (0, -10, 20 + 6 * self.attrs["width"], 10)

    def all_ports(self):
        return [make_port("In", "in", self.attrs["width"], 0, 0, self.body(), "")]

    def evaluate(self, v):
        return {}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        val = ctx.val(self.ins.get("In"), None)
        r.text(ax + (x0 + x1) / 2, ay, "x" if val is None else format(val, "b").zfill(self.attrs["width"]), 9, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {}
