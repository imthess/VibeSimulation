"""Buffer gate."""
from ..registry import register
from .gate_base import Gate


@register
class Buffer(Gate):
    """Output equals the input (used to clean up a signal)."""
    type_name = "BUFFER"
    aliases = ('Buffer',)
    logisim_name = "Buffer"
    summary = "Output equals the input."
    kind = "NOT"
    single_input = True
    gate_width = 20

    @classmethod
    def combine(cls, vals, width):
        return vals[0]
