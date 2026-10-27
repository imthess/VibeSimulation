"""The dark icon rail on the left: Home, Logisim, Import & AI, Multisim, VLSI, and Settings at the bottom.
Mouse: click an icon (a label appears on hover). Keyboard: Tab to the rail, Up/Down to move, Enter to open; Ctrl+1-5 work everywhere."""
import tkinter as tk
from tkinter import font as tkfont

from .shapes import mix, rrect

ITEMS = (("home", "⌂", "Home", "Ctrl+1"), ("logisim", "⊞", "Logisim", "Ctrl+2"), ("import", "✦", "Import & AI", "Ctrl+3"), ("multisim", "∿", "Multisim", "Ctrl+4"), ("vlsi", "⬡", "VLSI", "Ctrl+5"))
BOTTOM = (("settings", "⚙", "Settings", "Ctrl+,"),)
SIZES = {"Small": (46, 34, 13), "Medium": (54, 40, 14), "Large": (66, 50, 17)}     # rail width, button, icon font size
STYLES = ("Floating", "Docked")
COLORS = ("Dark", "Accent", "Light", "Soft")
PAD = 8


class Rail(tk.Canvas):
    def __init__(self, ctx, master, shell):
        super().__init__(master, width=60, bd=0, highlightthickness=0, takefocus=1)
        self.ctx, self.sh, self.cur, self.hot, self.idx, self.tip, self._tip_job = ctx, shell, "home", None, 0, None, None
        self.keys = [i[0] for i in ITEMS + BOTTOM]
        self.font = tkfont.Font(root=ctx.root)
        self.bind("<Configure>", lambda e: self.draw()); self.bind("<Motion>", self._move); self.bind("<Leave>", lambda e: self._hot(None))
        self.bind("<ButtonRelease-1>", self._click); self.bind("<Button-1>", lambda e: self.focus_set())
        self.bind("<Up>", lambda e: self.step(-1)); self.bind("<Down>", lambda e: self.step(1))
        for k in ("<Return>", "<space>"): self.bind(k, lambda e: (self.sh.activity(self.keys[self.idx]) if self.keys[self.idx] != "settings" else self.sh.show("settings"), "break")[1])
        self.bind("<FocusIn>", lambda e: self.draw()); self.bind("<FocusOut>", lambda e: self.draw())
        ctx.themed.append(self.draw)

    # ---- settings
    def opt(self):
        c = self.ctx.cfg; size = c.get("rail_size", "Small"); w, b, fs = SIZES.get(size, SIZES["Small"])
        return dict(w=w, b=b, fs=fs, style="Docked", color="Accent", side=c.get("rail_side", "Left"))     # one flat bar in the accent colour

    def colors(self, color):
        P = self.ctx.P
        if color == "Accent": return dict(bg=P["accent"], sel=mix(P["accent"], "#000000", .22), hot=mix(P["accent"], "#000000", .12), fg=mix(P["accent"], "#ffffff", .72), on="#ffffff")
        if color == "Light": return dict(bg=P["card"], sel=P["soft_h"], hot=P["soft"], fg=P["muted"], on=P["text"])
        if color == "Soft": return dict(bg=P["soft_h"], sel=P["card"], hot=mix(P["soft_h"], P["card"], .5), fg=P["muted"], on=P["accent"])
        return dict(bg=P["rail"], sel=P["rail_sel"], hot=mix(P["rail"], P["rail_sel"], .55), fg=P["rail_fg"], on=P["rail_on"])

    def set(self, name): self.cur = name; self.idx = self.keys.index(name) if name in self.keys else 0; self.draw()

    def step(self, d): self.idx = (self.idx + d) % len(self.keys); self.draw(); return "break"

    # ---- geometry: key -> (x1, y1, x2, y2)
    def boxes(self):
        o = self.opt(); B = o["b"]; h = self.winfo_height(); out = {}
        cw = o["w"] + (2 * PAD if o["style"] == "Floating" else 0); x = (cw - B) // 2
        y = PAD + 14 + B // 2 + 12 if o["style"] == "Floating" else 6
        for k, *_ in ITEMS: out[k] = (x, y, x + B, y + B); y += B + 6
        yb = h - (PAD if o["style"] == "Floating" else 0) - 10 - B
        for k, *_ in BOTTOM: out[k] = (x, yb, x + B, yb + B)
        return out

    def _at(self, x, y):
        for k, (a, b, c, d) in self.boxes().items():
            if a <= x <= c and b <= y <= d: return k

    def _move(self, e):
        k = self._at(e.x, e.y); self._hot(k)

    def _hot(self, k):
        if k == self.hot: return
        self.hot = k; self.configure(cursor="hand2" if k else "arrow"); self.draw()
        if self._tip_job: self.after_cancel(self._tip_job); self._tip_job = None
        if self.tip: self.tip.destroy(); self.tip = None
        if k: self._tip_job = self.after(350, lambda k=k: self._show_tip(k))

    def _show_tip(self, k):
        try:
            o = self.opt(); P = self.ctx.P; lab = next(i for i in ITEMS + BOTTOM if i[0] == k); b = self.boxes()[k]
            t = tk.Toplevel(self); t.wm_overrideredirect(True)
            tk.Label(t, text=f"{lab[2]}   {lab[3]}", bg=P["rail"], fg=P["rail_on"], font=self.ctx.f_small, padx=10, pady=4).pack()
            t.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - 2 if o["side"] != "Right" else -t.winfo_reqwidth() + 2)
            t.wm_geometry(f"+{x}+{self.winfo_rooty() + (b[1] + b[3]) // 2 - t.winfo_reqheight() // 2}"); self.tip = t
        except (tk.TclError, StopIteration): pass

    def _click(self, e):
        k = self._at(e.x, e.y)
        if self.tip: self.tip.destroy(); self.tip = None
        if k == "settings": b = self.boxes()[k]; self.sh.manage_menu(self.winfo_rootx() + b[2] + 4, self.winfo_rooty() + b[1])
        elif k: self.sh.activity(k)

    def draw(self):
        try:
            self.delete("all"); P = self.ctx.P; o = self.opt(); h = self.winfo_height(); cw = o["w"] + (2 * PAD if o["style"] == "Floating" else 0)
            if int(self["width"]) != cw: self.configure(width=cw)
            self.configure(bg=P["bg"]); bx = self.boxes(); C = self.colors(o["color"]); B = o["b"]
            self.font.configure(size=o["fs"], family=self.ctx.f_body.actual("family"))
            rad = max(4, min(self.ctx.r_card, o["w"] // 2)); br = max(4, min(B // 2, round(self.ctx.r_card * .7)))
            if o["style"] == "Floating":
                for d, t in ((2, .5), (1, .75)):                    # soft shadow
                    rrect(self, PAD, PAD + d, PAD + o["w"], h - PAD + d, rad, fill=mix(P["bg"], P["shadow"], t * .6), outline="")
                rrect(self, PAD, PAD, PAD + o["w"], h - PAD, rad, fill=C["bg"], outline="")
                top = PAD + 14 + B // 4
            else:
                self.create_rectangle(0, 0, cw, h, fill=C["bg"], outline=""); self.create_line(cw - 1, 0, cw - 1, h, fill=P["border"] if o["color"] in ("Light", "Soft") else C["bg"])
                top = 14 + B // 4
            if o["style"] == "Floating":
                self.create_text(cw / 2, top, text="◈", fill=C["on"], font=self.font)
                ly = bx["home"][1] - 8; self.create_line(cw / 2 - B / 3, ly, cw / 2 + B / 3, ly, fill=mix(C["bg"], C["fg"], .35))
            for k, g, name, key in ITEMS + BOTTOM:
                a, b, c, d = bx[k]; on = k == self.cur
                if on and o["style"] == "Docked": self.create_rectangle(0, b, 2, d, fill=C["on"], outline="")          # VS Code's marker for the active view
                elif on: rrect(self, a, b, c, d, br, fill=C["sel"], outline="")
                if on: pass
                elif k == self.hot: rrect(self, a, b, c, d, br, fill=C["hot"], outline="")
                if self.focus_get() is self and self.ctx.kbd and self.keys[self.idx] == k: rrect(self, a + 1, b + 1, c - 1, d - 1, br, fill="", outline=C["fg"], width=2)
                self.create_text((a + c) / 2, (b + d) / 2, text=g, fill=C["on"] if (on or k == self.hot) else C["fg"], font=self.font)
        except tk.TclError: pass
