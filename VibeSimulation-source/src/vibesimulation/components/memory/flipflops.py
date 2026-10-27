"""D, T, J-K and S-R flip-flops (Logisim: Memory > ... Flip-Flop). Geometry, behaviour and defaults follow Logisim-evolution 3.8 (classic look)."""
from ...core.model import Attr, make_port
from ...core.render import FILL, OUTLINE, MUTED, ON, OFF
from ..registry import register
from .seq_base import EDGE, LEVEL, Sequential


class FlipFlop(Sequential):
    """Q (and its opposite) change only when the clock triggers; Clr (0) and Pre (1) work at once."""
    names = ()           # data input names, in Logisim's order
    ys = ()              # their y positions
    levels = False
    attrs_spec = (Attr("trigger", "choice", "rising", "Trigger", choices=EDGE),)
    state_outs = ("Q", "Qn")

    def body(self):
        return (-40, -10, 0, 30)

    def all_ports(self):
        b = self.body()
        ps = [make_port(n, "in", 1, -40, y, b, n) for n, y in zip(self.names, self.ys)]
        ps.append(make_port("Clk", "in", 1, -40, {1: 0, 2: 10}[len(self.names)], b, ""))
        ps.append(make_port("Clr", "in", 1, -10, 30, b, "0", optional=True, default=0))
        ps.append(make_port("Pre", "in", 1, -30, 30, b, "1", optional=True, default=0))
        ps.append(make_port("Q", "out", 1, 0, 0, b, "Q"))
        ps.append(make_port("Qn", "out", 1, 0, 20, b, "", optional=True))
        return ps

    def evolution_ports(self):
        d = {n: (-10, 10 + 20 * i) for i, n in enumerate(self.names)}
        d.update(Clk=(-10, 50), Clr=(20, 60), Pre=(20, 0), Q=(50, 10), Qn=(50, 50)); return d

    def init_state(self):
        return {"q": 0, "clk": None}

    def outputs(self, st, args):
        return {"Q": st["q"], "Qn": 1 - st["q"]}

    def compute(self, a, q):
        return None

    def step(self, st, a, tick):
        hit = self.clocked(st, a)
        if a.get("Clr") == 1: st["q"] = 0
        elif a.get("Pre") == 1: st["q"] = 1
        elif hit:
            nv = self.compute(a, st["q"])
            if nv in (0, 1): st["q"] = nv
        return st

    def draw(self, r, ax, ay, ctx):
        q = ctx.val(self.outs.get("Q"), 0)
        labels = [(n, n, "in") for n in self.names] + [("Q", "Q", "out"), ("Clr", "0", "down"), ("Pre", "1", "down")]
        self.box(r, ax, ay, ctx, labels)
        r.circle(ax - 20, ay + 10, 6.5, ON if q else OFF, OUTLINE, 1, ctx.body_tags)
        r.text(ax - 20, ay + 10, "E" if q is None else str(q), 8, "label", True, "c", ctx.body_tags)


class LevelFlipFlop(FlipFlop):
    attrs_spec = (Attr("trigger", "choice", "rising", "Trigger", choices=LEVEL),)


@register
class DFlipFlop(LevelFlipFlop):
    type_name = "D Flip-Flop"
    aliases = ("DFF", "DFlipFlop")
    logisim_name = "D Flip-Flop"
    summary = "D flip-flop: Q takes the value of D when the clock triggers."
    names, ys = ("D",), (20,)

    def compute(self, a, q): return a.get("D")


@register
class TFlipFlop(FlipFlop):
    type_name = "T Flip-Flop"
    aliases = ("TFF", "TFlipFlop")
    logisim_name = "T Flip-Flop"
    summary = "T flip-flop: Q toggles when T is 1 as the clock triggers."
    names, ys = ("T",), (20,)

    def compute(self, a, q): return 1 - q if a.get("T") == 1 else q


@register
class JKFlipFlop(FlipFlop):
    type_name = "J-K Flip-Flop"
    aliases = ("JKFF", "JKFlipFlop")
    logisim_name = "J-K Flip-Flop"
    summary = "J-K flip-flop: J sets, K clears, both toggle (on a clock edge)."
    names, ys = ("J", "K"), (0, 20)

    def compute(self, a, q):
        j, k = a.get("J"), a.get("K")
        if j == 0 and k == 0: return q
        if j == 0 and k == 1: return 0
        if j == 1 and k == 0: return 1
        if j == 1 and k == 1: return 1 - q
        return None


@register
class SRFlipFlop(FlipFlop):
    type_name = "S-R Flip-Flop"
    aliases = ("SRFF", "SRFlipFlop")
    logisim_name = "S-R Flip-Flop"
    summary = "S-R flip-flop: S sets, R clears (both 1 leaves Q alone)."
    names, ys = ("S", "R"), (0, 20)

    def compute(self, a, q):
        s, r_ = a.get("S"), a.get("R")
        if s == 0 and r_ == 0: return q
        if s == 0 and r_ == 1: return 0
        if s == 1 and r_ == 0: return 1
        return None
