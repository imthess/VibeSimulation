"""NAND gate."""
from functools import reduce

from ...core.bits import mask
from ..registry import register
from .gate_base import Gate


@register
class NandGate(Gate):
    """AND followed by NOT."""
    type_name = "NAND"
    logisim_name = "NAND Gate"
    summary = "AND followed by NOT."
    kind = "AND"
    dominant = 0
    bubble = True
    xor = False
    gate_width = 60

    @classmethod
    def combine(cls, vals, width):
        return ~reduce(lambda a, b: a & b, vals)
