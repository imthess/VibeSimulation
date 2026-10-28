"""Demultiplexer (Logisim: Plexers > Demultiplexer): sends the input to one of several outputs."""
from ...core.bits import mask
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins
from .multiplexer import trapezoid


@register
class Demultiplexer(Component):
    type_name = "DEMUX"
    aliases = ('Demultiplexer',)
    logisim_name = "Demultiplexer"
    library, category = "Plexers", "Plexers"
    summary = "Demultiplexer: the input is copied to the output chosen by the select pin(s); others are 0."
    attrs_spec = (Attr("select", "int", 1, "Select bits", 1, 5), Attr("width", "int", 1, "Data bits", 1, 64))

    @property
    def n(self):
        return 1 << self.attrs["select"]

    def _geom(self):
        n = self.n
        return (30 if n == 2 else 40), 5 * n + 10, (10 if n == 2 else 20)

    def sel_y(self):
        return 20 if self.n <= 4 else 5 * self.n

    def body(self):
        xr, half, _ = self._geom()
        return (0, -half, xr, half)

    def all_ports(self):
        n, w, s = self.n, self.attrs["width"], self.attrs["select"]
        xr = self._geom()[0]
        b = self.body()
        ys = [-10, 10] if n == 2 else [-5 * n + 10 * i for i in range(n)]
        ports = [make_port("In", "in", w, 0, 0, b, "")]
        ports.append(make_port("Sel", "in", s, 20, self.sel_y(), b, ""))
        ports.append(make_port("En", "in", 1, 10, self.sel_y(), b, "", optional=True, default=1))
        ports += [make_port(f"Out{i}", "out", w, xr, ys[i], b, str(i)) for i in range(n)]
        return ports

    handles_error = True

    def evaluate(self, v):
        en = v.get("En", 1)
        if en == 0: return {f"Out{i}": 0 for i in range(self.n)}      # disabled: every output is 0, whatever Sel is
        if en is None or v["Sel"] is None: return {f"Out{i}": None for i in range(self.n)}
        return {f"Out{i}": (v["In"] if i == v["Sel"] else 0) for i in range(self.n)}

    def draw(self, r, ax, ay, ctx):
        xr, half, inset = self._geom()
        r.polygon(trapezoid(ax, ay, 0, xr, half, inset, flip=True), FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + xr / 2 - 4, ay + 2, "DMX", 11, OUTLINE, True, "c", ctx.body_tags)
        r.text(ax + xr - 3, ay + self.all_ports()[3].dy, "0", 8, MUTED, False, "e", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        return {"select": self.attrs["select"], "width": self.attrs["width"],
                "enable": "true" if self.ins.get("En") is not None else "false"}
