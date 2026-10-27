"""Shifter (Logisim: Arithmetic > Shifter)."""
from ...core.bits import clog2, mask, to_signed
from ...core.model import Attr, make_port
from ..registry import register
from .arith_base import SquareArith, WIDTH


@register
class Shifter(SquareArith):
    type_name = "Shifter"
    logisim_name = "Shifter"
    summary = "Shifts or rotates In by Shift places (ll/lr logical, ar arithmetic right, rl/rr rotate)."
    attrs_spec = (WIDTH, Attr("shift", "choice", "ll", "Shift type", choices=("ll", "lr", "ar", "rl", "rr")))
    symbol = "<<"

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", self.w, -40, -10, b, "in"), make_port("Shift", "in", clog2(self.w), -40, 10, b, "shift"),
                make_port("Out", "out", self.w, 0, 0, b, "")]

    def evaluate(self, v):
        w, x, n, k = self.w, v["In"], v["Shift"], self.attrs["shift"]
        if k == "ll": r = x << n
        elif k == "lr": r = x >> n
        elif k == "ar": r = to_signed(x, w) >> n
        elif k == "rl": n %= w; r = (x << n) | (x >> (w - n))
        else: n %= w; r = (x >> n) | (x << (w - n))
        return {"Out": r & mask(w)}

    def logisim_attrs(self):
        return {"width": self.w, "shift": self.attrs["shift"]}
