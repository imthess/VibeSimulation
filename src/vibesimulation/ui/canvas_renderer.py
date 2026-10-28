"""Renderer that draws onto a Tk Canvas (the screen side of the Bridge pattern)."""
from ..core.render import ACCENT, BAD, FILL, LABEL, MUTED, OFF, ON, OUTLINE, Renderer

ANCHOR = {"c": "center", "w": "w", "e": "e", "n": "n", "s": "s", "sw": "sw", "se": "se", "nw": "nw", "ne": "ne"}


class TkRenderer(Renderer):
    def __init__(self, canvas, palette, sans, scale=1.0, ox=0.0, oy=0.0):
        self.c, self.P, self.sans, self.s, self.ox, self.oy = canvas, palette, sans, scale, ox, oy

    def color(self, role):
        P = self.P
        return {OUTLINE: P["pin"], FILL: P["gatefill"], MUTED: P["muted"], ON: P["on"], OFF: P["off"], LABEL: P["label"],
                ACCENT: P["accent"], BAD: P["bad"]}.get(role, role) if role else ""

    def T(self, x, y):
        return self.ox + x * self.s, self.oy + y * self.s

    def _w(self, width):
        return max(1.2, width * self.s)

    def line(self, pts, width=2, role=OUTLINE, tags=()):
        flat = [v for p in pts for v in self.T(*p)]
        self.c.create_line(*flat, fill=self.color(role), width=self._w(width), capstyle="round", joinstyle="round", tags=tags)

    def polygon(self, pts, fill=FILL, outline=OUTLINE, width=2, tags=()):
        flat = [v for p in pts for v in self.T(*p)]
        self.c.create_polygon(*flat, fill=self.color(fill), outline=self.color(outline), width=self._w(width), joinstyle="round", tags=tags)

    def circle(self, cx, cy, r, fill=FILL, outline=OUTLINE, width=2, tags=()):
        x, y = self.T(cx, cy); rr = max(1.5, r * self.s)
        self.c.create_oval(x - rr, y - rr, x + rr, y + rr, fill=self.color(fill), outline=self.color(outline), width=self._w(width) if outline else 0, tags=tags)

    def rect(self, x0, y0, x1, y1, fill=FILL, outline=OUTLINE, width=2, tags=()):
        a, b = self.T(x0, y0); c, d = self.T(x1, y1)
        self.c.create_rectangle(a, b, c, d, fill=self.color(fill), outline=self.color(outline), width=self._w(width), tags=tags)

    def text(self, x, y, s, size=10, role=MUTED, bold=False, anchor="c", tags=()):
        X, Y = self.T(x, y)
        font = (self.sans, max(6, round(size * self.s * 0.82))) + (("bold",) if bold else ())
        self.c.create_text(X, Y, text=s, fill=self.color(role), font=font, anchor=ANCHOR[anchor], tags=tags)
