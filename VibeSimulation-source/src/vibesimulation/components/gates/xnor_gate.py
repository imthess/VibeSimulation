"""XNOR gate."""
from functools import reduce

from ...core.bits import mask
from ..registry import register
from .gate_base import Gate


@register
class XnorGate(Gate):
    """XOR followed by NOT (1 when an even number of inputs are 1)."""
    type_name = "XNOR"
    logisim_name = "XNOR Gate"
    summary = "XOR followed by NOT (1 when an even number of inputs are 1)."
    kind = "OR"
    bubble = True
    xor = True
    gate_width = 70

    @classmethod
    def combine(cls, vals, width):
        return ~reduce(lambda a, b: a ^ b, vals)
