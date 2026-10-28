"""Themed widgets, all drawn on canvases so they get rounded corners, hover animation and keyboard focus rings:
Btn, Card, Switch, Segmented, Swatches, ScrollFrame, Toast, plus the read-only Notice box."""
import tkinter as tk
from tkinter import ttk

from .shapes import mix, rrect
from .theme import ACCENTS, auto

TkBase = tk


def _parent_bg(w, default):
    try: return w.master.cget("bg")
    except Exception: return default


class Focusable(tk.Canvas):
    """Canvas widget with a focus ring and a theme repaint hook (base of the custom controls)."""
    def __init__(self, ctx, master, **kw):
        super().__init__(master, bd=0, highlightthickness=0, takefocus=kw.pop("takefocus", 1), **kw)
        self.ctx, self.focused = ctx, False
        self.bind("<FocusIn>", lambda e: self._focus(True)); self.bind("<FocusOut>", lambda e: self._focus(False))
        self.bind("<Configure>", lambda e: self.draw())
        ctx.themed.append(self.paint)

    def _focus(self, v): self.focused = v; self.draw()

    def paint(self): self.draw()

    def draw(self): pass

    def ring(self, x1, y1, x2, y2, r):
        if self.focused and self.ctx.kbd: rrect(self, x1 + 1, y1 + 1, x2 - 1, y2 - 1, r, outline=mix(self.ctx.P["accent"], self.ctx.P["card"], 0.35), fill="", width=2)


class Btn(Focusable):
    """Rounded button (primary / secondary / ghost) with animated hover, press state, focus ring and Enter/Space activation."""
    def __init__(self, ctx, master, text, command, kind="secondary", **kw):
        self.font = kw.pop("font", None) or ctx.f_bold; self.align = kw.pop("anchor", "center"); self.padx, self.pady = kw.pop("padx", 16), kw.pop("pady", 8)
        super().__init__(ctx, master, cursor="hand2", **kw)
        self.text, self.cmd, self.kind, self.on, self.hover, self.down = text, command, kind, True, False, False
        self.tip_text, self._tip_after, self._tip_win, self._cur, self._job = None, None, None, None, None
        self.bind("<Enter>", lambda e: self._h(True)); self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<ButtonPress-1>", self._press); self.bind("<ButtonRelease-1>", self._click)
        for k in ("<Return>", "<KP_Enter>", "<space>"): self.bind(k, self._key)
        self.paint()

    def configure(self, cnf=None, **kw):
        if "text" in kw: self.text = kw.pop("text"); self._size(); self.draw()
        if "font" in kw: self.font = kw.pop("font"); self._size()
        kw.pop("fg", None); kw.pop("bg", None)
        return super().configure(cnf, **kw) if (cnf or kw) else None
    config = configure

    def _h(self, v):
        self.hover = v; self._anim()
        if self._tip_after: self.after_cancel(self._tip_after); self._tip_after = None
        if self._tip_win: self._tip_win.destroy(); self._tip_win = None
        if v and self.tip_text: self._tip_after = self.after(450, self._show_tip)

    def tip(self, text): self.tip_text = text; return self

    def _show_tip(self):
        self._tip_after = None
        try:
            P = self.ctx.P; w = tk.Toplevel(self); w.wm_overrideredirect(True)
            tk.Label(w, text=self.tip_text, bg=P["text"], fg=P["card"], font=self.ctx.f_small, padx=8, pady=3).pack()
            w.wm_geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 4}"); self._tip_win = w
        except tk.TclError: pass

    def _press(self, e):
        if self._tip_win: self._tip_win.destroy(); self._tip_win = None
        if self.on: self.down = True; self.focus_set() if False else None; self._anim()

    def _click(self, e):
        was, self.down = self.down, False; self._anim()
        if self.on and was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height() and self.cmd: self.cmd()

    def _key(self, e):
        if self.on and self.cmd: self.cmd()
        return "break"

    def set_enabled(self, v):
        self.on = v; self.configure(cursor="hand2" if v else "arrow", takefocus=1 if v else 0); self.paint()

    # ---- drawing
    def _target(self):
        P = self.ctx.P; k = self.kind; pbg = _parent_bg(self, P["card"])
        if not self.on: return (P["soft"] if k != "ghost" else pbg), P["muted"]
        if k == "primary": return (mix(P["accent_h"], "#000000", 0.12) if self.down else P["accent_h"] if self.hover else P["accent"]), P["accent_fg"]
        if k == "tonal": return (mix(P["sel"], P["text"], 0.06) if self.hover else P["sel"]), P["text"]
        if k == "ghost": return (P["soft_h"] if self.down else P["soft"] if self.hover else pbg), P["text"]
        return (mix(P["soft_h"], P["text"], 0.1) if self.down else P["soft_h"] if self.hover else P["soft"]), P["text"]

    def _size(self):
        c = self.ctx
        self.configure(width=self.font.measure(self.text) + 2 * c.dp(self.padx), height=self.font.metrics("linespace") + 2 * c.dp(self.pady))

    def _anim(self):
        if self._job: self.after_cancel(self._job); self._job = None
        tgt = self._target()[0]
        if not self.ctx.motion or self._cur is None: self._cur = tgt; self.draw(); return
        start, n = self._cur, 4
        def step(i=1):
            try:
                self._cur = mix(start, tgt, i / n); self.draw()
                self._job = self.after(16, lambda: step(i + 1)) if i < n else None
            except tk.TclError: pass
        step()

    def paint(self):
        self._size(); self._cur = self._target()[0]; self.draw()

    def draw(self):
        try:
            self.delete("all"); P = self.ctx.P; w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
            tk.Canvas.configure(self, bg=_parent_bg(self, P["card"]))
            fill, fg = self._target()
            if self._job and self._cur: fill = self._cur
            r = min(self.ctx.r_btn, h / 2)
            rrect(self, 0, 0, w, h, r, fill=fill, outline=fill)
            if self.align == "w": self.create_text(self.ctx.dp(self.padx), h / 2, text=self.text, fill=fg, font=self.font, anchor="w")
            else: self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)
            self.ring(0, 0, w, h, r)
        except tk.TclError: pass


class Switch(Focusable):
    """On/off toggle. Click or Space/Enter flips it; `var` is a BooleanVar."""
    W, H = 42, 24

    def __init__(self, ctx, master, var, command=None):
        super().__init__(ctx, master, width=self.W + 4, height=self.H + 4, cursor="hand2")
        self.var, self.cmd, self._x = var, command, 1.0 if var.get() else 0.0
        self.bind("<Button-1>", lambda e: self.flip()); 
        for k in ("<space>", "<Return>"): self.bind(k, lambda e: (self.flip(), "break")[1])
        var.trace_add("write", lambda *a: self._sync())
        self.draw()

    def flip(self):
        self.var.set(not self.var.get()); self.cmd and self.cmd()

    def _sync(self):
        tgt = 1.0 if self.var.get() else 0.0
        def step():
            try:
                d = tgt - self._x
                if not self.ctx.motion or abs(d) < 0.05: self._x = tgt; self.draw(); return
                self._x += d * 0.5; self.draw(); self.after(16, step)
            except tk.TclError: pass
        step()

    def draw(self):
        try:
            self.delete("all"); P = self.ctx.P; self.configure(bg=_parent_bg(self, P["card"]))
            x0, y0, w, h = 2, 2, self.W, self.H
            rrect(self, x0, y0, x0 + w, y0 + h, h / 2, fill=mix(P["off"], P["card"], 0.35) if self._x < 0.5 else P["accent"], outline="")
            if self._x > 0 and self._x < 1: pass
            kx = x0 + h / 2 + (w - h) * self._x
            self.create_oval(kx - h / 2 + 3, y0 + 3, kx + h / 2 - 3, y0 + h - 3, fill="#ffffff", outline="")
            self.ring(0, 0, w + 4, h + 4, (h + 4) / 2)
        except tk.TclError: pass


class Segmented(Focusable):
    """Segmented control: pick one of a few labelled options. Left/Right arrows move the choice."""
    def __init__(self, ctx, master, options, value, command=None):
        super().__init__(ctx, master, cursor="hand2")
        self.opts, self.value, self.cmd, self.hot = list(options), value, command, None
        self.bind("<Button-1>", self._click); self.bind("<Motion>", self._move); self.bind("<Leave>", lambda e: self._hot(None))
        self.bind("<Left>", lambda e: self.step(-1)); self.bind("<Right>", lambda e: self.step(1))
        self.paint()

    def _widths(self): return [self.ctx.f_body.measure(l) + self.ctx.dp(26) for l, _ in self.opts]

    def paint(self):
        self.configure(width=sum(self._widths()) + 8, height=self.ctx.f_body.metrics("linespace") + self.ctx.dp(16) + 8); self.draw()

    def _at(self, x):
        x0 = 4
        for i, w in enumerate(self._widths()):
            if x0 <= x < x0 + w: return i
            x0 += w

    def _hot(self, i):
        if i != self.hot: self.hot = i; self.draw()

    def _move(self, e): self._hot(self._at(e.x))

    def _click(self, e):
        i = self._at(e.x); self.focus_set()
        if i is not None: self.pick(self.opts[i][1])

    def step(self, d):
        vals = [v for _, v in self.opts]; i = (vals.index(self.value) + d) % len(vals) if self.value in vals else 0; self.pick(vals[i]); return "break"

    def pick(self, v):
        changed = v != self.value; self.value = v; self.draw()
        if changed and self.cmd: self.cmd(v)

    def set(self, v): self.value = v; self.draw()

    def draw(self):
        try:
            self.delete("all"); P = self.ctx.P; W, H = int(self["width"]), int(self["height"]); self.configure(bg=_parent_bg(self, P["card"]))
            rr = min(self.ctx.r_btn + 3, H / 2)
            rrect(self, 0, 0, W, H, rr, fill=P["soft"], outline="")
            x = 4
            for i, ((label, val), w) in enumerate(zip(self.opts, self._widths())):
                on = val == self.value
                if on:
                    chip = P["card"] if not self.ctx.dark else P["soft_h"]
                    rrect(self, x, 5, x + w, H - 3, max(1, rr - 3), fill=P["shadow"], outline="")
                    rrect(self, x, 4, x + w, H - 4, max(1, rr - 3), fill=chip, outline="")
                elif i == self.hot: rrect(self, x, 4, x + w, H - 4, max(1, rr - 3), fill=P["soft_h"], outline="")
                self.create_text(x + w / 2, H / 2, text=label, font=self.ctx.f_bold if on else self.ctx.f_body, fill=P["text"] if on else P["muted"])
                x += w
            self.ring(0, 0, W, H, rr)
        except tk.TclError: pass


class Swatches(Focusable):
    """Accent colour picker: round swatches (+ a custom colour). Left/Right arrows move, Enter picks."""
    def __init__(self, ctx, master, value, command, custom=None):
        super().__init__(ctx, master, cursor="hand2", width=10, height=10)
        self.names = list(ACCENTS) + ["Custom"]; self.value, self.cmd, self.custom, self.idx = value, command, custom, 0
        self.bind("<Button-1>", self._click)
        self.bind("<Left>", lambda e: self.move(-1)); self.bind("<Right>", lambda e: self.move(1))
        for k in ("<Return>", "<space>"): self.bind(k, lambda e: (self.pick(self.names[self.idx]), "break")[1])
        self.paint()

    SZ, GAP = 26, 10

    def paint(self): self.configure(width=len(self.names) * (self.SZ + self.GAP) + 4, height=self.SZ + 12); self.draw()

    def sel(self): return self.value if self.value in ACCENTS else "Custom"

    def move(self, d):
        self.idx = (self.idx + d) % len(self.names); self.draw(); return "break"

    def _click(self, e):
        self.focus_set(); i = int((e.x - 2) // (self.SZ + self.GAP))
        if 0 <= i < len(self.names): self.idx = i; self.pick(self.names[i])

    def pick(self, name):
        if name == "Custom":
            c = self.custom() if self.custom else None
            if not c: return
            name = c
        self.value = name; self.cmd(name); self.draw()

    def draw(self):
        try:
            self.delete("all"); P = self.ctx.P; self.configure(bg=_parent_bg(self, P["card"])); s = self.sel()
            if not self.focused: self.idx = self.names.index(s)
            for i, n in enumerate(self.names):
                x = 2 + i * (self.SZ + self.GAP); y = 6
                col = (ACCENTS[n][1] if self.ctx.dark else ACCENTS[n][0]) if n in ACCENTS else (self.value if self.value not in ACCENTS else P["soft_h"])
                self.create_oval(x, y, x + self.SZ, y + self.SZ, fill=col, outline=P["border"] if n != s else "")
                if n == "Custom" and self.value in ACCENTS: self.create_text(x + self.SZ / 2, y + self.SZ / 2, text="+", font=self.ctx.f_bold, fill=P["muted"])
                if n == s:
                    self.create_oval(x - 4, y - 4, x + self.SZ + 4, y + self.SZ + 4, outline=P["muted"], width=1)
                    self.create_text(x + self.SZ / 2, y + self.SZ / 2, text="✓", font=self.ctx.f_bold, fill=P["accent_fg"] if n != "Custom" or self.value not in ACCENTS else "#fff")
                if self.focused and self.ctx.kbd and i == self.idx: self.create_oval(x - 7, y - 7, x + self.SZ + 7, y + self.SZ + 7, outline=P["accent"], width=2)
        except tk.TclError: pass


class ScrollFrame(TkBase.Frame):
    """Vertically scrolling area (mouse wheel, scrollbar, and it scrolls to whatever control gets keyboard focus)."""
    def __init__(self, ctx, master, bg_key="card"):
        super().__init__(master, bd=0); self.ctx, self.key = ctx, bg_key
        self.cv = tk.Canvas(self, bd=0, highlightthickness=0, takefocus=0)
        self.sb = ttk.Scrollbar(self, command=self.cv.yview, style="Thin.Vertical.TScrollbar"); self.cv.configure(yscrollcommand=auto(self.sb, self.cv))
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bd=0); self.win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self.win, width=e.width))
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        for w in (self.cv, self.inner): w.bind("<Enter>", lambda e: self._wheel(True)); w.bind("<Leave>", lambda e: self._wheel(False))
        ctx.themed.append(self.paint); self.paint()

    def paint(self):
        c = self.ctx.P[self.key]; self.configure(bg=c); self.cv.configure(bg=c); self.inner.configure(bg=c)

    def _wheel(self, on):
        if on:
            self.bind_all("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units")); self.bind_all("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))
            self.bind_all("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        else:
            for k in ("<Button-4>", "<Button-5>", "<MouseWheel>"): self.unbind_all(k)

    def see(self, w):
        try:
            self.update_idletasks(); top = w.winfo_rooty() - self.inner.winfo_rooty(); h = w.winfo_height()
            total = max(1, self.inner.winfo_height()); view = self.cv.winfo_height(); y0 = self.cv.yview()[0] * total
            if top < y0: self.cv.yview_moveto(max(0, (top - 20) / total))
            elif top + h > y0 + view: self.cv.yview_moveto(min(1, (top + h - view + 20) / total))
        except tk.TclError: pass

    def watch_focus(self, root=None):
        for ch in (root or self.inner).winfo_children():
            ch.bind("<FocusIn>", lambda e, w=ch: self.see(w), add="+"); self.watch_focus(ch)


class Notice(TkBase.Frame):
    """Read-only, scrollable message box (so long errors can be read in full)."""
    def __init__(self, ctx, master, height=3):
        super().__init__(master, bd=0); self.ctx, self.kind, self.msg = ctx, "none", ""
        self.t = tk.Text(self, height=height, wrap="word", bd=0, highlightthickness=0, padx=10, pady=7, relief="flat", cursor="arrow", font=ctx.f_small)
        self.sb = ttk.Scrollbar(self, command=self.t.yview, style="Thin.Vertical.TScrollbar"); self.t.configure(yscrollcommand=auto(self.sb, self.t))
        self.t.pack(side="left", fill="both", expand=True)
        self.t.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in "ca") or e.keysym in ("Up", "Down", "Prior", "Next", "Home", "End") else "break")
        ctx.themed.append(self.paint); self.paint()

    def set(self, text, kind="none"):
        self.msg, self.kind = text, kind; self.paint()
        self.t.configure(state="normal"); self.t.delete("1.0", "end"); self.t.insert("1.0", text); self.t.configure(state="normal"); self.t.yview_moveto(0)

    def paint(self):
        P = self.ctx.P
        amber = "#fbbf24" if self.ctx.dark else "#b45309"
        bg, fg = {"ok": (P["okbg"], P["ok"]), "bad": (P["badbg"], P["bad"]), "info": (P["infobg"], P["text"]), "warn": (mix(P["card"], amber, .16), amber)}.get(self.kind, (P["field"], P["muted"]))
        self.configure(bg=bg); self.t.configure(bg=bg, fg=fg, selectbackground=P["sel"], selectforeground=P["text"], inactiveselectbackground=P["sel"])


class Card(TkBase.Canvas):
    """Soft floating panel: rounded, no outline, a faint shadow; header with title, hint, tool and pane-button areas, and a body."""
    SH = 5      # room for the shadow on the right and bottom

    def __init__(self, ctx, master, num, title, hint="", flat=False):
        super().__init__(master, bd=0, highlightthickness=0, width=2, height=2); self.ctx = ctx
        self.flat = flat; self.SH = 0 if flat else Card.SH          # flat: square, no shadow, so panes can sit 1 px apart like VS Code's
        self.inner = tk.Frame(self, bd=0); self.win = self.create_window(0, 0, window=self.inner, anchor="nw")
        self.head = head = tk.Frame(self.inner, bd=0); head.pack(fill="x")
        self.badge = tk.Label(head, text=str(num), font=ctx.f_small, padx=7, pady=1) if num else None
        if self.badge: self.badge.pack(side="left", padx=(0, 8))
        self.title = tk.Label(head, text=title, font=ctx.f_title); self.title.pack(side="left")
        self.hint = tk.Label(head, text=hint, font=ctx.f_small); self.hint.pack(side="left", padx=(12, 0))
        self.tools = tk.Frame(head, bd=0); self.tools.pack(side="right")
        self.chrome = tk.Frame(head, bd=0); self.chrome.pack(side="right", before=self.tools, padx=(8, 0))   # pane buttons (swap / hide)
        self.body = tk.Frame(self.inner, bd=0); self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(0, weight=1)
        self.bind("<Configure>", lambda e: self.draw()); self.inner.bind("<Configure>", lambda e: self._req())
        ctx.themed.append(self.paint); self.paint()

    def inset(self): return 8 if self.flat else max(3, round(self.ctx.r_card * 0.32) + 2)

    def _req(self):
        i = self.inset(); w, h = self.inner.winfo_reqwidth() + 2 * i + self.SH, self.inner.winfo_reqheight() + 2 * i + self.SH
        if (int(self["width"]), int(self["height"])) != (w, h): self.configure(width=w, height=h)

    def draw(self):
        try:
            self.delete("shape"); P = self.ctx.P; sh = self.SH; w, h = self.winfo_width() - sh, self.winfo_height() - sh; i = self.inset()
            self.configure(bg=_parent_bg(self, P["bg"])); r = self.ctx.r_card
            if self.flat: self.create_rectangle(0, 0, w, h, fill=P["card"], outline="", tags="shape")
            else:
                for k, (dx, dy, t) in enumerate(((0, 4, 0.35), (0, 3, 0.55), (0, 2, 0.8))):
                    rrect(self, 1 + dx, 1 + dy, w - 1 + dx, h - 1 + dy, r, fill=mix(_parent_bg(self, P["bg"]), P["shadow"], t), outline="", tags="shape")
                rrect(self, 1, 1, w - 1, h - 1, r, fill=P["card"], outline="", tags="shape")
            self.tag_lower("shape")
            self.coords(self.win, i, i); self.itemconfigure(self.win, width=max(1, w - 2 * i), height=max(1, h - 2 * i))
        except tk.TclError: pass

    def paint(self):
        P, c = self.ctx.P, self.ctx
        for w in (self.inner, self.head, self.body, self.tools, self.chrome): w.configure(bg=P["card"])
        if self.badge: self.badge.configure(bg=P["soft"], fg=P["muted"])
        self.title.configure(bg=P["card"], fg=P["text"]); self.hint.configure(bg=P["card"], fg=P["muted"])
        self.head.pack_configure(padx=c.dp(18), pady=(c.dp(16), c.dp(8))); self.body.pack_configure(padx=c.dp(18), pady=(0, c.dp(18)))
        self._req(); self.draw()


class Toast:
    """Short message shown in the status area at the bottom of the window; disappears by itself (or on click)."""
    def __init__(self, ctx): self.ctx, self.w, self.job = ctx, None, None; ctx.themed.append(self.hide)

    def show(self, text, kind="info"):
        ctx = self.ctx; P = ctx.P; root = ctx.root
        self.hide()
        bg = {"bad": P["bad"], "ok": P["ok"]}.get(kind, P["text"]); fg = P["card"] if kind == "info" else "#ffffff"
        f = ctx.f_small; H = max(30, f.metrics("linespace") + 14); w = f.measure(text) + 36
        base = P["card"] if ctx.cfg.get("show_status", True) else P["bg"]
        cv = tk.Canvas(root, width=w, height=H, bd=0, highlightthickness=0, bg=base); self.w = cv
        rrect(cv, 1, 3, w - 1, H - 3, (H - 6) / 2, fill=bg, outline=bg); cv.create_text(w / 2, H / 2, text=text, fill=fg, font=f)
        cv.bind("<Button-1>", lambda e: self.hide()); cv.configure(cursor="hand2")
        cv.place(relx=0.5, rely=1.0, anchor="s"); tk.Misc.lift(cv)
        self.job = root.after(max(2200, 60 * len(text)), self.hide)

    def hide(self):
        if self.job:
            try: self.ctx.root.after_cancel(self.job)
            except Exception: pass
            self.job = None
        try:
            if self.w is not None: self.w.destroy()
        except tk.TclError: pass
        self.w = None
