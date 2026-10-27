"""Hex digit display (Logisim: Input/Output > Hex Digit Display)."""
from ...core.model import Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


@register
class HexDisplay(Component):
    type_name = "HEXDISPLAY"
    aliases = ('Hex Digit Display',)
    logisim_name = "Hex Digit Display"
    library, category = "Input/Output", "Input/Output"
    summary = "Shows a 4-bit input as one hexadecimal digit (display only)."
    handles_error = True

    def body(self):
        return (-15, -60, 25, 0)

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", 4, 0, 0, b, ""), make_port("DP", "in", 1, 20, 0, b, "", optional=True, default=0)]

    def evaluate(self, v):
        return {}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        val = ctx.val(self.ins.get("In"), None)
        r.text(ax + 5, ay - 30, "x" if val is None else format(val, "X"), 26, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)
