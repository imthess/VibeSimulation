"""The prompt bar's parts: the rounded text box, the message bubble and the rounded panel (card, soft shadow) that holds them."""
import tkinter as tk

from vibesimulation.ui.assistant.backdrop import Image, ImageTk, _rgb, panel_image
from vibesimulation.ui.look.shapes import mix, rrect
class Field(tk.Canvas):
    """The prompt box: rounded, grows from one to a few lines, shows a hint while empty."""
    PADX, PADY = 16, 10

    def __init__(self, ctx, master, on_send, max_lines=6):
        super().__init__(master, bd=0, highlightthickness=0)
        self.ctx, self.on_send, self.max, self._focus = ctx, on_send, max_lines, False
        self.txt = tk.Text(self, wrap="word", height=1, width=10, bd=0, highlightthickness=0, relief="flat", padx=0, pady=0, undo=True, font=ctx.f_body, exportselection=False)
        self.ph = tk.Label(self, anchor="w", justify="left", font=ctx.f_body, bd=0, cursor="xterm")
        self.win = self.create_window(self.PADX, self.PADY, window=self.txt, anchor="nw"); self.phw = self.create_window(self.PADX, self.PADY, window=self.ph, anchor="nw")
        self.bind("<Configure>", self._size); self.ph.bind("<Button-1>", lambda e: self.txt.focus_set())
        t = self.txt; t.bind("<<Modified>>", self._changed); t.bind("<FocusIn>", lambda e: self._focused(True)); t.bind("<FocusOut>", lambda e: self._focused(False))
        if on_send:                                                      # a prompt box sends on Enter; a plain multi-line box keeps Enter for new lines
            t.bind("<Return>", lambda e: (self.on_send(), "break")[1]); t.bind("<KP_Enter>", lambda e: (self.on_send(), "break")[1])
            t.bind("<Shift-Return>", lambda e: (t.insert("insert", "\n"), "break")[1])
        for k in ("a", "A"): t.bind(f"<Control-Key-{k}>", lambda e: (t.tag_add("sel", "1.0", "end-1c"), "break")[1])
        for k in ("z",): t.bind(f"<Control-Key-{k}>", lambda e: (self._undo(), "break")[1])
        for k in ("y", "Y", "Z"): t.bind(f"<Control-Key-{k}>", lambda e: (self._redo(), "break")[1])
        ctx.themed.append(self.paint); self.paint()

    def _undo(self):
        try: self.txt.edit_undo()
        except tk.TclError: pass

    def _redo(self):
        try: self.txt.edit_redo()
        except tk.TclError: pass

    def get(self): return self.txt.get("1.0", "end-1c")

    def set(self, text): self.txt.delete("1.0", "end"); self.txt.insert("1.0", text); self._changed()

    def hint(self, text): self.ph.configure(text=text)

    def focus_set(self): self.txt.focus_set()

    def _focused(self, v): self._focus = v; self.paint()

    def _changed(self, e=None):
        self.txt.edit_modified(False); self.itemconfigure(self.phw, state="hidden" if self.get() else "normal"); self.after_idle(self._fit)

    def _fit(self):
        try:
            n = self.txt.count("1.0", "end-1c", "displaylines"); n = n[0] if n else 1
            n = max(1, min(self.max, int(n))); ls = self.ctx.f_body.metrics("linespace")
            self.txt.configure(height=n); h = n * ls + 2 * self.PADY + 2
            if int(self["height"]) != h: self.configure(height=h)
        except tk.TclError: pass

    def _size(self, e=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.itemconfigure(self.win, width=max(20, w - 2 * self.PADX), height=max(10, h - 2 * self.PADY)); self.itemconfigure(self.phw, width=max(20, w - 2 * self.PADX)); self.paint(); self.after_idle(self._fit)

    def paint(self):
        try:
            P = self.ctx.P; self.configure(bg=P["card"]); w, h = self.winfo_width(), self.winfo_height()
            self.txt.configure(bg=P["field"], fg=P["text"], insertbackground=P["text"], selectbackground=P["sel"], selectforeground=P["text"], inactiveselectbackground=P["sel"])
            self.ph.configure(bg=P["field"], fg=P["muted"]); self.delete("bg")
            if w > 10 and h > 10: rrect(self, 0, 0, w, h, min(h / 2, 22), fill=P["field"], outline=P["accent"] if self._focus else P["border"], width=1, tags="bg"); self.tag_lower("bg")
        except tk.TclError: pass


class Bubble(tk.Canvas):
    """A rounded message (status, answer or error) with read-only selectable text."""
    PADX, PADY, MAXL = 14, 9, 9

    def __init__(self, ctx, master):
        super().__init__(master, bd=0, highlightthickness=0)
        self.ctx, self.kind, self.msg = ctx, "info", ""
        self.txt = tk.Text(self, wrap="word", height=1, width=10, bd=0, highlightthickness=0, relief="flat", padx=0, pady=0, font=ctx.f_small, cursor="arrow", exportselection=False)
        self.win = self.create_window(self.PADX, self.PADY, window=self.txt, anchor="nw")
        self.txt.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in "ca") or e.keysym in ("Up", "Down", "Prior", "Next", "Home", "End") else "break")
        self.bind("<Configure>", self._size); ctx.themed.append(self.paint)

    def set(self, text, kind="info"):
        self.msg, self.kind = text, kind; self.txt.configure(state="normal"); self.txt.delete("1.0", "end"); self.txt.insert("1.0", text); self.txt.yview_moveto(0)
        self.paint(); self.after_idle(self._fit)

    def _fit(self):
        try:
            n = self.txt.count("1.0", "end-1c", "displaylines"); n = max(1, min(self.MAXL, int(n[0] if n else 1)))
            self.txt.configure(height=n); h = n * self.ctx.f_small.metrics("linespace") + 2 * self.PADY + 2
            if int(self["height"]) != h: self.configure(height=h)
        except tk.TclError: pass

    def _size(self, e=None):
        w, h = self.winfo_width(), self.winfo_height(); self.itemconfigure(self.win, width=max(20, w - 2 * self.PADX), height=max(10, h - 2 * self.PADY)); self.paint(); self.after_idle(self._fit)

    def colours(self):
        P = self.ctx.P
        return {"ok": (P["okbg"], P["ok"]), "bad": (P["badbg"], P["bad"]), "info": (P["infobg"], P["text"])}.get(self.kind, (P["field"], P["text"]))

    def paint(self):
        try:
            P = self.ctx.P; bg, fg = self.colours(); w, h = self.winfo_width(), self.winfo_height()
            self.configure(bg=P["card"]); self.txt.configure(bg=bg, fg=fg, selectbackground=P["sel"], selectforeground=P["text"], inactiveselectbackground=P["sel"]); self.delete("bg")
            if w > 10 and h > 10: rrect(self, 0, 0, w, h, min(h / 2, 18), fill=bg, outline="", tags="bg"); self.tag_lower("bg")
        except tk.TclError: pass


# ------------------------------------------------------------------------------------------------- the prompt bar
class Panel(tk.Canvas):
    M, PAD = 8, 18                                 # room for the shadow, inner padding

    def __init__(self, ctx, master, ui):
        super().__init__(master, bd=0, highlightthickness=0)
        self.ctx, self.ui = ctx, ui; self._img = None; self._key = None; self._job = None
        self.inner = tk.Frame(self, bd=0); self.win = self.create_window(self.M + self.PAD, self.M + self.PAD, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._fit()); self.bind("<Configure>", self._size)

    def _fit(self):
        h = self.inner.winfo_reqheight() + 2 * (self.M + self.PAD)
        if int(self["height"]) != h: self.configure(height=h)

    def _size(self, e=None):
        self.itemconfigure(self.win, width=max(60, self.winfo_width() - 2 * (self.M + self.PAD))); self.schedule(); self.after(40, self.ui.refresh)

    def schedule(self):
        if self._job is None: self._job = self.after(20, self.paint)

    def paint(self):
        self._job = None
        try:
            W, H = self.winfo_width(), self.winfo_height(); P = self.ctx.P
            self.inner.configure(bg=P["card"]); self.delete("bg")
            if W < 80 or H < 60: return
            r = min(26, (H - 2 * self.M) // 2) if self.ctx.r_card > 20 else min(self.ctx.r_card, 18)
            if Image is not None and self.ui.panel_bg is not None and self.ui.panel_bg.size == (W, H):
                key = (W, H, r, P["card"], self.ctx.dark, self.ui.panel_sig)
                if key != self._key:
                    bg = self.ui.panel_bg
                    self._img = ImageTk.PhotoImage(panel_image(self.ctx, W, H, self.M, r, _rgb(self.ctx, P["card"]), _rgb(self.ctx, mix(P["border"], P["card"], .35)), bg), master=self); self._key = key
                self.create_image(0, 0, image=self._img, anchor="nw", tags="bg")
            else:
                self.configure(bg=P["bg"]); rrect(self, self.M, self.M, W - self.M, H - self.M, r, fill=P["card"], tags="bg")
            self.tag_lower("bg")
        except tk.TclError: pass
