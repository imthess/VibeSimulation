"""Themed dialogs: message/question box and an in-app file chooser that looks the same on every system."""
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .theme import auto
from .widgets import Btn

TkBase = tk


class FormDialog(TkBase.Toplevel):
    """Several labelled fields in one box. fields = [(key, label, initial, choices or None)]; result = {key: text} or None if cancelled."""
    def __init__(self, ctx, title, msg, fields, check=None):
        super().__init__(ctx.root); P = ctx.P; self.result = None; self.vars = {}; self.check = check
        self.title(title); self.configure(bg=P["card"]); self.transient(ctx.root); self.resizable(False, False)
        tk.Label(self, text=title, bg=P["card"], fg=P["text"], font=ctx.f_title, anchor="w").pack(fill="x", padx=22, pady=(18, 4))
        if msg: tk.Label(self, text=msg, bg=P["card"], fg=P["muted"], font=ctx.f_body, wraplength=420, justify="left", anchor="w").pack(fill="x", padx=22, pady=(0, 8))
        grid = tk.Frame(self, bg=P["card"]); grid.pack(fill="x", padx=22); grid.columnconfigure(1, weight=1); first = None
        for r, (key, label, init, choices) in enumerate(fields):
            tk.Label(grid, text=label, bg=P["card"], fg=P["text"], font=ctx.f_body, anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 12))
            self.vars[key] = v = tk.StringVar(value=str(init))
            if choices: w = ttk.Combobox(grid, textvariable=v, values=list(choices), state="readonly", style="Modern.TCombobox", width=18)
            else: w = ttk.Entry(grid, textvariable=v, style="Modern.TEntry", width=20); w.bind("<Return>", lambda e: self.ok())
            w.grid(row=r, column=1, sticky="ew", pady=3, ipady=2); first = first or w
        self.err = tk.Label(self, text="", bg=P["card"], fg=P["bad"] if "bad" in P else "#c0392b", font=ctx.f_small, anchor="w", wraplength=420, justify="left"); self.err.pack(fill="x", padx=22, pady=(6, 0))
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=22, pady=14)
        Btn(ctx, row, "OK", self.ok, "primary").pack(side="right", padx=(8, 0)); Btn(ctx, row, "Cancel", self.destroy, "secondary").pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        if first is not None: first.focus_set()
        self.update_idletasks(); r = ctx.root
        self.geometry(f"+{r.winfo_rootx() + (r.winfo_width() - self.winfo_width()) // 2}+{r.winfo_rooty() + (r.winfo_height() - self.winfo_height()) // 3}")
        try: self.grab_set()
        except tk.TclError: pass

    def ok(self):
        vals = {k: v.get().strip() for k, v in self.vars.items()}
        msg = self.check(vals) if self.check else None
        if msg: self.err.config(text=msg); return
        self.result = vals; self.destroy()


class Dialog(TkBase.Toplevel):
    """Small themed message / question / text-input dialog."""
    def __init__(self, ctx, title, msg, parent=None, ask=False, field=None):
        super().__init__(parent or ctx.root); P = ctx.P; self.result = None
        self.title(title); self.configure(bg=P["card"]); self.transient(parent or ctx.root); self.resizable(False, False)
        tk.Label(self, text=title, bg=P["card"], fg=P["text"], font=ctx.f_title, anchor="w").pack(fill="x", padx=22, pady=(18, 4))
        tk.Label(self, text=msg, bg=P["card"], fg=P["muted"], font=ctx.f_body, wraplength=420, justify="left", anchor="w").pack(fill="x", padx=22, pady=(0, 10))
        self.v = tk.StringVar(value=field or "")
        if field is not None:
            e = ttk.Entry(self, textvariable=self.v, style="Modern.TEntry"); e.pack(fill="x", padx=22, ipady=3); e.focus_set(); e.select_range(0, "end")
            e.bind("<Return>", lambda ev: self.ok())
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=22, pady=16)
        Btn(ctx, row, "OK" if not ask else "Yes", self.ok, "primary").pack(side="right", padx=(8, 0))
        if ask or field is not None: Btn(ctx, row, "Cancel" if field is not None else "No", self.destroy, "secondary").pack(side="right")
        self.field = field; self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks(); r = ctx.root
        self.geometry(f"+{r.winfo_rootx() + (r.winfo_width() - self.winfo_width()) // 2}+{r.winfo_rooty() + (r.winfo_height() - self.winfo_height()) // 3}")
        try: self.grab_set()
        except tk.TclError: pass

    def ok(self): self.result = self.v.get() if self.field is not None else True; self.destroy()
