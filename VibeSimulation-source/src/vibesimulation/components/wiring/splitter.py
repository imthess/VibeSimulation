"""Splitter (one wide signal -> several narrower ones) and Combiner (the reverse)."""
from ...core.bits import mask
from ...core.model import Attr, Component, make_port
from ...core.render import OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


class _Fan(Component):
    library, category = "Wiring", "Wiring"
    attrs_spec = (Attr("widths", "list", [1, 1, 1, 1], "Bits in each part (lowest bits first)"),)
    west = False

    def parts(self):
        return self.attrs["widths"]

    def bus_width(self):
        return sum(self.parts())

    def part_y(self, i):
        k = len(self.parts())
        return 10 * (i - k // 2)

    def starts(self):
        s, out = 0, []
        for w in self.parts():
            out.append(s); s += w
        return out

    def body(self):
        k = len(self.parts())
        top, bot = -10 * (k // 2), 10 * (k - 1 - k // 2)
        return (-20, top, 0, bot) if self.west else (0, top, 20, bot)

    def draw(self, r, ax, ay, ctx):
        k, sgn = len(self.parts()), -1 if self.west else 1
        top, bot = ay - 10 * (k // 2), ay + 10 * (k - 1 - k // 2)
        r.line([(ax, ay), (ax + sgn * 10, ay)], 3, OUTLINE, ctx.body_tags)
        r.line([(ax + sgn * 10, top), (ax + sgn * 10, bot)], 3, OUTLINE, ctx.body_tags)
        for i, (s, w) in enumerate(zip(self.starts(), self.parts())):
            y = ay + self.part_y(i)
            r.line([(ax + sgn * 10, y), (ax + sgn * 20, y)], 2 if w == 1 else 3, OUTLINE, ctx.body_tags)
            r.text(ax + sgn * 15, y - 2, str(s) if w == 1 else f"{s}-{s + w - 1}", 7, MUTED, False, "s", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        parts = self.parts(); k = len(parts); a = {"fanout": k, "incoming": self.bus_width(), "appear": "center"}
        if self.west: a["facing"] = "west"
        bit = 0
        for i, w in enumerate(parts):
            for _ in range(w):
                a[f"bit{bit}"] = i; bit += 1
        return a

    def check(self):
        return [] if len(self.parts()) <= 32 else ["Too many parts"]


@register
class Splitter(_Fan):
    """Splits a multi-bit signal into parts, e.g. a 4-bit bus into four single wires."""
    type_name = "Splitter"
    logisim_name = "Splitter"
    summary = "Splits a bus into several narrower signals (Out0 holds the lowest bits)."

    def all_ports(self):
        b = self.body()
        return ([make_port("In", "in", self.bus_width(), 0, 0, b, "")] +
                [make_port(f"Out{i}", "out", w, 20, self.part_y(i), b, "") for i, w in enumerate(self.parts())])

    def evaluate(self, v):
        x = v["In"]
        return {f"Out{i}": (x >> s) & mask(w) for i, (s, w) in enumerate(zip(self.starts(), self.parts()))}


@register
class Combiner(_Fan):
    """Joins several signals into one multi-bit signal."""
    type_name = "Combiner"
    logisim_name = "Splitter"
    summary = "Joins several signals into one bus (In0 provides the lowest bits)."
    west = True

    def all_ports(self):
        b = self.body()
        return ([make_port(f"In{i}", "in", w, -20, self.part_y(i), b, "") for i, w in enumerate(self.parts())] +
                [make_port("Out", "out", self.bus_width(), 0, 0, b, "")])

    def evaluate(self, v):
        x = 0
        for i, (s, w) in enumerate(zip(self.starts(), self.parts())):
            x |= (v[f"In{i}"] & mask(w)) << s
        return {"Out": x}
