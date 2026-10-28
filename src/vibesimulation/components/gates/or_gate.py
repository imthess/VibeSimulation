"""OR gate."""
from functools import reduce

from ...core.bits import mask
from ..registry import register
from .gate_base import Gate


@register
class OrGate(Gate):
    """Output is 1 when any input is 1."""
    type_name = "OR"
    logisim_name = "OR Gate"
    summary = "Output is 1 when any input is 1."
    kind = "OR"
    dominant = 1
    bubble = False
    xor = False
    gate_width = 50

    @classmethod
    def combine(cls, vals, width):
        return reduce(lambda a, b: a | b, vals)
