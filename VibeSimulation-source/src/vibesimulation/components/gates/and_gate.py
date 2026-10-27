"""AND gate."""
from functools import reduce

from ...core.bits import mask
from ..registry import register
from .gate_base import Gate


@register
class AndGate(Gate):
    """Output is 1 only when every input is 1."""
    type_name = "AND"
    logisim_name = "AND Gate"
    summary = "Output is 1 only when every input is 1."
    kind = "AND"
    dominant = 0
    bubble = False
    xor = False
    gate_width = 50

    @classmethod
    def combine(cls, vals, width):
        return reduce(lambda a, b: a & b, vals)
