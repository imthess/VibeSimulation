"""Decoder (Logisim: Plexers > Decoder): turns a binary number into a single active output line."""
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins
from .multiplexer import trapezoid


@register
class Decoder(Component):
    type_name = "DECODER"
    aliases = ('Decoder',)
    logisim_name = "Decoder"
    library, category = "Plexers", "Plexers"
    summary = "Decoder: exactly one output (the one numbered by the input) is 1."
    attrs_spec = (Attr("select", "int", 2, "Select bits", 1, 5),)

    @property
    def n(self):
        return 1 << self.attrs["select"]

    def out_xy(self, i):
        n = self.n
        return (10, -30 + 20 * i) if n == 2 else (20, -10 * (n - i))

    def body(self):
        n = self.n
        if n == 2: return (-20, -45, 10, 5)
        return (-20, -10 * n - 10, 20, 10)

    def all_ports(self):
        b = self.body()
        ports = [make_port("Sel", "in", self.attrs["select"], 0, 0, b, "")]
        ports.append(make_port("En", "in", 1, -10, 0, b, "", optional=True, default=1))
        for i in range(self.n):
            x, y = self.out_xy(i)
            ports.append(make_port(f"Out{i}", "out", 1, x, y, b, str(i)))
        return ports

    handles_error = True

    def evaluate(self, v):
        en = v.get("En", 1)
        if en == 0: return {f"Out{i}": 0 for i in range(self.n)}      # disabled: all outputs 0 even if Sel is unknown
        if en is None or v["Sel"] is None: return {f"Out{i}": None for i in range(self.n)}
        return {f"Out{i}": int(i == v["Sel"]) for i in range(self.n)}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        pts = [(ax + x0, ay + y0 + 10 if self.n > 2 else ay + y0 + 6), (ax + x1, ay + y0), (ax + x1, ay + y1), (ax + x0, ay + y1 - (10 if self.n > 2 else 6))]
        r.polygon(pts, FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + (x0 + x1) / 2, ay + (y0 + y1) / 2 + 2, "Decd", 11, OUTLINE, True, "c", ctx.body_tags)
        x, y = self.out_xy(0)
        r.text(ax + x - 3, ay + y, "0", 8, MUTED, False, "e", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"select": self.attrs["select"], "enable": "true" if self.ins.get("En") is not None else "false"}
