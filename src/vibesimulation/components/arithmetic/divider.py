"""Divider (Logisim: Arithmetic > Divider)."""
from ...core.bits import mask
from ..registry import register
from .arith_base import SquareArith


@register
class Divider(SquareArith):
    type_name = "Divider"
    logisim_name = "Divider"
    summary = "Computes (Upper:A) / B. Quot is the quotient, Rem the remainder."
    symbol, top_label, bottom_label = "÷", "upper", "rem"

    def all_ports(self):
        return self.std_ports("A", "B", "Quot", ("Upper", 0), "Rem", self.w, self.w)

    def evaluate(self, v):
        b = v["B"]
        if b == 0:                      # Logisim's own behaviour: the quotient is just A, the remainder 0
            return {"Quot": v["A"], "Rem": 0}
        n = (v.get("Upper", 0) << self.w) | v["A"]
        return {"Quot": (n // b) & mask(self.w), "Rem": n % b}
