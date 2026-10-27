"""Subtractor (Logisim: Arithmetic > Subtractor)."""
from ...core.bits import mask
from ..registry import register
from .arith_base import SquareArith


@register
class Subtractor(SquareArith):
    type_name = "Subtractor"
    logisim_name = "Subtractor"
    summary = "Computes A - B - Bin. Bout is 1 when a borrow is needed."
    symbol, top_label, bottom_label = "−", "b in", "b out"

    def all_ports(self):
        return self.std_ports("A", "B", "Diff", ("Bin", 0), "Bout")

    def evaluate(self, v):
        t = v["A"] - v["B"] - v.get("Bin", 0)
        return {"Diff": t & mask(self.w), "Bout": int(t < 0)}
