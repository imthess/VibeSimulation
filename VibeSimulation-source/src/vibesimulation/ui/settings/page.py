"""Settings: categories on the left, a search box, and rows on the right (label + explanation + control).
Every change is applied and saved immediately. Everything works with Tab / arrow keys / Space / Enter as well as the mouse."""
import tkinter as tk
from tkinter import colorchooser, ttk

from ... import APP_NAME, __version__
from ..widgets import Btn, Card, ScrollFrame, Segmented, Switch

CATS = ("Commonly Used", "Appearance", "General", "Keyboard", "Logisim", "Multisim", "AI & Import", "About")
COMMON = ("Theme", "Accent colour", "Text size", "Density", "Show dotted grid behind the circuit", "Show intermediate signals in the truth table", "Significant digits in results", "Show status bar", "Pane layout")


class SettingsPage(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.cur, self.setters = CATS[0], {}
        self.top = tk.Frame(self, bd=0); self.top.pack(side="top", fill="x", padx=14, pady=(12, 4))
        self.hint = tk.Label(self.top, text="Settings", font=ctx.f_title, anchor="w"); self.hint.pack(side="left", padx=(0, 18))
        self.q = tk.StringVar(); self.q.trace_add("write", lambda *a: self.build())
        self.search = ttk.Entry(self.top, textvariable=self.q, style="Modern.TEntry"); self.search.pack(side="left", fill="x", expand=True, ipady=3)
        self.ph = tk.Label(self.search, text="⌕  Search settings  (Ctrl+F)", font=ctx.f_small, cursor="xterm"); self.ph.place(x=8, rely=0.5, anchor="w"); self.ph.bind("<Button-1>", lambda e: self.search.focus_set())
        self.q.trace_add("write", lambda *a: self.ph.place_forget() if self.q.get() else self.ph.place(x=8, rely=0.5, anchor="w"))
        self.count = tk.Label(self.top, text="", font=ctx.f_small, anchor="e", width=20); self.count.pack(side="left", padx=(10, 0))
        self.search.bind("<Escape>", lambda e: (self.q.set(""), self.focus_cat(), "break")[1]); self.search.bind("<Down>", lambda e: (self.focus_cat(), "break")[1])
        self.holder = tk.Frame(self, bd=0); self.holder.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=(4, 8))
        ctx.themed.append(self._paint); self._paint(); self.card = None; self.build()

    # ---- navigation
    def focus_first(self):
        try: self.search.focus_set()
        except tk.TclError: pass
    def focus_search(self): self.search.focus_set(); self.search.select_range(0, "end")
    def focus_cat(self):
        v = self.shell.side.view() if self.shell.side.winfo_ismapped() else None
        if v is not None and hasattr(v, "t"): v.t.focus_set()
        else: self.holder.focus_set()

    def pick(self, cat, focus=False):
        self.cur = cat
        if self.q.get(): self.q.set("")
        else: self.build()
        self.sync_nav()
        if focus: self.focus_cat()

    def sync_nav(self):
        v = self.shell.side.view() if hasattr(self.shell, "side") else None
        if v is not None and hasattr(v, "show_cat"): v.show_cat(self.cur, bool(self.q.get().strip()))

    def refresh(self):
        for key, fn in list(self.setters.items()):
            try: fn()
            except tk.TclError: self.setters.pop(key, None)
        self._paint()

    # ---- building
    def build(self):
        ctx = self.ctx; query = self.q.get().strip().lower()
        if self.card is not None: self.card.destroy()
        self.setters = {}
        self.card = Card(ctx, self.holder, 0, "Search results" if query else self.cur)
        self.count.configure(text=""); self.card.pack(fill="both", expand=True)
        self.sf = ScrollFrame(ctx, self.card.body); self.sf.pack(fill="both", expand=True)
        self.rows = self.sf.inner
        defs = self.defs()
        if query:
            hits = [d for d in defs if query in (d["label"] + " " + d.get("desc", "") + " " + d["cat"]).lower()]
            if not hits: self.text("Nothing matches “%s”." % query, muted=True)
            for d in hits: self.row(d, show_cat=True)
            self.count.configure(text=f"{len(hits)} setting{'s' if len(hits) != 1 else ''} found")
        else:
            self.sections(self.cur, defs)
        self.sync_nav(); self.sf.watch_focus(); self._paint()

    def text(self, t, muted=False, pady=(0, 10)):
        l = self.lab(self.rows, t, "muted" if muted else "text", font=self.ctx.f_body if not muted else self.ctx.f_small, wraplength=620, justify="left", anchor="w")
        l.pack(fill="x", pady=pady, padx=4); return l

    def lab(self, parent, text, fg="text", bg="card", **kw):
        l = tk.Label(parent, text=text, **kw)
        def paint():
            P = self.ctx.P; l.configure(bg=P[bg], fg=P[fg])
        self.ctx.themed.append(paint); paint(); return l

    def frame(self, parent, bg="card", **kw):
        f = tk.Frame(parent, bd=0, **kw); self.ctx.themed.append(lambda: f.configure(bg=self.ctx.P[bg])); f.configure(bg=self.ctx.P[bg]); return f

    def sections(self, cat, defs):
        if cat == "Commonly Used":
            for d in defs:
                if d["label"] in COMMON: self.row(d, show_cat=True)
            return
        if cat == "Keyboard": return self.keyboard()
        if cat == "About": return self.about()
        for d in defs:
            if d["cat"] == cat: self.row(d)
        if cat == "General": self.text("Settings are saved in your home folder (.vibesimulation.json).", muted=True, pady=(14, 0))
        if cat == "AI & Import": self.text("The model, provider and server address are chosen on the Import & AI page, where you insert the picture.", muted=True)

    def row(self, d, show_cat=False):
        r = self.frame(self.rows); r.pack(fill="x", pady=0)
        tk.Frame(r, height=1, bd=0, bg=self.ctx.P["border"]).pack(fill="x") if False else None
        inner = self.frame(r); inner.pack(fill="x", padx=4, pady=self.ctx.dp(10))
        left = self.frame(inner); left.pack(side="left", fill="x", expand=True)
        head = self.frame(left); head.pack(fill="x")
        self.lab(head, d["cat"] + ": ", "muted", font=self.ctx.f_body, anchor="w").pack(side="left")
        self.lab(head, d["label"], font=self.ctx.f_bold, anchor="w").pack(side="left")
        if d.get("desc"): self.lab(left, d["desc"], "muted", font=self.ctx.f_small, anchor="w", justify="left", wraplength=360).pack(fill="x")
        ctl = d["make"](inner)
        if ctl is not None: ctl.pack(side="right", padx=(16, 0))
        sep = tk.Frame(r, height=1, bd=0); sep.pack(fill="x"); self.ctx.themed.append(lambda: sep.configure(bg=self.ctx.P["border"])); sep.configure(bg=self.ctx.P["border"])

    # ---- control factories (each registers a setter so the page follows changes made elsewhere, e.g. Ctrl+K)
    def seg(self, key, options, default, cast=str, after=None):
        def make(parent):
            cur = self.ctx.cfg.get(key, default)
            s = Segmented(self.ctx, parent, options, cur if cast is str else cast(cur), lambda v: self.set(key, v if cast is str else cast(v), after))
            self.setters[key] = lambda: s.set(self.ctx.cfg.get(key, default) if cast is str else cast(self.ctx.cfg.get(key, default))); return s
        return make

    def switch(self, key, default, after=None):
        def make(parent):
            v = tk.BooleanVar(value=bool(self.ctx.cfg.get(key, default))); sw = Switch(self.ctx, parent, v, lambda: self.set(key, v.get(), after))
            self.setters[key] = lambda: v.set(bool(self.ctx.cfg.get(key, default))); return sw
        return make

    def combo(self, key, default, values, after=None, width=9):
        def make(parent):
            v = tk.StringVar(value=str(self.ctx.cfg.get(key, default)))
            cb = ttk.Combobox(parent, textvariable=v, values=[str(x) for x in values], state="readonly", style="Modern.TCombobox", width=width)
            cb.bind("<<ComboboxSelected>>", lambda e: self.set(key, type(default)(v.get()) if not isinstance(default, str) else v.get(), after))
            self.setters[key] = lambda: v.set(str(self.ctx.cfg.get(key, default))); return cb
        return make

    def button(self, text, fn, kind="secondary"):
        return lambda parent: Btn(self.ctx, parent, text, fn, kind, pady=5)

    def set(self, key, val, after=None):
        if after is not None and after == "look": self.shell.set_pref(key, val); return
        self.ctx.cfg[key] = val; self.ctx.save_cfg()
        if after: after()
        if key == "show_status": self.shell.status.refresh()

    def custom_color(self):
        c = colorchooser.askcolor(color=self.ctx.P["accent"], title="Accent colour", parent=self.ctx.root)
        return c[1] if c and c[1] else None

    def defs(self):
        from .items import all_items
        return all_items(self)

    def keyboard(self):
        ctx = self.ctx
        self.text("Press  F1  anywhere for this list in a window, or  Ctrl+K  to search every command.", muted=True)
        last = None
        for c in self.shell.commands:
            if not c.keys: continue
            if c.group != last:
                last = c.group; self.lab(self.rows, c.group.upper(), "muted", font=ctx.f_small, anchor="w").pack(fill="x", padx=4, pady=(12, 2))
            r = self.frame(self.rows); r.pack(fill="x", padx=4, pady=2)
            self.lab(r, c.title, font=ctx.f_body, anchor="w").pack(side="left")
            k = tk.Label(r, text=c.keys, font=ctx.f_small, padx=8, pady=1); k.pack(side="right")
            self.ctx.themed.append(lambda k=k: k.configure(bg=ctx.P["soft"], fg=ctx.P["text"])); k.configure(bg=ctx.P["soft"], fg=ctx.P["text"])
        f = self.frame(self.rows); f.pack(anchor="w", pady=16, padx=4); Btn(ctx, f, "Open command palette", self.shell.open_palette, "primary", pady=5).pack()

    def about(self):
        self.text(f"{APP_NAME} {__version__}\nTurns a photo of a digital circuit into an editable Logisim circuit, with a truth table, PDF and .circ export, plus a Multisim (analog) workspace.", muted=True)

    def _paint(self):
        P = self.ctx.P
        for w in (self, self.holder): w.configure(bg=P["bg"])
        self.hint.configure(bg=P["bg"], fg=P["text"]); self.count.configure(bg=P["bg"], fg=P["muted"]); self.top.configure(bg=P["bg"]); self.ph.configure(bg=P["input"] if "input" in P else P["soft"], fg=P["muted"])
