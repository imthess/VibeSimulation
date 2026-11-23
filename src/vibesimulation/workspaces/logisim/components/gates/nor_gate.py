"""NOR gate."""
from functools import reduce

from vibesimulation.workspaces.logisim.core.bits import mask
from vibesimulation.workspaces.logisim.components.registry import register
from vibesimulation.workspaces.logisim.components.gates.gate_base import Gate
@register
class NorGate(Gate):
    """OR followed by NOT."""
    type_name = "NOR"
    logisim_name = "NOR Gate"
    summary = "OR followed by NOT."
    kind = "OR"
    dominant = 1
    bubble = True
    xor = False
    gate_width = 60

    @classmethod
    def combine(cls, vals, width):
        return ~reduce(lambda a, b: a | b, vals)
