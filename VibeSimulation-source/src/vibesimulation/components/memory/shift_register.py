"""Shift Register (Logisim: Memory > Shift Register)."""
from ...core.bits import mask
from ...core.model import Attr, make_port
from ..registry import register
from .seq_base import EDGE, Sequential


@register
class ShiftRegister(Sequential):
    type_name = "Shift Register"
    aliases = ("ShiftRegister",)
    logisim_name = "Shift Register"
    summary = "Shift register: on every clock edge (Shift not 0) takes In at one end and pushes everything one place; Load (1) fills all stages from D0..; Out is the oldest stage."
    attrs_spec = (Attr("width", "int", 1, "Data bits", 1, 64), Attr("length", "int", 8, "Stages", 1, 64),
                  Attr("parallel", "bool", True, "Parallel load"), Attr("trigger", "choice", "rising", "Trigger", choices=EDGE))

    @property
    def state_outs(self):                 # Out and every parallel Q show remembered values only
        n = self.attrs["length"] if self.attrs["parallel"] else 0
        return ("Out",) + tuple(f"Q{i}" for i in range(n))

    def body(self):
        return (0, -20, (20 + 10 * self.attrs["length"]) if self.attrs["parallel"] else 30, 20)

    def all_ports(self):
        w, n, par, b = self.attrs["width"], self.attrs["length"], self.attrs["parallel"], self.body()
        ps = [make_port("In", "in", w, 0, 0, b, "In"), make_port("Clk", "in", 1, 0, 10, b, ""),
              make_port("Sh", "in", 1, 0, -10, b, "sh", optional=True, default=1),
              make_port("Clr", "in", 1, 10, 20, b, "0", optional=True, default=0)]
        if par:
            ps.append(make_port("Ld", "in", 1, 10, -20, b, "ld", optional=True, default=0))
            ps += [make_port(f"D{i}", "in", w, 20 + 10 * i, -20, b, "", optional=True, default=0) for i in range(n)]
        ps.append(make_port("Out", "out", w, b[2], 0, b, "Out"))
        if par: ps += [make_port(f"Q{i}", "out", w, 20 + 10 * i, 20, b, "", optional=True) for i in range(n)]
        return ps

    def evolution_ports(self):
        n = self.attrs["length"]
        d = {"In": (0, 80), "Sh": (0, 40), "Clk": (0, 50), "Clr": (0, 20), "Ld": (0, 30), "Out": (120, 70 + 20 * n)}
        for i in range(n):
            d[f"D{i}"] = (0, 90 + 20 * i)
            if i < n - 1: d[f"Q{i}"] = (120, 90 + 20 * i)          # (the last row's output is Out itself)
        return d

    def init_state(self): return {"v": [0] * self.attrs["length"], "clk": None}

    def outputs(self, st, args):
        v, n = st["v"], self.attrs["length"]
        out = {"Out": v[0]}
        for i in range(n): out[f"Q{i}"] = v[n - 1 - i]
        return out

    def step(self, st, a, tick):
        hit = self.clocked(st, a); n = self.attrs["length"]; m = mask(self.attrs["width"])
        if a.get("Clr") == 1: st["v"] = [0] * n
        elif hit:
            if self.attrs["parallel"] and a.get("Ld") == 1:
                st["v"] = [(a.get(f"D{i}") or 0) & m for i in range(n - 1, -1, -1)]
            elif a.get("Sh") != 0: st["v"] = st["v"][1:] + [(a.get("In") or 0) & m]
        return st

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        self.box(r, ax, ay, ctx, [("In", "", "in")], title="Shift Reg", title_at=((x0 + x1) / 2, 0))

    def logisim_attrs(self):
        return dict(super().logisim_attrs(), width=self.attrs["width"], length=self.attrs["length"], parallel=str(self.attrs["parallel"]).lower())
