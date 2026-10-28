"""Magnitude comparator (Logisim: Arithmetic > Comparator)."""
from ...core.bits import to_signed
from ...core.model import Attr, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins
from .arith_base import SquareArith, WIDTH


@register
class Comparator(SquareArith):
    type_name = "Comparator"
    aliases = ('MagnitudeComparator',)
    logisim_name = "Comparator"
    summary = "Compares A and B: GT (A>B), EQ (A=B) or LT (A<B) is 1."
    attrs_spec = (WIDTH, Attr("mode", "choice", "unsigned", "Number type", choices=("unsigned", "signed")))

    def all_ports(self):
        b = self.body()
        return [make_port("A", "in", self.w, -40, -10, b, "A"), make_port("B", "in", self.w, -40, 10, b, "B"),
                make_port("GT", "out", 1, 0, -10, b, ""), make_port("EQ", "out", 1, 0, 0, b, ""),
                make_port("LT", "out", 1, 0, 10, b, "")]

    def evaluate(self, v):
        a, b = v["A"], v["B"]
        if self.attrs["mode"] == "signed":
            a, b = to_signed(a, self.w), to_signed(b, self.w)
        return {"GT": int(a > b), "EQ": int(a == b), "LT": int(a < b)}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        for s, dy in ((">", -10), ("=", 0), ("<", 10)):
            r.text(ax - 6, ay + dy, s, 11, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"width": self.w, "mode": "twosComplement" if self.attrs["mode"] == "signed" else "unsigned"}
