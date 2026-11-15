"""PNG pictures of a circuit, drawn with Pillow (Bridge pattern: PilRenderer is one more Renderer, like the screen and the PDF).

Used for "download as picture" and to make training pictures for the AI import (see ``dev/finetune``)."""
import os

from ..core.render import ACCENT, BAD, FILL, LABEL, MUTED, OFF, ON, OUTLINE, Renderer
from ..layout.painter import CircuitPainter, extent

LIGHT = {OUTLINE: "#151a2d", FILL: "#ffffff", MUTED: "#6a7285", ON: "#16a34a", OFF: "#9aa3b5", LABEL: "#4f46e5", ACCENT: "#4f46e5", BAD: "#d92d20"}
MONO = {OUTLINE: "#000000", FILL: "#ffffff", MUTED: "#000000", ON: "#000000", OFF: "#000000", LABEL: "#000000", ACCENT: "#000000", BAD: "#000000"}   # black on white, like a textbook
_FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
          "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf")
_BOLD = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def _font(size, bold=False):
    from PIL import ImageFont
    for p in (_BOLD if bold else _FONTS):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, max(6, int(round(size))))
            except Exception: pass
    return ImageFont.load_default(max(6, int(round(size))))


class PilRenderer(Renderer):
    """Draws onto a Pillow ImageDraw. ``tf`` maps circuit units to pixels; ``s`` is the pixels per unit."""
    def __init__(self, draw, tf, scale, palette=LIGHT):
        self.d, self.tf, self.s, self.pal = draw, tf, scale, palette

    def _c(self, role):
        return self.pal.get(role, role) if role else None

    def _w(self, w):
        return max(1, int(round(w * self.s * 0.9)))

    def line(self, pts, width=2, role=OUTLINE, tags=()):
        P = [self.tf(*q) for q in pts]; w = self._w(width)
        self.d.line(P, fill=self._c(role), width=w, joint="curve")
        for x, y in (P[0], P[-1]) if w > 2 else ():
            self.d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=self._c(role))

    def polygon(self, pts, fill=FILL, outline=OUTLINE, width=2, tags=()):
        P = [self.tf(*q) for q in pts]
        self.d.polygon(P, fill=self._c(fill))
        if outline: self.d.line(P + [P[0]], fill=self._c(outline), width=self._w(width), joint="curve")

    def circle(self, cx, cy, r, fill=FILL, outline=OUTLINE, width=2, tags=()):
        X, Y = self.tf(cx, cy); R = r * self.s
        self.d.ellipse((X - R, Y - R, X + R, Y + R), fill=self._c(fill), outline=self._c(outline), width=self._w(width) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill=FILL, outline=OUTLINE, width=2, tags=()):
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width)

    def text(self, x, y, s, size=10, role=MUTED, bold=False, anchor="c", tags=()):
        X, Y = self.tf(x, y)
        v = "t" if anchor.startswith("n") else "b" if anchor.startswith("s") else "m"
        h = "l" if anchor.endswith("w") else "r" if anchor.endswith("e") else "m"
        self.d.text((X, Y), str(s), fill=self._c(role), font=_font(size * self.s * 1.25, bold), anchor=h + {"t": "a", "m": "m", "b": "d"}[v])


def _canvas(box, scale, pad, bg):
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    W, H = int((x1 - x0) * scale + 2 * pad), int((y1 - y0) * scale + 2 * pad)
    im = Image.new("RGB", (W, H), bg)
    return im, ImageDraw.Draw(im), (lambda x, y: ((x - x0) * scale + pad, (y - y0) * scale + pad))


def digital_png(circuit, layout=None, scale=1.5, pad=30, palette=LIGHT, bg="#ffffff", invals=None):
    """Picture of a digital circuit (``core.model.Circuit``). Returns a Pillow image."""
    from ..layout.engine import LayoutEngine
    layout = layout or LayoutEngine().build(circuit)
    invals = invals or {}
    im, d, tf = _canvas(extent(layout), scale, pad, bg)
    CircuitPainter(PilRenderer(d, tf, scale, palette)).paint(layout, circuit, circuit.simulate(invals), invals)
    return im


def analog_png(netlist, layout=None, scale=1.5, pad=30, palette=LIGHT, bg="#ffffff"):
    """Picture of an analog schematic (``analog.netlist.Netlist``). Returns a Pillow image."""
    from ..workspaces.multisim.engine.layout import SchematicBuilder
    from ..workspaces.multisim.engine.painter import paint_schematic
    layout = layout or SchematicBuilder().build(netlist)
    im, d, tf = _canvas(layout.extent(), scale, pad, bg)
    paint_schematic(PilRenderer(d, tf, scale, palette), layout, None, 4, tagged=False)
    return im
