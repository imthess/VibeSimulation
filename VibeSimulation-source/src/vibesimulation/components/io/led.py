"""LED (Logisim: Input/Output > LED): lights up when its input is 1."""
from ...core.model import Component, make_port
from ...core.render import FILL, OUTLINE, ON, OFF
from ..registry import register
from ..shapes import draw_pins


@register
class Led(Component):
    type_name = "LED"
    logisim_name = "LED"
    library, category = "Input/Output", "Input/Output"
    summary = "A light that shows the input value (display only)."
    handles_error = True

    def all_ports(self):
        return [make_port("In", "in", 1, 0, 0, self.body(), "")]

    def body(self):
        return (0, -10, 20, 10)

    def evaluate(self, v):
        return {}

    def draw(self, r, ax, ay, ctx):
        on = ctx.val(self.ins.get("In"), None)
        r.circle(ax + 10, ay, 8, ON if on else FILL, OUTLINE, 2, ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"facing": "west"}
