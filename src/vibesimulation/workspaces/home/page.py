"""Home page: greeting, big tiles (Logisim, Import & AI, Multisim, VLSI, SystemVerilog) and your recent files."""
import os
import tkinter as tk

from vibesimulation.ui.look.shapes import mix, rrect
from vibesimulation.ui.controls.widgets import Btn, Focusable
TILES = (("logisim", "⊞", "Logisim", "Digital circuits: gates, adders, MUX, decoders…\nEdit the circuit, JSON and truth table side by side.", "Ctrl+2"),
         ("import", "✦", "Import & AI", "Insert a photo or screenshot, choose an AI model\n(local or cloud) and turn it into a circuit.", "Ctrl+3"),
         ("multisim", "∿", "Multisim", "Electrical circuits: resistors, sources, diodes…\nDC results and a SPICE netlist for Multisim.", "Ctrl+4"),
         ("vlsi", "⬡", "VLSI", "Write a circuit as Verilog.\nSee it drawn as a circuit with its truth table.", "Ctrl+5"),
         ("systemverilog", "◈", "SystemVerilog", "Write a circuit in SystemVerilog: logic, enum, struct,\npackages, always_ff / always_comb.", "Ctrl+6"))


class Tile(Focusable):
    """Big rounded tile. Click, or focus it (Tab / arrow keys) and press Enter or Space."""
    def __init__(self, ctx, master, glyph, name, text, keys, command):
        super().__init__(ctx, master, cursor="hand2")
        self.glyph, self.name, self.text, self.keys, self.cmd, self.hover, self._lift = glyph, name, text, keys, command, False, 0.0
        self.bind("<Enter>", lambda e: self._h(True)); self.bind("<Leave>", lambda e: self._h(False)); self.bind("<Button-1>", lambda e: (self.focus_set(), self.cmd()))
        for k in ("<Return>", "<space>", "<KP_Enter>"): self.bind(k, lambda e: (self.cmd(), "break")[1])
        self.paint()

    W = 270

    def paint(self):
        c = self.ctx; self.configure(width=c.dp(self.W) + 8, height=c.dp(40) + c.dp(72) + c.f_title.metrics("linespace") + 3 * c.f_small.metrics("linespace") + c.dp(44) + 8); self.draw()

    def _h(self, v):
        self.hover = v; tgt = 1.0 if v else 0.0
        def step():
            try:
                d = tgt - self._lift
                if not self.ctx.motion or abs(d) < 0.1: self._lift = tgt; self.draw(); return
                self._lift += d * 0.5; self.draw(); self.after(16, step)
            except tk.TclError: pass
        step()

    def draw(self):
        try:
            self.delete("all"); c = self.ctx; P = c.P; self.configure(bg=P["card"])
            w, h = c.dp(self.W), int(self["height"]) - 8; y = 4; x = 4
            rrect(self, x, y + 2, x + w, y + h + 2, c.r_card, fill=mix(P["card"], P["shadow"], 0.25), outline="")      # soft edge under the tile
            rrect(self, x, y, x + w, y + h, c.r_card, fill=P["soft_h"] if self.hover else P["soft"], outline=P["accent"] if (self.focused and c.kbd) else "", width=2)
            R = c.dp(36); cy = y + c.dp(24) + R
            rrect(self, x + w / 2 - R, cy - R, x + w / 2 + R, cy + R, 999, fill=P["accent"]); gl_fg = P["accent_fg"]
            self.create_text(x + w / 2, cy, text=self.glyph, font=c.f_glyph, fill=gl_fg)
            ty = cy + R + c.dp(14)
            self.create_text(x + w / 2, ty, text=self.name, font=c.f_title, fill=P["text"], anchor="n")
            self.create_text(x + w / 2, ty + c.f_title.metrics("linespace") + 6, text=self.text, font=c.f_small, fill=P["muted"], anchor="n", justify="center", width=w - 36)
            self.create_text(x + w - 12, y + 10, text=self.keys, font=c.f_small, fill=P["muted"], anchor="ne")
        except tk.TclError: pass


class HomePage(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.box = tk.Frame(self, bd=0); self.box.place(relx=0.5, rely=0.5, anchor="center"); self.inner = tk.Frame(self.box, bd=0); self.inner.pack(padx=34, pady=28); ctx.glass.attach(self.box, ctx.r_card + 10, "panel", (3, 3, 3, 8))
        self.title = tk.Label(self.inner, text="What do you want to work on?", font=ctx.f_big); self.title.pack(pady=(0, 4))
        self.sub = tk.Label(self.inner, text="Turn a picture of a circuit into an editable, simulatable circuit.", font=ctx.f_body); self.sub.pack(pady=(0, 22))
        self.row = tk.Frame(self.inner, bd=0); self.row.pack()
        self.tiles = []
        for key, glyph, name, text, k in TILES:
            t = Tile(ctx, self.row, glyph, name, text, k, lambda key=key: shell.show(key)); self.tiles.append(t)
        self._cols = 0; self.bind("<Configure>", lambda e: self._arrange())
        for i, t in enumerate(self.tiles):
            t.bind("<Left>", lambda e, i=i: (self.tiles[max(0, i - 1)].focus_set(), "break")[1]); t.bind("<Right>", lambda e, i=i: (self.tiles[min(len(self.tiles) - 1, i + 1)].focus_set(), "break")[1])
        self.rec_title = tk.Label(self.inner, text="Recent files", font=ctx.f_bold, anchor="w"); self.rec = tk.Frame(self.inner, bd=0)
        self.hint = tk.Label(self.inner, text="Tip:  press  Ctrl+K  to search every command  ·  F1 shows all keyboard shortcuts", font=ctx.f_small); self.hint.pack(pady=(20, 0))
        ctx.themed.append(self._paint); self._paint(); self.bind("<Map>", lambda e: self.recent())

    def _arrange(self):
        """All tiles in one row when the page is wide enough, else two rows."""
        n, w = len(self.tiles), self.winfo_width()
        tw = self.tiles[0].ctx.dp(Tile.W) + 24
        cols = n if w >= n * tw + 160 else 3 if w >= 3 * tw + 60 else 2 if w >= 2 * tw + 20 else 1
        if cols == self._cols: return
        self._cols = cols
        for i, t in enumerate(self.tiles): t.grid(row=i // cols, column=i % cols, padx=8, pady=6)

    def focus_first(self): self.tiles[0].focus_set()

    def recent(self):
        for w in self.rec.winfo_children(): w.destroy()
        items = [x for x in self.ctx.cfg.get("recent", []) if os.path.isfile(x[0]) and x[0].lower().endswith((".json", ".txt"))][:4]
        self.rec_title.pack_forget(); self.rec.pack_forget()
        if not items: return
        self.rec_title.pack(anchor="w", padx=10, pady=(22, 4), before=self.hint); self.rec.pack(fill="x", before=self.hint)
        for p, _ in items:
            sh = self.shell
            b = Btn(self.ctx, self.rec, f"{os.path.basename(p)}      {os.path.dirname(p)}", lambda p=p: sh.cur_actions_for_logisim().json_open(p) and sh.show("logisim"), "ghost", anchor="w", font=self.ctx.f_body, pady=5)
            b.pack(fill="x", padx=4, pady=1)

    def _paint(self):
        P = self.ctx.P
        for w in (self, self.box, self.inner, self.row, self.rec): w.configure(bg=P["card"])
        self.title.configure(bg=P["card"], fg=P["text"]); self.sub.configure(bg=P["card"], fg=P["muted"]); self.rec_title.configure(bg=P["card"], fg=P["muted"]); self.hint.configure(bg=P["card"], fg=P["muted"])
        self.ctx.glass.attach(self.box, self.ctx.r_card + 10, "panel", (3, 3, 3, 8))
