"""Multiplier (Logisim: Arithmetic > Multiplier)."""
from ...core.bits import mask
from ..registry import register
from .arith_base import SquareArith


@register
class Multiplier(SquareArith):
    type_name = "Multiplier"
    logisim_name = "Multiplier"
    summary = "Computes A x B (+ Cin). Prod holds the low bits, Cout the high bits."
    symbol, top_label, bottom_label = "×", "c in", "c out"

    def all_ports(self):
        return self.std_ports("A", "B", "Prod", ("Cin", 0), "Cout", self.w, self.w)

    def evaluate(self, v):
        t = v["A"] * v["B"] + v.get("Cin", 0)
        return {"Prod": t & mask(self.w), "Cout": (t >> self.w) & mask(self.w)}
