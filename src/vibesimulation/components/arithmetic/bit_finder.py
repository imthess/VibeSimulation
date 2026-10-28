"""Bit finder (Logisim: Arithmetic > Bit Finder): position of the lowest/highest 1 or 0."""
from ...core.bits import clog2
from ...core.model import Attr, make_port
from ..registry import register
from .arith_base import SquareArith, WIDTH


@register
class BitFinder(SquareArith):
    type_name = "BitFinder"
    aliases = ('Bit Finder',)
    logisim_name = "BitFinder"
    summary = "Index of the lowest or highest 1 (or 0) bit; Present tells whether one exists."
    attrs_spec = (WIDTH, Attr("find", "choice", "low1", "Find", choices=("low1", "high1", "low0", "high0")))
    symbol = "find"

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", self.w, -40, 0, b, ""), make_port("Index", "out", clog2(self.w), 0, 0, b, ""),
                make_port("Present", "out", 1, -20, 20, b, "", optional=True)]

    def evaluate(self, v):
        want = 1 if self.attrs["find"].endswith("1") else 0
        idx = [i for i in range(self.w) if (v["In"] >> i & 1) == want]
        if not idx:
            return {"Index": 0, "Present": 0}
        return {"Index": idx[0] if self.attrs["find"].startswith("low") else idx[-1], "Present": 1}

    def logisim_attrs(self):
        return {"width": self.w, "type": self.attrs["find"]}
