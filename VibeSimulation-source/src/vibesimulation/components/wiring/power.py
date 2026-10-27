"""Power symbol (Logisim: Wiring > Power): a constant 1."""
from ...core.model import Attr, Component, make_port
from ...core.bits import mask
from ...core.render import OUTLINE
from ..registry import register
from ..shapes import draw_pins


@register
class Power(Component):
    type_name = "Power"
    logisim_name = "Power"
    library, category = "Wiring", "Wiring"
    summary = "Always outputs all ones (1)."
    attrs_spec = (Attr("width", "int", 1, "Data bits", 1, 64),)
    value_is_one = True

    def all_ports(self):
        return [make_port("Out", "out", self.attrs["width"], 0, 0, self.body(), "")]

    def body(self):
        return (-10, 0, 10, 10)

    def evaluate(self, v):
        return {"Out": mask(self.attrs["width"]) if self.value_is_one else 0}

    def draw(self, r, ax, ay, ctx):
        r.line([(ax, ay), (ax, ay + 6)], 2, OUTLINE, ctx.body_tags)
        if self.value_is_one:
            r.polygon([(ax - 7, ay + 6), (ax + 7, ay + 6), (ax, ay + 14)], "fill", OUTLINE, 2, ctx.body_tags)
        else:
            for i, hw in enumerate((8, 5, 2)):
                r.line([(ax - hw, ay + 6 + 3 * i), (ax + hw, ay + 6 + 3 * i)], 2, OUTLINE, ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"width": self.attrs["width"]} if self.attrs["width"] != 1 else {}
