"""Glass look: a soft aurora backdrop behind the whole window and frosted, rounded panels that sit on it.

Tk cannot make a widget see-through, so the glass is painted: every container carries a picture (an "underlay") made from the part of the
backdrop behind it, with a blurred, tinted, softly lit panel drawn on top (rim light, faint shadow). Widgets inside use the panel's mean colour.
Needs Pillow; without it everything falls back to flat colours."""
import tkinter as tk

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk
except Exception:                                                      # Pillow missing: flat colours
    Image = None


def _rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Glass:
    def __init__(self, ctx):
        self.ctx, self.root = ctx, ctx.root
        self.ok = Image is not None
        self.back = None; self.key = None; self.gen = 0; self.under = {}; self._job = {}; self._cache = {}

    # ---- the backdrop
    def enabled(self): return self.ok and self.ctx.cfg.get("glass", True)

    PRESETS = {"Aurora": None, "Sky": 210, "Lilac": 268, "Sunset": 18, "Mint": 160, "Rose": 340, "Slate": -1}

    def look(self):
        """(style, colour, picture, vividness) from the settings."""
        c = self.ctx.cfg
        return c.get("bg_style", "Aurora"), c.get("bg_color", "#7aa2ff"), c.get("bg_image", ""), int(c.get("bg_vivid", 60))

    def backdrop(self):
        """Window-sized backdrop picture (rebuilt when the window size, the theme or the background setting changes)."""
        import colorsys
        W, H = max(self.root.winfo_width(), 400), max(self.root.winfo_height(), 300); P = self.ctx.P; look = self.look()
        key = (W // 64, H // 64, self.ctx.dark, P["bg"], look)
        if key == self.key and self.back is not None and self.back.width >= W and self.back.height >= H: return self.back
        W, H = (W // 64 + 1) * 64, (H // 64 + 1) * 64; self.key = key; self._cache.clear()
        dark = self.ctx.dark; style, color, pic, vivid = look; vf = max(0.0, min(1.6, vivid / 60))
        if style == "Picture" and pic:
            try:
                from PIL import ImageOps
                im = ImageOps.fit(Image.open(pic).convert("RGB"), (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(14 + 10 * (1 - min(vf, 1))))
                im = Image.blend(im, Image.new("RGB", (W, H), (8, 10, 14) if dark else (255, 255, 255)), .62 if dark else .52 - .12 * min(vf, 1))
                self.back = im; return im
            except Exception: pass                                                                  # unreadable picture: fall back to Aurora
        def hsv(h, s_, v): r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, max(0, min(1, s_)), max(0, min(1, v))); return (round(r * 255), round(g * 255), round(b * 255))
        if style == "Custom":
            r, g, b = _rgb(color); h0, s0, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255); h0 *= 360; hues = [h0 - 20, h0 + 25, h0 + 8, h0 - 8]; sat = max(.25, s0)
        elif self.PRESETS.get(style) == -1:
            h0 = 215; hues = [h0, h0 + 10, h0 - 5, h0 + 5]; sat = .12
        elif self.PRESETS.get(style) is not None:
            h0 = self.PRESETS[style]; hues = [h0 - 22, h0 + 22, h0 + 10, h0 - 10]; sat = 1.0
        else:
            h0 = 215; hues = [205, 268, 25, 165]; sat = 1.0
        w, h = W // 8, H // 8                                          # paint small, enlarge smoothly
        if dark: a, b2, c = hsv(h0, .35 * sat, .075), hsv(h0 + 10, .35 * sat, .11), hsv(h0 - 10, .3 * sat, .08)
        else: a, b2, c = hsv(h0, .10 * sat, .97), hsv(h0 + 40, .08 * sat, .965), hsv(h0 - 40, .09 * sat, .97)
        im = Image.new("RGB", (w, h)); px = im.load()
        for y in range(h):
            for x in range(w):
                t = (x / w * 0.55 + y / h * 0.45); u = t * 2 if t < .5 else (t - .5) * 2; s0_, e0 = (a, b2) if t < .5 else (b2, c)
                px[x, y] = tuple(round(s0_[i] + (e0[i] - s0_[i]) * u) for i in range(3))
        spots = [(.16, .12, .30), (.86, .20, .32), (.70, .95, .30), (.05, .90, .26)]
        for (fx, fy, fr), hue in zip(spots, hues):
            col = hsv(hue, (.62 if dark else .34) * sat, .42 if dark else 1.0)
            al = min(.9, (.50 if dark else .62) * vf)
            m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m); r = fr * max(w, h)
            d.ellipse((fx * w - r, fy * h - r, fx * w + r, fy * h + r), fill=int(255 * al))
            m = m.filter(ImageFilter.GaussianBlur(r * .55)); im.paste(Image.new("RGB", (w, h), col), (0, 0), m)
        self.back = im.resize((W, H), Image.BICUBIC); return self.back

    # ---- cropping / composing
    def _origin(self, w):
        return w.winfo_rootx() - self.root.winfo_rootx(), w.winfo_rooty() - self.root.winfo_rooty()

    def crop(self, w, width=None, height=None):
        x, y = self._origin(w); W, H = width or w.winfo_width(), height or w.winfo_height(); B = self.backdrop()
        return B.crop((x, y, x + W, y + H)).convert("RGB")

    def compose(self, w, radius=0, kind=None, pad=(0, 0, 0, 0), width=None, height=None, core=None):
        """Picture for widget w: its backdrop, and (kind 'panel' | 'dark' | 'pill') a frosted rounded panel inset by pad = (left, top, right, bottom)."""
        W, H = width or w.winfo_width(), height or w.winfo_height()
        if W < 4 or H < 4: return None
        base = self.crop(w, W, H)
        if kind is None or radius <= 0 and kind is None: return base
        P = self.ctx.P; dark = self.ctx.dark
        l, t, r, b = pad; x1, y1, x2, y2 = l, t, W - r, H - b
        if x2 - x1 < 8 or y2 - y1 < 8: return base
        S = 2                                                              # supersample the mask for smooth corners
        def rmask(box, rad):
            m = Image.new("L", (W * S, H * S), 0); ImageDraw.Draw(m).rounded_rectangle([v * S for v in box], radius=rad * S, fill=255)
            return m.resize((W, H), Image.LANCZOS)
        rad = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        body = rmask((x1, y1, x2 - 1, y2 - 1), rad)
        out = base
        if min(l, t, r, b) >= 3 or max(l, t, r, b) >= 6:                  # shadow, only where there is room for it
            sh = Image.new("L", (W, H), 0); sh.paste(body, (0, 2)); sh = sh.filter(ImageFilter.GaussianBlur(5))
            sh = ImageChops.subtract(sh, body)                              # only the halo around the panel, never under it
            out = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), out, sh.point(lambda v: int(v * (.40 if dark else .16))))
        frost = base.filter(ImageFilter.GaussianBlur(10))
        if kind == "dark": tint, al = ((22, 25, 36), .88) if not dark else ((8, 9, 13), .70)
        else: tint, al = _rgb(P["card"]), .80                           # frosted band at the edge ...
        glass = Image.blend(frost, Image.new("RGB", (W, H), tint), al)
        if kind != "dark":                                              # ... and the card colour, exactly, where the contents sit (no seams, no sharp corners)
            c = core if core is not None else (6 if kind == "pill" else 12)
            if x2 - x1 > 2 * c + 4 and y2 - y1 > 2 * c + 4:
                inner = rmask((x1 + c, y1 + c, x2 - c - 1, y2 - c - 1), max(3, rad - c)).filter(ImageFilter.GaussianBlur(max(1, c * .35)))
                glass = Image.composite(Image.new("RGB", (W, H), tint), glass, inner)
        out = Image.composite(glass, out, body)
        # rim light: a thin bright edge, brighter on top
        rim = ImageChops.subtract(body, rmask((x1 + 1, y1 + 1, x2 - 2, y2 - 2), max(0, rad - 1)))
        grad = Image.linear_gradient("L").resize((W, H)); top = ImageChops.multiply(rim, grad.transpose(Image.FLIP_TOP_BOTTOM))
        edge = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), out, rim.point(lambda v: int(v * (.22 if dark else .5))))
        out = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), edge, top.point(lambda v: int(v * (.30 if dark else .55))))
        return out

    # ---- underlays: a picture behind a frame's children
    def attach(self, frame, radius=0, kind=None, pad=(0, 0, 0, 0)):
        """Paint the glass picture behind everything inside `frame` (a Label placed under its children)."""
        if frame in self.under:
            self.under[frame][1:5] = [radius, kind, pad, None]; self.schedule(frame); return
        lab = tk.Label(frame, bd=0, highlightthickness=0, bg=self.ctx.P["bg"]); lab.place(x=0, y=0, relwidth=1, relheight=1); tk.Misc.lower(lab)
        self.under[frame] = [lab, radius, kind, pad, None]
        frame.bind("<Configure>", lambda e, f=frame: self.schedule(f), add="+"); frame.bind("<Map>", lambda e, f=frame: self.schedule(f), add="+"); self.schedule(frame)

    def schedule(self, frame):
        if frame in self._job: return
        self._job[frame] = frame.after(30, lambda: self._paint(frame))

    def _paint(self, frame):
        self._job.pop(frame, None)
        try:
            if frame not in self.under or not frame.winfo_exists(): return
            lab, radius, kind, pad, last = self.under[frame]
            if not self.enabled() or not frame.winfo_ismapped(): lab.configure(image="", bg=self.ctx.P["bg"]); return
            key = (frame.winfo_rootx() - self.root.winfo_rootx(), frame.winfo_rooty() - self.root.winfo_rooty(), frame.winfo_width(), frame.winfo_height(), radius, kind, pad, self.ctx.dark, self.ctx.P["bg"], self.ctx.P["card"], self.gen)
            if key == last: return
            im = self.compose(frame, radius, kind, pad)
            if im is None: return
            ph = ImageTk.PhotoImage(im, master=self.root); lab.configure(image=ph); lab.image = ph; self.under[frame][4] = key
        except tk.TclError: pass

    def repaint(self):
        """Theme changed: redo every picture."""
        self.key = None; self.back = None; self.gen += 1
        for f in list(self.under):
            try:
                if f.winfo_exists(): self.under[f][4] = None; self.schedule(f)
                else: self.under.pop(f, None)
            except tk.TclError: self.under.pop(f, None)

    # ---- small things that sit straight on the backdrop (titles, hints): give them the backdrop's colour under them
    def blend(self, w):
        """Keep widget w's background equal to the backdrop behind it (it cannot be see-through, but the backdrop is smooth)."""
        if getattr(w, "_blend", False): return
        w._blend = True; w.bind("<Configure>", lambda e: self._tint(w), add="+"); self._tint(w)

    def _tint(self, w):
        try:
            if not self.enabled() or w.winfo_width() < 3: return
            c = self.crop(w).resize((1, 1), Image.BOX).getpixel((0, 0)); col = "#%02x%02x%02x" % c
            if str(w.cget("bg")) != col: w.configure(bg=col)
        except tk.TclError: pass
