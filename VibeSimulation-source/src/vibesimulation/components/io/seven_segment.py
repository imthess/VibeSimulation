"""7-segment display (Logisim: Input/Output > 7-Segment Display)."""
from ...core.model import Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins

PINS = [("A", 20, 0), ("B", 30, 0), ("C", 20, 60), ("D", 10, 60), ("E", 0, 60), ("F", 10, 0), ("G", 0, 0), ("DP", 30, 60)]


@register
class SevenSegment(Component):
    type_name = "SEVENSEG"
    aliases = ('7-Segment Display', 'SevenSegmentDisplay')
    logisim_name = "7-Segment Display"
    library, category = "Input/Output", "Input/Output"
    summary = "Seven-segment display: pins A..G light the segments, DP the dot (display only)."
    handles_error = True

    def body(self):
        return (-5, 0, 35, 60)

    def all_ports(self):
        b = self.body()
        return [make_port(n, "in", 1, x, y, b, "", optional=True, default=0) for n, x, y in PINS]

    def evaluate(self, v):
        return {}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        seg = {"A": (6, 8, 24, 8), "G": (6, 30, 24, 30), "D": (6, 52, 24, 52), "F": (4, 10, 4, 28), "B": (26, 10, 26, 28),
               "E": (4, 32, 4, 50), "C": (26, 32, 26, 50)}
        for n, (a, b, c, d) in seg.items():
            on = ctx.val(self.ins.get(n), None)
            r.line([(ax + a, ay + b), (ax + c, ay + d)], 4, "on" if on else MUTED, ctx.body_tags)
        r.circle(ax + 31, ay + 52, 2, MUTED, MUTED, 1, ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)
