"""Register (Logisim: Memory > Register): stores a value on the clock edge."""
from ...core.bits import mask
from ...core.model import Attr, make_port
from ..registry import register
from .seq_base import LEVEL, Sequential


@register
class Register(Sequential):
    type_name = "Register"
    logisim_name = "Register"
    summary = "Register: Q takes D on the clock edge when Enable is not 0; Clear (1) resets it to 0."
    attrs_spec = (Attr("width", "int", 8, "Data bits", 1, 64), Attr("trigger", "choice", "rising", "Trigger", choices=LEVEL))
    state_outs = ("Q",)

    def body(self):
        return (-30, -20, 0, 20)

    def all_ports(self):
        w, b = self.attrs["width"], self.body()
        return [make_port("D", "in", w, -30, 0, b, "D"), make_port("Clk", "in", 1, -20, 20, b, ""),
                make_port("En", "in", 1, -30, 10, b, "En", optional=True, default=1),
                make_port("Clr", "in", 1, -10, 20, b, "0", optional=True, default=0),
                make_port("Q", "out", w, 0, 0, b, "Q")]

    def evolution_ports(self):
        return {"Q": (60, 30), "D": (0, 30), "Clk": (0, 70), "Clr": (30, 90), "En": (0, 50)}

    def init_state(self): return {"q": 0, "clk": None}

    def outputs(self, st, args): return {"Q": st["q"]}

    def step(self, st, a, tick):
        hit = self.clocked(st, a)
        if a.get("Clr") == 1: st["q"] = 0
        elif hit and a.get("En") != 0 and a.get("D") is not None: st["q"] = a["D"] & mask(self.attrs["width"])
        return st

    def draw(self, r, ax, ay, ctx):
        w = self.attrs["width"]
        self.box(r, ax, ay, ctx, [], title="Reg", title_at=(-15, -8))
        r.text(ax - 15, ay + 5, "0x" + self.hexval(ctx, "Q", w), 9, "label", True, "c", ctx.body_tags)

    def logisim_attrs(self):
        return dict(super().logisim_attrs(), width=self.attrs["width"])
