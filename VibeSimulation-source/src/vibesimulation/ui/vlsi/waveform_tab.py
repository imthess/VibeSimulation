"""Bottom panel, tab 3: the signals of a run drawn against time (1-bit signals as lines, buses as hex boxes). Wheel = zoom, drag = pan."""
import tkinter as tk
from tkinter import ttk


def value_at(changes, t):
    """The value a signal has at time t. `changes` is [(time, value)] sorted by time."""
    v = None
    for ct, cv in changes:
        if ct > t: break
        v = cv
    return v


class WaveformTab(tk.Frame):
    ROW, LEFT, TOP = 26, 130, 24

    def __init__(self, ctx, master):
        super().__init__(master, bd=0); self.ctx = ctx
        self.res = None; self.x0 = 0.0; self.scale = 1.0; self.names = []; self._drag = None; self.cursor = None
        self.c = tk.Canvas(self, bd=0, highlightthickness=0, height=120); self.c.pack(fill="both", expand=True)
        for ev in ("<Configure>",): self.c.bind(ev, lambda e: self.draw())
        self.c.bind("<MouseWheel>", lambda e: self.zoom(e.x, 1.2 if e.delta > 0 else 1 / 1.2))
        self.c.bind("<Button-4>", lambda e: self.zoom(e.x, 1.2)); self.c.bind("<Button-5>", lambda e: self.zoom(e.x, 1 / 1.2))
        self.c.bind("<ButtonPress-1>", self._down); self.c.bind("<B1-Motion>", self._move); self.c.bind("<Motion>", self._hover)
        self.c.bind("<Double-1>", lambda e: self.fit())
        ctx.themed.append(self.draw)

    # ---- data
    def show(self, res):
        self.res = res; self.names = [n for n in res.order if n in res.waves]
        self.fit()

    def fit(self):
        end = max(1, self.res.end_time if self.res else 1); w = max(100, self.c.winfo_width() - self.LEFT - 12)
        self.scale = w / end; self.x0 = 0.0; self.draw()

    def zoom(self, x, f):
        t = self.x0 + (x - self.LEFT) / self.scale; self.scale = min(max(self.scale * f, 1e-4), 400)
        self.x0 = max(0.0, t - (x - self.LEFT) / self.scale); self.draw()

    def _down(self, e): self._drag = (e.x, self.x0)

    def _move(self, e):
        if self._drag: self.x0 = max(0.0, self._drag[1] - (e.x - self._drag[0]) / self.scale); self.draw()

    def _hover(self, e):
        self.cursor = self.x0 + (e.x - self.LEFT) / self.scale if e.x >= self.LEFT else None; self.draw()

    # ---- drawing
    def tx(self, t): return self.LEFT + (t - self.x0) * self.scale

    def draw(self):
        c, P = self.c, self.ctx.P; c.delete("all"); c.configure(bg=P["field"])
        r = self.res
        if not r or not self.names:
            c.create_text(14, 14, anchor="nw", fill=P["muted"], font=self.ctx.f_body, text="Run the design (▶ Run) to see its waveforms here." if not r else "The run changed no signals.")
            return
        W, H = c.winfo_width(), c.winfo_height(); f = self.ctx.f_small
        step = self._tick_step()
        t = (int(self.x0 // step)) * step
        while self.tx(t) < W:
            x = self.tx(t)
            if x >= self.LEFT:
                c.create_line(x, self.TOP, x, H, fill=P["border"]); c.create_text(x + 3, 4, anchor="nw", text=str(t), fill=P["muted"], font=f)
            t += step
        for i, n in enumerate(self.names):
            y0 = self.TOP + i * self.ROW + 3; y1 = y0 + self.ROW - 8
            kind = r.kinds.get(n, "variable"); col = P["accent"] if kind == "input" else (P["ok"] if kind == "output" else P["text"])
            c.create_text(8, (y0 + y1) / 2, anchor="w", text=f"{n}" + (f"[{r.widths[n] - 1}:0]" if r.widths.get(n, 1) > 1 else ""), fill=col, font=f)
            self._signal(n, r.waves[n], r.widths.get(n, 1), y0, y1, col, W)
        c.create_line(self.LEFT, 0, self.LEFT, H, fill=P["border"])
        if self.cursor is not None and self.cursor >= 0:
            x = self.tx(self.cursor); c.create_line(x, self.TOP, x, H, fill=P["muted"], dash=(2, 3))
            tip = [f"t = {int(self.cursor)}"] + [f"{n} = {self._fmt(value_at(r.waves[n], self.cursor), r.widths.get(n, 1))}" for n in self.names]
            tx = min(x + 8, W - 130); it = c.create_text(tx, self.TOP + 4, anchor="nw", text="\n".join(tip[:9]), fill=P["text"], font=f)
            bb = c.bbox(it); r_ = c.create_rectangle(bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2, fill=P["card"], outline=P["border"]); c.tag_raise(it, r_)

    def _tick_step(self):
        want = 70 / self.scale
        for base in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 1000000):
            if base >= want: return base
        return 1000000

    @staticmethod
    def _fmt(v, w):
        if v is None: return "?"
        return str(v) if w == 1 else f"{v:0{(w + 3) // 4}X}h"

    def _signal(self, n, ch, w, y0, y1, col, W):
        c, P = self.c, self.ctx.P; end = self.res.end_time
        pts = list(ch) + [(end, ch[-1][1])] if ch else []
        for k in range(len(pts) - 1):
            ta, va = pts[k]; tb = pts[k + 1][0]
            xa, xb = max(self.LEFT, self.tx(ta)), min(W, self.tx(tb))
            if xb <= self.LEFT or xa >= W or xb < xa: continue
            if w == 1:
                y = y0 if va else y1; c.create_line(xa, y, xb, y, fill=col, width=2)
                if k + 1 < len(pts) - 1 and pts[k + 1][1] != va and self.LEFT <= self.tx(tb) <= W: c.create_line(self.tx(tb), y0, self.tx(tb), y1, fill=col, width=2)
            else:
                c.create_polygon(xa + 3, y0, xb - 3, y0, xb, (y0 + y1) / 2, xb - 3, y1, xa + 3, y1, xa, (y0 + y1) / 2, outline=col, fill="")
                if xb - xa > 24: c.create_text((xa + xb) / 2, (y0 + y1) / 2, text=self._fmt(va, w), fill=P["text"], font=self.ctx.f_small)
