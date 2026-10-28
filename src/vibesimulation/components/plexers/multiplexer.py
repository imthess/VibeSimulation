"""Multiplexer (Logisim: Plexers > Multiplexer): copies one of several inputs to the output."""
from ...core.bits import mask
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


def trapezoid(ax, ay, x0, x1, half, inset, flip=False):
    """Slanted-edge body used by MUX / DEMUX / Decoder. flip: the long edge is on the right."""
    if flip:
        return [(ax + x0, ay - half + inset), (ax + x1, ay - half), (ax + x1, ay + half), (ax + x0, ay + half - inset)]
    return [(ax + x0, ay - half), (ax + x1, ay - half + inset), (ax + x1, ay + half - inset), (ax + x0, ay + half)]


@register
class Multiplexer(Component):
    """Picks which of the data inputs In0, In1, ... reaches the output, according to Sel."""
    type_name = "MUX"
    aliases = ('Multiplexer',)
    logisim_name = "Multiplexer"
    library, category = "Plexers", "Plexers"
    summary = "Multiplexer: output = the input chosen by the select pin(s)."
    attrs_spec = (Attr("select", "int", 1, "Select bits", 1, 5), Attr("width", "int", 1, "Data bits", 1, 64))

    @property
    def n(self):
        return 1 << self.attrs["select"]

    def _geom(self):
        n = self.n
        return (-30 if n == 2 else -40), 5 * n + 10, (10 if n == 2 else 20)

    def sel_y(self):
        return 20 if self.n <= 4 else 5 * self.n

    def all_ports(self):
        n, w, s = self.n, self.attrs["width"], self.attrs["select"]
        xl, half, inset = self._geom()
        body = self.body()
        ys = [-10, 10] if n == 2 else [-5 * n + 10 * i for i in range(n)]
        ports = [make_port(f"In{i}", "in", w, xl, ys[i], body, str(i)) for i in range(n)]
        ports.append(make_port("Sel", "in", s, -20, self.sel_y(), body, ""))
        ports.append(make_port("En", "in", 1, -10, self.sel_y(), body, "", optional=True, default=1))
        ports.append(make_port("Out", "out", w, 0, 0, body, ""))
        return ports

    def body(self):
        xl, half, _ = self._geom()
        return (xl, -half, 0, half)

    handles_error = True

    def evaluate(self, v):
        if v.get("En", 1) == 0:
            return {"Out": 0}      # Logisim: a disabled multiplexer outputs floating; shown as 0 here
        if v.get("En", 1) is None or v["Sel"] is None: return {"Out": None}
        return {"Out": v[f"In{v['Sel']}"]}     # only the selected input matters (the others may be unknown)

    def active_ports(self):
        return [p for p in self.all_ports() if not (p.name == "En" and self.ins.get("En") is None)]

    def draw(self, r, ax, ay, ctx):
        xl, half, inset = self._geom()
        r.polygon(trapezoid(ax, ay, xl, 0, half, inset), FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + xl / 2 + 5, ay, "MUX", 11, OUTLINE, True, "c", ctx.body_tags)
        r.text(ax + xl + 3, ay + self.all_ports()[0].dy, "0", 8, MUTED, False, "w", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        a = {"select": self.attrs["select"], "width": self.attrs["width"]}
        a["enable"] = "true" if self.ins.get("En") is not None else "false"
        return a
