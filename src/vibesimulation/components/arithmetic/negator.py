"""Negator (Logisim: Arithmetic > Negator)."""
from ...core.bits import mask
from ...core.model import make_port
from ..registry import register
from .arith_base import SquareArith


@register
class Negator(SquareArith):
    type_name = "Negator"
    logisim_name = "Negator"
    summary = "Two's complement negative of the input (-A)."
    symbol = "-x"

    def all_ports(self):
        b = self.body()
        return [make_port("In", "in", self.w, -40, 0, b, ""), make_port("Out", "out", self.w, 0, 0, b, "")]

    def evaluate(self, v):
        return {"Out": (-v["In"]) & mask(self.w)}
