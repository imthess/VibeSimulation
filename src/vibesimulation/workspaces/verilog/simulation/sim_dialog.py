"""Simulation settings window (Verilog and SystemVerilog sections): the options a simulator such as Icarus Verilog, Verilator or Vivado asks for,
and the command lines they would become. Applying recompiles the design with the new macros, include folders and warning switches."""
import tkinter as tk
from tkinter import ttk

from ..engine.lintcodes import CODES
from ..project.simsettings import SimSettings, format_defines, parse_defines
from ....ui.widgets import Btn


class SimDialog(tk.Toplevel):
    def __init__(self, ctx, parent, doc, sv=False, modules=()):
        super().__init__(parent); self.ctx, self.doc, self.sv = ctx, doc, sv; P = ctx.P
        self.title("Simulation settings"); self.configure(bg=P["card"]); self.transient(parent.winfo_toplevel()); self.bind("<Escape>", lambda e: self.destroy())
        s = doc.sim_settings; self.v = {k: tk.StringVar(value=str(getattr(s, k))) for k in ("top", "standard", "timescale", "max_time", "cycles", "period", "stimulus")}
        self.dump = tk.BooleanVar(value=s.dump_vcd); self.off = {c: tk.BooleanVar(value=c in s.lint_off) for c in CODES if c != "OTHER"}
        left = tk.Frame(self, bg=P["card"]); left.grid(row=0, column=0, sticky="nsew", padx=(14, 8), pady=12)
        right = tk.Frame(self, bg=P["card"]); right.grid(row=0, column=1, sticky="nsew", padx=(8, 14), pady=12); self.columnconfigure(1, weight=1); self.rowconfigure(0, weight=1)
        def lab(parent, text, r, hint=""):
            tk.Label(parent, text=text, font=ctx.f_small, bg=P["card"], fg=P["muted"], anchor="w").grid(row=r, column=0, sticky="w", pady=3)
            if hint: tk.Label(parent, text=hint, font=ctx.f_small, bg=P["card"], fg=P["muted"], anchor="w").grid(row=r, column=2, sticky="w", padx=6)
        def combo(r, key, values, text, hint="", w=18):
            lab(left, text, r, hint); ttk.Combobox(left, textvariable=self.v[key], values=values, width=w, style="Modern.TCombobox").grid(row=r, column=1, sticky="w", padx=8)
        def entry(r, key, text, hint=""):
            lab(left, text, r, hint); ttk.Entry(left, textvariable=self.v[key], width=20, style="Modern.TEntry").grid(row=r, column=1, sticky="w", padx=8, ipady=1)
        combo(0, "top", ["", *modules], "Top module", "empty = automatic  (iverilog -s)")
        combo(1, "standard", ["auto", "2001", "2005", "2012"], "Language standard", "-g2005 / -g2012", 10)
        entry(2, "timescale", "Timescale", "for the VCD")
        entry(3, "max_time", "Time limit", "time units")
        entry(4, "cycles", "Generated clock cycles", "no testbench")
        entry(5, "period", "Clock period", "time units")
        combo(6, "stimulus", ["random", "count"], "Generated inputs", "", 10)
        ttk.Checkbutton(left, text="Write dump.vcd after a run  ($dumpfile / $dumpvars)", variable=self.dump).grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 2))
        tk.Label(left, text="Defines  (-D)  one per line: NAME or NAME=value", font=ctx.f_small, bg=P["card"], fg=P["muted"]).grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.defs = self._text(left, 9, format_defines(s.defines), 3)
        tk.Label(left, text="Include folders  (-I)  one per line", font=ctx.f_small, bg=P["card"], fg=P["muted"]).grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.incs = self._text(left, 11, "\n".join(s.incdirs), 2)
        tk.Label(left, text="Warnings to switch off  (-Wno-CODE)", font=ctx.f_small, bg=P["card"], fg=P["muted"]).grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 2))
        ck = tk.Frame(left, bg=P["card"]); ck.grid(row=13, column=0, columnspan=3, sticky="w")
        for i, c in enumerate(self.off): ttk.Checkbutton(ck, text=c, variable=self.off[c]).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 10))
        tk.Label(right, text="The same run as command lines", font=ctx.f_bold, bg=P["card"], fg=P["text"]).pack(anchor="w")
        self.cmd = tk.Text(right, width=48, height=20, wrap="word", font=ctx.f_mono, bd=0, highlightthickness=1, bg=P["field"], fg=P["text"], highlightbackground=P["border"]); self.cmd.pack(fill="both", expand=True, pady=6)
        row = tk.Frame(right, bg=P["card"]); row.pack(fill="x")
        Btn(ctx, row, "Update", self.preview, "secondary", pady=3, padx=12, font=ctx.f_small).pack(side="left")
        Btn(ctx, row, "Copy", self.copy, "ghost", pady=3, padx=10, font=ctx.f_small).pack(side="left", padx=6)
        Btn(ctx, row, "Apply", self.apply, "primary", pady=3, padx=16, font=ctx.f_small).pack(side="right")
        Btn(ctx, row, "Cancel", self.destroy, "ghost", pady=3, padx=12, font=ctx.f_small).pack(side="right", padx=6)
        self.msg = tk.Label(right, text="", font=ctx.f_small, bg=P["card"], fg=P["bad"], anchor="w", justify="left"); self.msg.pack(fill="x")
        self.preview(); self.update_idletasks()
        x = parent.winfo_toplevel().winfo_rootx() + max(0, (parent.winfo_toplevel().winfo_width() - self.winfo_reqwidth()) // 2); y = parent.winfo_toplevel().winfo_rooty() + 40
        self.geometry(f"+{x}+{y}")

    def _text(self, parent, r, value, h):
        P = self.ctx.P; t = tk.Text(parent, width=40, height=h, font=self.ctx.f_mono, bd=0, highlightthickness=1, bg=P["field"], fg=P["text"], highlightbackground=P["border"], insertbackground=P["text"])
        t.grid(row=r, column=0, columnspan=3, sticky="ew"); t.insert("1.0", value); return t

    def read(self):
        """The dialog's fields as a SimSettings (ValueError names the field that is wrong)."""
        v = {k: x.get().strip() for k, x in self.v.items()}
        try:
            n = {k: int(v[k]) for k in ("max_time", "cycles", "period")}
        except ValueError: raise ValueError("time limit, cycles and period must be whole numbers")
        s = SimSettings(top=v["top"], standard=v["standard"], timescale=v["timescale"] or "1ns/1ps", stimulus=v["stimulus"], dump_vcd=self.dump.get(), **n,
                        defines=parse_defines(self.defs.get("1.0", "end")), incdirs=[l.strip() for l in self.incs.get("1.0", "end").split("\n") if l.strip()],
                        lint_off=[c for c, x in self.off.items() if x.get()])
        bad = s.problems()
        if bad: raise ValueError(bad[0])
        return s

    def preview(self):
        try: s = self.read()
        except ValueError as e: self.msg.config(text=str(e)); return None
        self.msg.config(text=""); self.cmd.delete("1.0", "end"); self.cmd.insert("1.0", s.commands_text(files=("design.sv",) if self.sv else ("design.v",), sv=self.sv, tb_top="tb")); return s

    def copy(self):
        self.clipboard_clear(); self.clipboard_append(self.cmd.get("1.0", "end").strip()); self.msg.config(text="Copied.", fg=self.ctx.P["muted"])

    def apply(self):
        s = self.preview()
        if s is None: return
        self.doc.apply_settings(s); self.destroy()
