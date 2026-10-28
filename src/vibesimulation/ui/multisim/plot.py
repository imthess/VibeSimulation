"""A small line-plot canvas used by the sweep, Bode and transient panes (linear or logarithmic x axis, gaps where a point has no value)."""
import math
import tkinter as tk

from ...analog.units import fmt_si

COLORS = ("#2f6bff", "#e5484d", "#16a34a", "#d97706", "#8b5cf6", "#0891b2", "#be185d", "#64748b")


def nice_ticks(lo, hi, n=5):
    if hi - lo < 1e-30: lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / n; mag = 10 ** math.floor(math.log10(raw)); step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag)
    t = math.ceil(lo / step - 1e-9) * step; out = []
    while t <= hi + step * 1e-9: out.append(round(t / step) * step); t += step
    return out


def decade_ticks(lo, hi):
    a, b = math.floor(math.log10(lo)), math.ceil(math.log10(hi)); return [10.0 ** e for e in range(a, b + 1) if lo * 0.999 <= 10.0 ** e <= hi * 1.001] or [lo, hi]


class Plot(tk.Canvas):
    def __init__(self, master, ctx, **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw); self.ctx = ctx
        self.args = None; self.msg = ""; self.bind("<Configure>", lambda e: self.redraw())

    def show(self, xs, series, xunit="", yunit="", xlog=False, title="", legend=True, message=""):
        """series = [(label, [y or None ...])]."""
        self.args = (xs, series, xunit, yunit, xlog, title, legend); self.msg = message; self.redraw()

    def clear(self, message=""):
        self.args = None; self.msg = message; self.redraw()

    def redraw(self):
        c, P = self, self.ctx.P; c.delete("all"); c.configure(bg=P["canvas"]); W, H = c.winfo_width(), c.winfo_height(); f = self.ctx.f_small
        if W < 80 or H < 40: return
        if not self.args or not self.args[1]:
            if self.msg: c.create_text(W / 2, H / 2, text=self.msg, fill=P["muted"], font=f, justify="center", width=W - 20)
            return
        xs, S, xu, yu, xlog, title, legend = self.args; S = [(t, ys) for t, ys in S if ys]
        vals = [y for _, ys in S for y in ys if y is not None]
        if not vals: c.create_text(W / 2, H / 2, text="Nothing to plot: no point has a value.", fill=P["muted"], font=f); return
        y0, y1 = min(vals), max(vals)
        if y1 - y0 < 1e-12 * max(1.0, abs(y1)): y0, y1 = y0 - 1, y1 + 1 if abs(y0) < 1e-12 else y1 + abs(y1) * 0.1
        ty = nice_ticks(y0, y1); y0, y1 = min(y0, ty[0]), max(y1, ty[-1])
        tx = decade_ticks(xs[0], xs[-1]) if xlog else nice_ticks(xs[0], xs[-1])
        rows = (len(S) + 2) // 3 if legend else 0
        L, R, T, B = 66, 26, 8 + (14 if title else 0), 22 + 16 * rows; pw, ph = W - L - R, H - T - B
        if pw < 30 or ph < 20: c.create_text(W / 2, H / 2, text="Make this pane taller to see the plot.", fill=P["muted"], font=f); return
        xa, xb = (math.log10(xs[0]), math.log10(xs[-1])) if xlog else (xs[0], xs[-1])
        X = lambda x: L + ((math.log10(x) if xlog else x) - xa) / ((xb - xa) or 1) * pw; Y = lambda y: T + ph - (y - y0) / ((y1 - y0) or 1) * ph
        if title: c.create_text(L, 2, text=title, anchor="nw", fill=P["muted"], font=f)
        for t in ty: c.create_line(L, Y(t), W - R, Y(t), fill=P["border"]); c.create_text(L - 6, Y(t), text=fmt_si(t, yu, 3), anchor="e", fill=P["muted"], font=f)
        for t in tx:
            if xlog and not (xs[0] * 0.999 <= t <= xs[-1] * 1.001): continue
            c.create_line(X(t), T, X(t), T + ph, fill=P["border"]); c.create_text(X(t), T + ph + 3, text=fmt_si(t, xu, 3), anchor="n", fill=P["muted"], font=f)
        c.create_rectangle(L, T, W - R, T + ph, outline=P["muted"])
        for j, (t, ys) in enumerate(S):
            col, seg = COLORS[j % len(COLORS)], []
            for x, y in zip(xs, ys):
                if y is None:
                    if len(seg) > 3: c.create_line(*seg, fill=col, width=2)
                    seg = []
                else: seg += [X(x), Y(y)]
            if len(seg) > 3: c.create_line(*seg, fill=col, width=2)
            elif len(seg) == 2: c.create_oval(seg[0] - 2, seg[1] - 2, seg[0] + 2, seg[1] + 2, fill=col, outline=col)
            if legend:
                lx, ly = L + (j % 3) * (pw // 3), T + ph + 28 + 14 * (j // 3)
                c.create_line(lx, ly, lx + 16, ly, fill=col, width=3); c.create_text(lx + 20, ly, text=t, anchor="w", fill=P["text"], font=f)
