"""What is behind the round button and the bar, and how the glass shapes are painted.

Tk cannot make a widget see-through, so the round button and the rounded bar are painted with Pillow on top of a picture of what is behind
them: ``Under.render`` paints the widgets (and glass pictures) under the overlay, layer by layer, and the corners blend into that picture,
so there are no square corners, whichever page is open. Without Pillow the shapes are flat but still work."""
import math
import tkinter as tk

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageTk
except Exception:                                                        # Pillow missing: flat shapes
    Image = ImageChops = ImageDraw = ImageFilter = ImageOps = ImageTk = None


def _rgb(ctx, c):
    r, g, b = ctx.root.winfo_rgb(c); return (r >> 8, g >> 8, b >> 8)


# ------------------------------------------------------------------------------------------------- what is behind the overlay
class Under:
    """Colour of whatever is drawn at a screen point, found by walking the widget tree (stacking order) instead of restacking windows."""
    def __init__(self, ctx, skip):
        self.ctx, self.skip = ctx, skip; self.root = ctx.root

    def _children(self, w, cache):
        k = ("c", w)
        if k not in cache:
            try: cache[k] = [c for c in w.winfo_children() if c not in self.skip and not isinstance(c, tk.Toplevel)]
            except tk.TclError: cache[k] = []
        return cache[k]

    def _box(self, w, cache):
        if w not in cache:
            try: cache[w] = (w.winfo_ismapped(), w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height())
            except tk.TclError: cache[w] = (False, 0, 0, 0, 0)
        return cache[w]

    def widget_at(self, x, y, cache):
        w = self.root
        while True:
            for ch in reversed(self._children(w, cache)):                  # winfo_children is in stacking order, lowest first
                ok, rx, ry, cw, chh = self._box(ch, cache)
                if ok and rx <= x < rx + cw and ry <= y < ry + chh: w = ch; break
            else: return w

    def _pixel(self, img, w, x, y):
        try:
            r = self.root.tk.call(str(img), "get", max(0, x - w.winfo_rootx()), max(0, y - w.winfo_rooty()))
            v = [int(t) for t in (r if isinstance(r, (tuple, list)) else str(r).split())][:3]
            return tuple(v) if len(v) == 3 else None
        except (tk.TclError, ValueError): return None

    def colour(self, x, y, cache):
        P = self.ctx.P; w = self.widget_at(x, y, cache)
        try:
            img = getattr(w, "_gimg", None) if isinstance(w, tk.Canvas) else getattr(w, "image", None) if isinstance(w, tk.Label) else None
            if img is not None:
                px = self._pixel(img, w, x, y)
                if px: return px
            u = self.ctx.glass.under.get(w)                              # a frame whose glass picture lies behind its children
            if u is not None and getattr(u[0], "image", None) is not None:
                px = self._pixel(u[0].image, w, x, y)
                if px: return px
            return _rgb(self.ctx, w.cget("bg"))
        except (tk.TclError, AttributeError): return _rgb(self.ctx, P["card"])

    def render(self, x0, y0, W, H):
        """A picture of what lies under the screen rectangle (x0, y0, W, H): the widgets below the overlay painted in stacking order
        (glass pictures are pasted, other widgets are filled with their background)."""
        P = self.ctx.P; im = Image.new("RGB", (max(1, W), max(1, H)), _rgb(self.ctx, P["bg"])); cache = {}; pics = {}

        def pic(photo):
            if photo not in pics:
                try: pics[photo] = ImageTk.getimage(photo).convert("RGB")
                except Exception: pics[photo] = None
            return pics[photo]

        def paint(w):
            for ch in self._children(w, cache):
                ok, rx, ry, cw, chh = self._box(ch, cache)
                ix0, iy0, ix1, iy1 = max(rx, x0), max(ry, y0), min(rx + cw, x0 + W), min(ry + chh, y0 + H)
                if not ok or ix0 >= ix1 or iy0 >= iy1: continue
                photo = getattr(ch, "_gimg", None) if isinstance(ch, tk.Canvas) else getattr(ch, "image", None) if isinstance(ch, tk.Label) else None
                src = pic(photo) if photo is not None else None
                try: bg = _rgb(self.ctx, ch.cget("bg"))
                except (tk.TclError, AttributeError): bg = _rgb(self.ctx, P["card"])
                im.paste(bg, (ix0 - x0, iy0 - y0, ix1 - x0, iy1 - y0))
                if src is not None:
                    cx1, cy1 = min(ix1 - rx, src.width), min(iy1 - ry, src.height)
                    if cx1 > ix0 - rx and cy1 > iy0 - ry: im.paste(src.crop((ix0 - rx, iy0 - ry, cx1, cy1)), (ix0 - x0, iy0 - y0))
                paint(ch)
        paint(self.root); return im


def _mask(W, H, box, r, S=4):
    m = Image.new("L", (W * S, H * S), 0); d = ImageDraw.Draw(m)
    (d.ellipse if r is None else (lambda b, fill: d.rounded_rectangle(b, radius=r * S, fill=fill)))([v * S for v in box], fill=255)
    return m.resize((W, H), Image.LANCZOS)


def _ring(mask, W, H, box, r, inset=1.2):
    x1, y1, x2, y2 = box; i = inset
    inner = _mask(W, H, (x1 + i, y1 + i, x2 - i, y2 - i), None if r is None else max(0, r - i))
    return ImageChops.subtract(mask, inner)


STAR = {False: ((59, 130, 246), (139, 92, 246), (236, 72, 153)), True: ((96, 165, 250), (167, 139, 250), (244, 114, 182))}      # blue -> violet -> pink (light, dark theme)
_GLYPH = {}


def _glyph_mask(n, d, kind):
    """Mask (n x n) of the star (kind 'star') or the cross (kind 'close'), drawn 4x larger and scaled down for smooth edges."""
    key = (n, d, kind)
    if key in _GLYPH: return _GLYPH[key]
    S = 4; m = Image.new("L", (n * S, n * S), 0); dr = ImageDraw.Draw(m); c = n * S / 2
    if kind == "star":
        def sparkle(cx, cy, R):                                         # a four-pointed star with concave sides (an astroid)
            pts = [(cx + R * math.cos(t) ** 3, cy + R * math.sin(t) ** 3) for t in [i * math.pi / 90 for i in range(180)]]
            dr.polygon(pts, fill=255)
        R = d * S * .27; sparkle(c - d * S * .02, c + d * S * .03, R); sparkle(c + d * S * .21, c - d * S * .22, R * .34)
    else:
        r = d * S * .15; w = max(3, int(d * S * .075))
        dr.line([(c - r, c - r), (c + r, c + r)], fill=255, width=w); dr.line([(c - r, c + r), (c + r, c - r)], fill=255, width=w)
        for x, y in ((c - r, c - r), (c + r, c + r), (c - r, c + r), (c + r, c - r)): dr.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=255)
    out = m.resize((n, n), Image.LANCZOS); _GLYPH[key] = out; return out


def glass_disc(ctx, n, d, bg, hot=False, closing=False):
    """The round button: a see-through frosted-glass disc (the colours behind it, softly blurred, with a lit rim, a gloss and a faint shadow)
    and a coloured star (a cross while the bar is open). `bg` is a picture of what is behind the button."""
    dark = ctx.dark; M = (n - d) / 2; box = (M, M, M + d - 1, M + d - 1); W = (255, 255, 255)
    mask = _mask(n, n, box, None)
    sh = ImageChops.offset(mask, 0, 2).filter(ImageFilter.GaussianBlur(3))
    out = Image.composite(Image.new("RGB", (n, n), (0, 0, 0)), bg, ImageChops.subtract(sh, mask.point(lambda v: v // 2)).point(lambda v: int(v * (.34 if dark else .18))))
    glass = Image.blend(bg.filter(ImageFilter.GaussianBlur(4)), Image.new("RGB", (n, n), W), (.16 if dark else .34) + (.07 if hot else 0))      # frosted: blurred backdrop + a little white
    down = Image.linear_gradient("L").resize((n, n)); up = down.transpose(Image.FLIP_TOP_BOTTOM)
    glass = Image.composite(Image.new("RGB", (n, n), W), glass, ImageChops.multiply(mask, up).point(lambda v: int(v * (.26 if dark else .34))))   # sheen on the upper half
    glass = Image.composite(Image.new("RGB", (n, n), (0, 0, 0)), glass, ImageChops.multiply(mask, down.point(lambda v: v * v // 255)).point(lambda v: int(v * (.22 if dark else .08))))   # faint depth below
    out = Image.composite(glass, out, mask)
    gloss = Image.new("L", (n, n), 0); ImageDraw.Draw(gloss).ellipse([M + d * .16, M + d * .07, M + d * .66, M + d * .36], fill=255)
    out = Image.composite(Image.new("RGB", (n, n), W), out, ImageChops.multiply(gloss.filter(ImageFilter.GaussianBlur(3)), mask).point(lambda v: int(v * .22)))
    rim = _ring(mask, n, n, box, None, 1.3); lit = ImageChops.multiply(rim, up)
    out = Image.composite(Image.new("RGB", (n, n), W), out, rim.point(lambda v: int(v * (.30 if dark else .55) * (1.25 if hot else 1))))
    out = Image.composite(Image.new("RGB", (n, n), W), out, lit.point(lambda v: int(v * .40)))
    gm = _glyph_mask(n, d, "close" if closing else "star"); c1, c2, c3 = STAR[dark]
    diag = Image.blend(Image.linear_gradient("L").resize((n, n)), Image.linear_gradient("L").rotate(90).resize((n, n)), .5)
    ink = ImageOps.colorize(diag, black=c1, white=c3, mid=c2)
    out = Image.composite(Image.new("RGB", (n, n), c2), out, gm.filter(ImageFilter.GaussianBlur(3.5)).point(lambda v: int(v * .45)))        # soft glow of the star
    return Image.composite(ink, out, gm)


def panel_image(ctx, W, H, M, r, fill, line, bg):
    """The rounded bar: card colour, thin border, soft shadow, blended into `bg`."""
    dark = ctx.dark; box = (M, M, W - M - 1, H - M - 1); mask = _mask(W, H, box, r)
    sh = ImageChops.offset(mask, 0, 3).filter(ImageFilter.GaussianBlur(4))
    out = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, ImageChops.subtract(sh, mask.point(lambda v: v // 3)).point(lambda v: int(v * (.46 if dark else .24))))
    out = Image.composite(Image.new("RGB", (W, H), fill), out, mask)
    return out
