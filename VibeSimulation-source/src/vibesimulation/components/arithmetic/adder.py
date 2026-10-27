"""Adder (Logisim: Arithmetic > Adder). With one bit and no carry-in it is a half adder; with carry-in a full adder."""
from ...core.bits import mask
from ..registry import register
from .arith_base import SquareArith


@register
class Adder(SquareArith):
    type_name = "Adder"
    aliases = ('HalfAdder', 'FullAdder', 'ParallelAdder', 'Half Adder', 'Full Adder')
    logisim_name = "Adder"
    summary = "Adds A + B (+ Cin). 1 bit: half adder (no Cin) / full adder (with Cin). More bits: parallel adder."
    symbol, top_label, bottom_label = "+", "c in", "c out"

    def all_ports(self):
        return self.std_ports("A", "B", "Sum", ("Cin", 0), "Cout")

    def evaluate(self, v):
        t = v["A"] + v["B"] + v.get("Cin", 0)
        return {"Sum": t & mask(self.w), "Cout": t >> self.w}
