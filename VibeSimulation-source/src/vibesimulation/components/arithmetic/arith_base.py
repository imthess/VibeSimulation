"""Shared pieces of the arithmetic parts: a 40x40 square body with two operands on the left."""
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..shapes import draw_pins

WIDTH = Attr("width", "int", 4, "Data bits", 1, 64)


class SquareArith(Component):
    library, category = "Arithmetic", "Arithmetic"
    attrs_spec = (WIDTH,)
    symbol = ""
    top_label = ""      # grey caption near the top pin
    bottom_label = ""   # grey caption near the bottom pin

    def body(self):
        return (-40, -20, 0, 20)

    @property
    def w(self):
        return self.attrs["width"]

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        if self.symbol:
            r.text(ax - 12, ay, self.symbol, 20, OUTLINE, True, "c", ctx.body_tags)
        if self.top_label: r.text(ax - 20, ay - 17, self.top_label, 8, MUTED, False, "n", ctx.body_tags)
        if self.bottom_label: r.text(ax - 20, ay + 17, self.bottom_label, 8, MUTED, False, "s", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"width": self.w}

    def std_ports(self, a, b, out, top=None, bottom=None, tw=None, bw=None):
        """Operands A,B on the left, result on the right, optional pins on the top and bottom edge."""
        bd = self.body()
        ports = [make_port(a, "in", self.w, -40, -10, bd, a), make_port(b, "in", self.w, -40, 10, bd, b),
                 make_port(out, "out", self.w, 0, 0, bd, out)]
        if top: ports.append(make_port(top[0], "in", tw or 1, -20, -20, bd, top[0], optional=True, default=top[1]))
        if bottom: ports.append(make_port(bottom, "out", bw or 1, -20, 20, bd, bottom, optional=True))
        return ports
