"""Odd Parity gate."""
from ...core.model import Attr
from ..registry import register
from .gate_base import Gate


@register
class OddParity(Gate):
    """Output is 1 when an odd number of input bits are 1."""
    type_name = "ODDPARITY"
    aliases = ('Odd Parity',)
    logisim_name = "Odd Parity"
    summary = "1 when an odd number of input bits are 1."
    kind = "BOX"
    gate_width = 50
    symbol = "2k+1"

    def out_width(self):
        return 1

    def body(self):
        h = self.height()
        return (-self.gate_width, -h // 2, 0, h // 2)

    @classmethod
    def combine(cls, vals, width):
        ones = sum(bin(v).count("1") for v in vals)
        return ones % 2

    def draw(self, r, ax, ay, ctx):
        from ..shapes import draw_box, draw_pins
        draw_box(r, ax, ay, self.body(), ctx, self.symbol, (), 12)
        draw_pins(r, ax, ay, self, ctx)
