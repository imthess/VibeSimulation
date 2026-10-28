"""XOR gate."""
from functools import reduce

from ...core.bits import mask
from ..registry import register
from .gate_base import Gate


@register
class XorGate(Gate):
    """Output is 1 when an odd number of inputs are 1."""
    type_name = "XOR"
    logisim_name = "XOR Gate"
    summary = "Output is 1 when an odd number of inputs are 1."
    kind = "OR"
    bubble = False
    xor = True
    gate_width = 60

    @classmethod
    def combine(cls, vals, width):
        return reduce(lambda a, b: a ^ b, vals)
