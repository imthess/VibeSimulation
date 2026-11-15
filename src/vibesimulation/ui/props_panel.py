"""Properties panel at the bottom of the side bar (like Logisim-evolution's attribute table).

A page gives it a title and a list of fields; every change is applied the moment it is committed (Enter, leaving the box, choosing from a list)."""
import tkinter as tk
from tkinter import ttk


class Field:
    """kind: ro (text only) | str | int | choice | bool.  apply(value) is called on commit and may raise to refuse."""
    def __init__(self, label, kind, value, apply=None, choices=()):
        self.label, self.kind, self.value, self.apply, self.choices = label, kind, value, apply, list(choices)


class PropsPanel(tk.Frame):
    def __init__(self, ctx, master):
        super().__init__(master, bd=0); self.ctx = ctx; self._sig = None; self.fields = []; self.vars = []
        self.head = tk.Label(self, text="Properties", font=ctx.f_bold, anchor="w"); self.head.pack(fill="x", padx=14, pady=(8, 2))
        self.sub = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left", wraplength=230); self.sub.pack(fill="x", padx=14)
        self.grid_f = tk.Frame(self, bd=0); self.grid_f.pack(fill="x", padx=14, pady=(4, 8))
        self.grid_f.columnconfigure(1, weight=1); self.paint()

    def paint(self):
        P = self.ctx.P
        for w in (self, self.grid_f): w.configure(bg=P["card"])
        self.head.configure(bg=P["card"], fg=P["text"]); self.sub.configure(bg=P["card"], fg=P["muted"])
        self._sig = None
        for ch in self.grid_f.winfo_children():
            if isinstance(ch, tk.Label): ch.configure(bg=P["card"], fg=P["muted"])

    def focus_inside(self):
        f = self.focus_get() if self.winfo_exists() else None
        return f is not None and str(f).startswith(str(self.grid_f))

    def show(self, title, sub, fields, sig):
        """Rebuild only when the selection (sig) changed, and never while the person is typing in a box."""
        if sig == self._sig or self.focus_inside(): return
        self._sig = sig
        for ch in self.grid_f.winfo_children(): ch.destroy()
        P = self.ctx.P; self.fields, self.vars = fields, []
        self.head.configure(text=title); self.sub.configure(text=sub)
        for i, f in enumerate(fields):
            tk.Label(self.grid_f, text=f.label, bg=P["card"], fg=P["muted"], font=self.ctx.f_small, anchor="w").grid(row=i, column=0, sticky="w", pady=2)
            if f.kind == "ro":
                w = tk.Label(self.grid_f, text=str(f.value), bg=P["card"], fg=P["text"], font=self.ctx.f_small, anchor="w"); self.vars.append(None)
            elif f.kind == "choice":
                v = tk.StringVar(value=str(f.value)); w = ttk.Combobox(self.grid_f, textvariable=v, values=f.choices, state="readonly", style="Modern.TCombobox", width=10)
                w.bind("<<ComboboxSelected>>", lambda e, f=f, v=v: self._commit(f, v.get())); self.vars.append(v)
            elif f.kind == "bool":
                v = tk.BooleanVar(value=bool(f.value)); w = ttk.Checkbutton(self.grid_f, variable=v, style="Card.TCheckbutton", command=lambda f=f, v=v: self._commit(f, v.get())); self.vars.append(v)
            else:
                v = tk.StringVar(value=str(f.value)); w = ttk.Entry(self.grid_f, textvariable=v, style="Modern.TEntry", width=10)
                w.bind("<Return>", lambda e, f=f, v=v: self._commit(f, v.get())); w.bind("<FocusOut>", lambda e, f=f, v=v: self._commit(f, v.get(), quiet=True)); self.vars.append(v)
            w.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=2)

    def _commit(self, f, raw, quiet=False):
        if f.apply is None: return
        try:
            val = int(raw) if f.kind == "int" else raw
        except ValueError:
            if not quiet: self.ctx.say(f.label, "Please type a whole number.")
            return
        if val == f.value or (f.kind in ("str",) and str(val) == str(f.value)): return
        self._sig = None
        try: f.apply(val)
        except Exception as ex: self.ctx.say(f.label, str(ex))
