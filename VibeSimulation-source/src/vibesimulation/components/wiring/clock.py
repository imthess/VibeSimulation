"""Clock (Logisim: Wiring > Clock): a pin that goes 0, 1, 0, 1 ... as the simulation ticks."""
from ...core.model import Attr, make_port
from ...core.render import FILL, OUTLINE, ON, OFF
from ..memory.seq_base import Sequential
from ..registry import register
from ..shapes import draw_pins


@register
class Clock(Sequential):
    type_name = "Clock"
    logisim_name = "Clock"
    library, category = "Wiring", "Wiring"
    summary = "Clock: output is low for 'low' ticks, then high for 'high' ticks, again and again (press Tick)."
    attrs_spec = (Attr("high", "int", 1, "Ticks high", 1, 1 << 30), Attr("low", "int", 1, "Ticks low", 1, 1 << 30), Attr("phase", "int", 0, "Phase offset", 0, 1 << 30))
    state_outs = ("Out",)
    lkeys = {"high": "highDuration", "low": "lowDuration", "phase": "phaseOffset"}     # our setting -> the name in a .circ file

    def body(self): return (-20, -10, 0, 10)

    def all_ports(self): return [make_port("Out", "out", 1, 0, 0, self.body(), "")]

    def init_state(self): return {"v": 0}

    def outputs(self, st, args): return {"Out": st["v"]}

    def step(self, st, a, tick):
        hi, lo = self.attrs["high"], self.attrs["low"]; cycle = hi + lo
        st["v"] = 0 if ((tick + self.attrs["phase"]) % cycle) < lo else 1
        return st

    def draw(self, r, ax, ay, ctx):
        v = ctx.val(self.outs.get("Out"), 0)
        r.rect(ax - 20, ay - 10, ax, ay + 10, ON if v else FILL, OUTLINE, 2, ctx.body_tags)
        r.line([(ax - 16, ay + 5), (ax - 12, ay + 5), (ax - 12, ay - 5), (ax - 6, ay - 5), (ax - 6, ay + 5), (ax - 3, ay + 5)], 1.5, OUTLINE, ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"highDuration": self.attrs["high"], "lowDuration": self.attrs["low"], "phaseOffset": self.attrs["phase"]}
