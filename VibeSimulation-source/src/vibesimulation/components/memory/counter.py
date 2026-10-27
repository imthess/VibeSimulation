"""Counter (Logisim: Memory > Counter)."""
from ...core.bits import mask
from ...core.model import Attr, make_port
from ..registry import register
from .seq_base import EDGE, Sequential


@register
class Counter(Sequential):
    type_name = "Counter"
    logisim_name = "Counter"
    summary = "Counter: counts up (or down) on every clock edge; Load (1) takes D; Clear (1) resets; Carry = at the end of its range."
    attrs_spec = (Attr("width", "int", 8, "Data bits", 1, 64),
                  Attr("max", "int", 0, "Maximum value (0 = all ones)", 0, 0xFFFFFFFF),
                  Attr("ongoal", "choice", "wrap", "Action on reaching the end", choices=("wrap", "stay", "continue", "load")),
                  Attr("trigger", "choice", "rising", "Trigger", choices=EDGE))
    state_outs = ("Q",)
    comb_in = ("UD",)

    def top(self):
        return self.attrs["max"] or mask(self.attrs["width"])

    def body(self):
        return (-30, -20, 0, 20)

    def all_ports(self):
        w, b = self.attrs["width"], self.body()
        return [make_port("Clk", "in", 1, -20, 20, b, ""),
                make_port("D", "in", w, -30, 0, b, "D", optional=True, default=0),
                make_port("Ld", "in", 1, -30, -10, b, "ld", optional=True, default=0),
                make_port("UD", "in", 1, -20, -20, b, "ud", optional=True, default=1),
                make_port("En", "in", 1, -30, 10, b, "en", optional=True, default=1),
                make_port("Clr", "in", 1, -10, 20, b, "0", optional=True, default=0),
                make_port("Q", "out", w, 0, 0, b, "Q"), make_port("Carry", "out", 1, 0, 10, b, "", optional=True)]

    def evolution_ports(self):
        w = self.attrs["width"]; x = 150 + int((w - 8) / 5) * 10 + 40; y = 120 if w == 1 else 110       # (int() truncates like Java)
        return {"Q": (x, y), "D": (0, y), "Clk": (0, 80), "Clr": (0, 20), "Ld": (0, 30), "UD": (0, 50), "En": (0, 70), "Carry": (x, 50)}

    def init_state(self): return {"q": 0, "clk": None, "up": 1}

    def outputs(self, st, args):
        up = args.get("UD", st.get("up", 1)) != 0
        return {"Q": st["q"], "Carry": int(st["q"] == (self.top() if up else 0))}

    def step(self, st, a, tick):
        hit = self.clocked(st, a); m = mask(self.attrs["width"]); top = self.top(); up = a.get("UD") != 0
        st["up"] = int(up)
        if a.get("Clr") == 1: st["q"] = 0
        elif hit:
            load = (a.get("D") or 0) & m
            if a.get("Ld") == 1: st["q"] = min(load, top) if load > top else load
            elif a.get("En") != 0:
                goal = top if up else 0
                if st["q"] == goal:
                    g = self.attrs["ongoal"]
                    if g == "wrap": st["q"] = 0 if up else top
                    elif g == "load": st["q"] = load & top if load > top else load
                    elif g == "continue": st["q"] = (st["q"] + (1 if up else -1)) & m
                else: st["q"] = (st["q"] + (1 if up else -1)) & m
        return st

    def draw(self, r, ax, ay, ctx):
        w = self.attrs["width"]
        self.box(r, ax, ay, ctx, [], title="ctr", title_at=(-15, -7))
        r.text(ax - 15, ay + 6, "0x" + self.hexval(ctx, "Q", w), 9, "label", True, "c", ctx.body_tags)

    def logisim_attrs(self):
        return dict(super().logisim_attrs(), width=self.attrs["width"], max=hex(self.top()), ongoal=self.attrs["ongoal"])
