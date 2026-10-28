"""NOT gate (inverter)."""
from ..registry import register
from .gate_base import Gate


@register
class NotGate(Gate):
    """Output is the opposite of the input."""
    type_name = "NOT"
    logisim_name = "NOT Gate"
    summary = "Output is the opposite of the input."
    kind = "NOT"
    bubble = True
    single_input = True
    gate_width = 30

    @classmethod
    def combine(cls, vals, width):
        return ~vals[0]
