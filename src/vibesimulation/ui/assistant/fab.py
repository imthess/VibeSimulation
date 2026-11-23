"""The round glass button at the bottom right (a star; a cross while the bar is open)."""
import tkinter as tk
from tkinter import font as tkfont

from vibesimulation.ui.assistant.backdrop import STAR, Image, ImageTk, glass_disc
GLYPH, CLOSE = "✦", "✕"          # the same star as the "Import & AI" icon on the rail


class Fab(tk.Canvas):
    def __init__(self, ctx, master, ui):
        super().__init__(master, bd=0, highlightthickness=0, cursor="hand2", takefocus=1)
        self.ctx, self.ui = ctx, ui; self.hot = False; self.spin = 0; self._img = None; self._key = None; self._tip = self._tipj = None
        self.font = tkfont.Font(root=ctx.root, weight="bold")
        self.bind("<Enter>", lambda e: self._hover(True)); self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<ButtonRelease-1>", self._release); self.bind("<Return>", lambda e: ui.toggle()); self.bind("<space>", lambda e: ui.toggle())
        self.bind("<FocusIn>", lambda e: self.draw()); self.bind("<FocusOut>", lambda e: self.draw())
        self.configure_size()

    def configure_size(self):
        self.d = max(40, self.ctx.dp(52)); self.n = self.d + 10; self.configure(width=self.n, height=self.n)
        self.font.configure(family=self.ctx.sans, size=max(12, round(self.d * .34)))

    def _hover(self, v):
        self.hot = v; self.draw()
        if self._tipj: self.after_cancel(self._tipj); self._tipj = None
        if self._tip: self._tip.destroy(); self._tip = None
        if v and not self.ui.open: self._tipj = self.after(450, self._show_tip)

    def _show_tip(self):
        self._tipj = None
        try:
            P = self.ctx.P; t = tk.Toplevel(self); t.wm_overrideredirect(True)
            tk.Label(t, text="Ask AI to edit this   Ctrl+J", bg=P["rail"], fg=P["rail_on"], font=self.ctx.f_small, padx=10, pady=4).pack(); t.update_idletasks()
            t.wm_geometry(f"+{self.winfo_rootx() - t.winfo_reqwidth() - 6}+{self.winfo_rooty() + (self.winfo_height() - t.winfo_reqheight()) // 2}"); self._tip = t
        except tk.TclError: pass

    def _release(self, e):
        if self._tip: self._tip.destroy(); self._tip = None
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height(): self.ui.toggle()

    def star_colour(self): return "#%02x%02x%02x" % STAR[self.ctx.dark][1]

    def draw(self):
        try:
            self.delete("all"); n, d = self.n, self.d; P = self.ctx.P
            if Image is not None and self.ui.fab_bg is not None:
                key = (n, d, self.ctx.dark, self.ui.fab_sig, self.hot, self.ui.open)
                if key != self._key:
                    bg = self.ui.fab_bg
                    self._img = ImageTk.PhotoImage(glass_disc(self.ctx, n, d, bg, self.hot, self.ui.open), master=self); self._key = key
                self.create_image(0, 0, image=self._img, anchor="nw")
            else:                                                     # no Pillow (or colours not read yet): an outline and the coloured star
                self.configure(bg=P["card"]); self.create_oval(5, 5, n - 5, n - 5, outline=P["border"], width=1)
                self.create_text(n / 2, n / 2 + 1, text=CLOSE if self.ui.open else GLYPH, fill=self.star_colour(), font=self.font)
            if self.ui.busy and self.ctx.motion:
                m = 5 + 4; self.create_arc(m, m, n - m, n - m, start=self.spin, extent=100, style="arc", outline=self.star_colour(), width=3)
            elif self.ui.busy: self.create_text(n / 2, n - 12, text="\u2026", fill=self.star_colour(), font=self.ctx.f_small)
            if self.focus_get() is self and self.ctx.kbd: self.create_oval(3, 3, n - 3, n - 3, outline=P["accent"], width=2)
        except tk.TclError: pass
