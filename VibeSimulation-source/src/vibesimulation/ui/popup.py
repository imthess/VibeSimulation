"""PopupMenu: a menu drawn inside the window that behaves like a normal desktop menu.
Closes on a click anywhere else, on Esc, when the window loses focus or is resized; works with Up/Down/Enter/Left/Right.
(Tk's own tk_popup menus stay open on many Linux desktops, so the app draws its own.)"""
import time
import tkinter as tk

from .shapes import mix


class PopupMenu:
    """Drop-in for the parts of tk.Menu the app uses: add_command / add_separator / add_cascade / add_checkbutton / tk_popup."""
    def __init__(self, ctx):
        self.ctx, self.items, self.rows, self.sel = ctx, [], [], None
        self.frame = self.shadow = self.top = None; self.child = None; self.parent = None; self._bind = []; self._job = None

    # ---- building (tk.Menu compatible)
    def add_command(self, label="", command=None, accelerator="", state="normal", **kw):
        self.items.append(dict(kind="command", label=label, cmd=command, acc=accelerator, state=state))

    def add_checkbutton(self, label="", variable=None, command=None, accelerator="", state="normal", **kw):
        self.items.append(dict(kind="check", label=label, var=variable, cmd=command, acc=accelerator, state=state))

    def add_cascade(self, label="", menu=None, state="normal", **kw):
        self.items.append(dict(kind="cascade", label=label, menu=menu, acc="›", state=state))

    def add_separator(self, **kw): self.items.append(dict(kind="sep", label="", state="disabled"))

    def index(self, what): return len(self.items) - 1 if what == "end" else int(what)
    def type(self, i): return {"sep": "separator"}.get(self.items[i]["kind"], self.items[i]["kind"])
    def entrycget(self, i, key): return self.items[i].get({"label": "label", "state": "state"}.get(key, key), "")
    def grab_release(self): pass

    # ---- showing
    def tk_popup(self, x, y, parent=None):
        ctx = self.ctx; self.parent = parent
        if parent is None: ctx.close_popups()
        w = ctx.root.winfo_containing(x, y) if parent is None else parent.top
        self.top = (w.winfo_toplevel() if w is not None else ctx.root)
        P = ctx.P; top = self.top
        self.shadow = tk.Frame(top, bd=0, bg=P["shadow"])
        self.frame = f = tk.Frame(top, bd=0, bg=P["border"], takefocus=1, highlightthickness=0)
        inner = tk.Frame(f, bd=0, bg=P["card"]); inner.pack(padx=1, pady=1)
        self.rows = []
        pad = ctx.dp(8)
        for i, it in enumerate(self.items):
            if it["kind"] == "sep":
                tk.Frame(inner, height=1, bd=0, bg=P["border"]).pack(fill="x", padx=10, pady=4); self.rows.append(None); continue
            dis = it["state"] == "disabled"
            r = tk.Frame(inner, bd=0, bg=P["card"], cursor="arrow" if dis else "hand2"); r.pack(fill="x", padx=5, pady=1)
            mark = "✓  " if it["kind"] == "check" and it["var"] is not None and it["var"].get() else ("     " if it["kind"] == "check" else "")
            fg = P["muted"] if dis else P["text"]
            l1 = tk.Label(r, text=mark + it["label"], bg=P["card"], fg=fg, font=ctx.f_body, anchor="w", padx=10, pady=pad // 2 + 2); l1.pack(side="left", fill="x", expand=True)
            l2 = tk.Label(r, text=it["acc"], bg=P["card"], fg=P["muted"], font=ctx.f_small, anchor="e", padx=14); l2.pack(side="right")
            self.rows.append((r, l1, l2))
            for wdg in (r, l1, l2):
                wdg.bind("<Enter>", lambda e, i=i: self.hilite(i)); wdg.bind("<ButtonRelease-1>", lambda e, i=i: self.activate(i))
        top.update_idletasks(); wd, ht = f.winfo_reqwidth(), f.winfo_reqheight()
        px, py = x - top.winfo_rootx(), y - top.winfo_rooty()
        px = max(4, min(px, top.winfo_width() - wd - 8)); py = max(4, min(py, top.winfo_height() - ht - 8))
        self.shadow.place(x=px + 2, y=py + 4, width=wd, height=ht); f.place(x=px, y=py); self.shadow.lift(); f.lift()
        self.at = (px, py, wd, ht)
        for k, fn in (("<Escape>", lambda e: (self.close_all(), "break")[1]), ("<Down>", lambda e: (self.move(1), "break")[1]), ("<Up>", lambda e: (self.move(-1), "break")[1]),
                      ("<Return>", lambda e: (self.activate(self.sel), "break")[1]), ("<KP_Enter>", lambda e: (self.activate(self.sel), "break")[1]), ("<space>", lambda e: (self.activate(self.sel), "break")[1]),
                      ("<Right>", lambda e: (self.open_child(self.sel, True), "break")[1]), ("<Left>", lambda e: (self.back(), "break")[1]),
                      ("<Home>", lambda e: (self.move(1, start=-1), "break")[1]), ("<End>", lambda e: (self.move(-1, start=len(self.rows)), "break")[1]), ("<Tab>", lambda e: "break")):
            f.bind(k, fn)
        self._bind = [(top, "<ButtonPress>", top.bind("<ButtonPress>", self._click, add="+")), (top, "<FocusOut>", top.bind("<FocusOut>", self._focus_out, add="+")),
                      (top, "<Configure>", top.bind("<Configure>", self._resized, add="+"))]
        if parent is None: ctx.popup = self
        try: f.focus_force()
        except tk.TclError: pass
        if parent is not None: self.hilite(self._first())

    # ---- selection
    def _first(self):
        for i, r in enumerate(self.rows):
            if r and self.items[i]["state"] != "disabled": return i

    def hilite(self, i):
        if i is None or i >= len(self.rows) or self.rows[i] is None: return
        P = self.ctx.P
        if self.sel is not None and self.sel < len(self.rows) and self.rows[self.sel]:
            for wd in self.rows[self.sel]: wd.configure(bg=P["card"])
        self.sel = i
        if self.items[i]["state"] != "disabled":
            for wd in self.rows[i]: wd.configure(bg=P["sel"])
        if self._job: self.frame.after_cancel(self._job); self._job = None
        if self.child is not None and not (self.items[i]["kind"] == "cascade" and self.child.owner == i): self.close_child()
        if self.items[i]["kind"] == "cascade" and self.items[i]["state"] != "disabled" and self.child is None:
            self._job = self.frame.after(220, lambda i=i: self.open_child(i))

    def move(self, d, start=None):
        n = len(self.rows); i = (self.sel if start is None and self.sel is not None else (start if start is not None else -1 if d > 0 else n))
        for _ in range(n):
            i = (i + d) % n
            if self.rows[i] and self.items[i]["state"] != "disabled": self.hilite(i); return

    def open_child(self, i, focus=False):
        if i is None: return
        it = self.items[i]
        if it["kind"] != "cascade" or it["state"] == "disabled": return
        if self._job:                                                  # a pending hover-open of the same submenu must not reopen it after Left closed it
            try: self.frame.after_cancel(self._job)
            except tk.TclError: pass
            self._job = None
        if self.child is not None and self.child.owner == i: 
            if focus: self.child.frame.focus_set()
            return
        self.close_child(); sub = it["menu"]; sub.owner = i
        r = self.rows[i][0]; self.child = sub
        sub.tk_popup(r.winfo_rootx() + r.winfo_width() - 4, r.winfo_rooty() - 4, parent=self)
        if focus: sub.frame.focus_force()

    def close_child(self):
        if self._job:
            try: self.frame.after_cancel(self._job)
            except (tk.TclError, AttributeError): pass
            self._job = None
        if self.child is not None:
            c, self.child = self.child, None; c.close()

    def back(self):
        if self.parent is not None:
            p = self.parent; self.close()
            if p._job:
                try: p.frame.after_cancel(p._job)
                except tk.TclError: pass
                p._job = None
            p.frame.focus_force()

    # ---- actions
    def activate(self, i):
        if i is None or i >= len(self.items): return
        it = self.items[i]
        if it["state"] == "disabled" or it["kind"] == "sep": return
        if it["kind"] == "cascade": self.open_child(i, True); return
        if it["kind"] == "check" and it["var"] is not None: it["var"].set(not it["var"].get())
        cmd = it["cmd"]; self.close_all()
        if cmd: self.ctx.root.after(20, cmd)

    def _inside(self, w):
        s = str(w)
        for m in (self, self.child):
            if m is not None and m.frame is not None and (s == str(m.frame) or s.startswith(str(m.frame) + ".")): return True
        return self.child._inside(w) if self.child is not None else False

    def _click(self, e):
        if not self._inside(e.widget):
            self.ctx.popup_closed = (time.time(), e.widget); self.close_all()

    def _focus_out(self, e):
        if e.widget is self.top and self.frame is not None:
            self.frame.after(80, lambda: self.close_all() if (self.frame is not None and self.top.focus_get() is None) else None)

    def _resized(self, e):
        if e.widget is self.top and self.frame is not None and (e.width, e.height) != getattr(self, "_sz", (e.width, e.height)): self.close_all()
        self._sz = (e.width, e.height)

    def close_all(self):
        m = self
        while m.parent is not None: m = m.parent
        m.close()

    def close(self):
        if self.frame is None: return
        self.close_child()
        for wdg, seq, fid in self._bind:
            try: wdg.unbind(seq, fid)
            except tk.TclError: pass
        self._bind = []
        for wdg in (self.frame, self.shadow):
            try: wdg.destroy()
            except tk.TclError: pass
        self.frame = self.shadow = None; self.sel = None
        if self.ctx.popup is self: self.ctx.popup = None
        if self.parent is not None: self.parent.child = None
        else:
            try: self.ctx.root.focus_set()
            except tk.TclError: pass
