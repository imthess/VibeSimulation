"""Look of the Import & AI page: soft rounded cards, black pill buttons and an orange accent (light and dark)."""
import math
import tkinter as tk

from ....ui.theme import mix

LIGHT = dict(bg="#eeeeef", card="#fbfbfc", edge="#e3e3e6", ink="#0c0c0d", muted="#8b8b94", accent="#f28c28", accent_soft="#fdecd8", field="#f1f1f3", shadow="#d9d9dd")
DARK = dict(bg="#121214", card="#1d1d20", edge="#2b2b30", ink="#f3f3f4", muted="#9b9ba5", accent="#f59a3c", accent_soft="#3a2a17", field="#18181b", shadow="#0a0a0b")


def tokens(ctx):
    """The page follows the app's glass palette (the old orange look is only kept as a fallback)."""
    P = ctx.P
    return dict(bg=P["bg"], card=P["card"], edge=P["border"], ink=P["text"], muted=P["muted"], accent=P["accent"], accent_soft=P["sel"], field=P["field"], shadow=P["shadow"])


def rounded(c, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle on a canvas: a polygon with a true circular arc at each corner."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(0, 10):
            ang = math.radians(a0 + 9 * k); pts += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
    return c.create_polygon(pts, **kw)


class SoftCard(tk.Canvas):
    """A rounded panel with a faint shadow. Put widgets in ``.body``."""
    def __init__(self, ctx, master, radius=28, pad=20):
        super().__init__(master, bd=0, highlightthickness=0)
        self.ctx, self.radius, self.pad = ctx, radius, pad
        self.body = tk.Frame(self, bd=0)
        self._win = self.create_window(pad, pad, window=self.body, anchor="nw")
        self.bind("<Configure>", self._layout); self.bind("<Map>", lambda e: self.after(40, self.paint))
        ctx.themed.append(self.paint); self.paint()

    def _layout(self, e=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.itemconfigure(self._win, width=max(10, w - 2 * self.pad - 4), height=max(10, h - 2 * self.pad - 6))
        self.paint()

    def paint(self):
        T = tokens(self.ctx); w, h = self.winfo_width(), self.winfo_height()
        self.configure(bg=T["bg"]); self.body.configure(bg=T["card"]); self.delete("bg")
        if w < 20 or h < 20: return
        g = self.ctx.glass
        if g.enabled() and self.winfo_ismapped():
            key = (g._origin(self), w, h, self.radius, self.ctx.dark, T["card"], g.gen)
            if key != getattr(self, "_gkey", None):
                im = g.compose(self, self.radius, "panel", pad=(2, 1, 2, 5))
                if im is not None:
                    from PIL import ImageTk
                    self._gimg = ImageTk.PhotoImage(im, master=self); self._gkey = key
            if getattr(self, "_gimg", None) is not None:
                self.create_image(0, 0, image=self._gimg, anchor="nw", tags="bg"); self.tag_lower("bg"); return
        for i, (dy, col) in enumerate(((5, mix(T["bg"], T["shadow"], .35)), (3, mix(T["bg"], T["shadow"], .6)))):
            rounded(self, 3 + i, 2 + dy, w - 3 - i, h - 2, self.radius, fill=col, outline="", tags="bg")
        rounded(self, 2, 1, w - 2, h - 5, self.radius, fill=T["card"], outline=T["edge"], width=1, tags="bg")
        self.tag_lower("bg")


class Pill(tk.Canvas):
    """Pill or round button. kind: ink (black), soft (white), accent (orange). Same small API as ui.widgets.Btn: cmd, on, set_enabled, tip, config(text=)."""
    def __init__(self, ctx, master, text, command, kind="soft", height=46, shape="pill", font=None, icon="", **kw):
        super().__init__(master, height=height, bd=0, highlightthickness=0, cursor="hand2", **kw)
        self.ctx, self.text, self.cmd, self.kind, self.shape, self.icon = ctx, text, command, kind, shape, icon
        self.h, self.on, self.hover, self.down, self.font = height, True, False, False, font or ctx.f_bold
        self.tip_text = None; self._tipw = None; self._tipj = None
        if shape == "circle": self.configure(width=height)
        self.bind("<Configure>", lambda e: self.draw()); self.bind("<Enter>", lambda e: self._h(True)); self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<ButtonPress-1>", self._press); self.bind("<ButtonRelease-1>", self._release)
        ctx.themed.append(self.draw)

    def tip(self, text):
        self.tip_text = text; return self

    def set_enabled(self, on):
        self.on = bool(on); self.configure(cursor="hand2" if self.on else "arrow"); self.draw()

    def configure(self, cnf=None, **kw):
        if "text" in kw: self.text = kw.pop("text"); self.draw()
        kw.pop("fg", None); kw.pop("bg", None)
        return super().configure(cnf, **kw) if (cnf or kw) else None
    config = configure

    def _h(self, v):
        self.hover = v; self.draw()
        if self._tipj: self.after_cancel(self._tipj); self._tipj = None
        if self._tipw: self._tipw.destroy(); self._tipw = None
        if v and self.tip_text: self._tipj = self.after(450, self._show_tip)

    def _show_tip(self):
        self._tipj = None
        try:
            T = tokens(self.ctx); w = tk.Toplevel(self); w.wm_overrideredirect(True)
            tk.Label(w, text=self.tip_text, bg=T["ink"], fg=T["card"], font=self.ctx.f_small, padx=8, pady=3).pack()
            w.wm_geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 4}"); self._tipw = w
        except tk.TclError: pass

    def _press(self, e):
        if self._tipw: self._tipw.destroy(); self._tipw = None
        if self.on: self.down = True; self.draw()

    def _release(self, e):
        was, self.down = self.down, False; self.draw()
        if self.on and was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height() and self.cmd: self.cmd()

    def colors(self):
        T = tokens(self.ctx)
        if not self.on: return mix(T["card"], T["muted"], .12), T["edge"], mix(T["card"], T["muted"], .6)
        if self.kind == "ink": return (mix(T["ink"], T["card"], .18) if self.hover else T["ink"]), T["ink"], T["card"]
        if self.kind == "accent": return (mix(T["accent"], "#ffffff", .12) if self.hover else T["accent"]), T["accent"], "#ffffff"
        return (mix(T["card"], T["ink"], .06) if self.hover else T["card"]), T["edge"], T["ink"]

    def draw(self):
        if not self.winfo_exists(): return
        self.delete("all"); w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8: return
        T = tokens(self.ctx); fill, line, fg = self.colors()
        super().configure(bg=self._bg())
        dy = 1 if self.down else 0
        rounded(self, 1, 1 + dy, w - 1, h - 1 + dy, h / 2, fill=fill, outline=line, width=1)
        label = (self.icon + "  " if self.icon else "") + self.text
        self.create_text(w / 2, h / 2 + dy, text=label, fill=fg, font=self.font)

    def _bg(self):
        return tokens(self.ctx)["card"]
