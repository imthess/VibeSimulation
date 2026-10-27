"""Orientation (Logisim's "Facing"): east, south, west, north.

Every component is written once, facing east. This module turns that single description into the other three:
pins and body are rotated by wrapping ``all_ports`` / ``body`` and the symbol is drawn through a renderer that
rotates what it is asked to draw. Rotation uses the same transform as Logisim: east (x, y), west (-x, -y),
north (y, -x), south (-y, x), around the component's Logisim location. Text stays upright, like in Logisim.
"""
import functools
from dataclasses import replace

FACINGS = ("east", "south", "west", "north")
_TURN = {"east": lambda x, y: (x, y), "west": lambda x, y: (-x, -y), "north": lambda x, y: (y, -x), "south": lambda x, y: (-y, x)}
_SIDE = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
_NAME = {v: k for k, v in _SIDE.items()}


def rot(facing, x, y):
    return _TURN[facing](x, y)


def rot_side(facing, side):
    return _NAME[rot(facing, *_SIDE[side])]


def rot_port(facing, p):
    dx, dy = rot(facing, p.dx, p.dy)
    return replace(p, dx=dx, dy=dy, side=rot_side(facing, p.side))


def rot_rect(facing, b):
    (ax, ay), (bx, by) = rot(facing, b[0], b[1]), rot(facing, b[2], b[3])
    return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def next_facing(f, step=1):
    return FACINGS[(FACINGS.index(f) + step) % 4]


def wrap_ports(fn):
    @functools.wraps(fn)
    def w(self, *a, **k):
        if self._raw or self.facing == "east": return fn(self, *a, **k)
        self._raw = 1
        try: res = fn(self, *a, **k)
        finally: self._raw = 0
        return [rot_port(self.facing, p) for p in res]
    return w


def wrap_body(fn):
    @functools.wraps(fn)
    def w(self, *a, **k):
        if self._raw or self.facing == "east": return fn(self, *a, **k)
        self._raw = 1
        try: res = fn(self, *a, **k)
        finally: self._raw = 0
        return rot_rect(self.facing, res)
    return w


def wrap_draw(fn):
    @functools.wraps(fn)
    def w(self, r, ax, ay, ctx, *a, **k):
        if self._raw or self.facing == "east": return fn(self, r, ax, ay, ctx, *a, **k)
        self._raw = 1
        try: return fn(self, RotRenderer(r, ax, ay, self.facing), ax, ay, ctx, *a, **k)
        finally: self._raw = 0
    return w


class RotRenderer:
    """Draws exactly what the component asks for, turned around (ax, ay)."""
    def __init__(self, r, ax, ay, facing):
        self._r, self._ax, self._ay, self._f = r, ax, ay, facing

    def _p(self, x, y):
        dx, dy = rot(self._f, x - self._ax, y - self._ay); return self._ax + dx, self._ay + dy

    def line(self, pts, *a, **k): return self._r.line([self._p(*p) for p in pts], *a, **k)

    def polygon(self, pts, *a, **k): return self._r.polygon([self._p(*p) for p in pts], *a, **k)

    def circle(self, cx, cy, rad, *a, **k):
        x, y = self._p(cx, cy); return self._r.circle(x, y, rad, *a, **k)

    def rect(self, x0, y0, x1, y1, *a, **k):
        (ax, ay), (bx, by) = self._p(x0, y0), self._p(x1, y1)
        return self._r.rect(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), *a, **k)

    def text(self, x, y, s, *a, **k):
        px, py = self._p(x, y); return self._r.text(px, py, s, *a, **k)

    def __getattr__(self, name): return getattr(self._r, name)
