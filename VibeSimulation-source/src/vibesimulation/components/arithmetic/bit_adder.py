"""Bit adder (Logisim: Arithmetic > Bit Adder): counts how many input bits are 1."""
from ...core.model import Attr, make_port
from ..registry import register
from .arith_base import SquareArith, WIDTH


@register
class BitAdder(SquareArith):
    type_name = "BitAdder"
    aliases = ('Bit Adder',)
    logisim_name = "BitAdder"
    summary = "Counts the 1 bits across all inputs."
    attrs_spec = (WIDTH, Attr("inputs", "int", 3, "Number of inputs", 1, 64))
    symbol = "add"

    def body(self):
        ys = self.in_ys()
        return (-40, min(-20, ys[0] - 5), 0, max(20, ys[-1] + 5))

    def in_ys(self):
        n = self.attrs["inputs"]
        if n == 2: return [-10, 10]
        return [10 * (i - (n // 2 if n % 2 else n // 2 - 1)) for i in range(n)]

    def all_ports(self):
        n, b = self.attrs["inputs"], self.body()
        ow = max(1, (self.w * n).bit_length())
        return [make_port(f"In{i}", "in", self.w, -40, y, b, "") for i, y in enumerate(self.in_ys())] + [make_port("Out", "out", ow, 0, 0, b, "")]

    def evaluate(self, v):
        return {"Out": sum(bin(v[f"In{i}"]).count("1") for i in range(self.attrs["inputs"]))}

    def logisim_attrs(self):
        return {"width": self.w, "inputs": self.attrs["inputs"]}
