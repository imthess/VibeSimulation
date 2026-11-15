"""Multisim box 3: DC results (node voltages, part currents and power)."""
import tkinter as tk
from tkinter import ttk

from ..engine import components as AC
from ..engine.layout import SchematicBuilder
from ..engine.painter import paint_schematic
from ..engine.solver import is_ground
from ..engine.units import fmt_si
from ....core.render import BAD, LABEL, MUTED, OUTLINE
from ....ui.canvas_renderer import TkRenderer
from ....ui.theme import auto
from ....ui.views.base import View
from ....ui.widgets import Btn
from .ac_panels import BodePanel, PhasorPanel, TransientPanel
from .analysis_panel import AnalysisPanel
from .focus import Focus, FocusPicker
from .more_panels import MonteCarloPanel, NoisePanel, SweepPanel

class ResultsView(View):
    MODES = {"op": "DC operating point", "an": "DC sweep", "ph": "AC: phasors, power", "bo": "AC: frequency response (Bode)", "tr": "Transient (time)", "th": "Thevenin / Norton", "ps": "Parameter sweep", "ts": "Temperature sweep", "mc": "Monte Carlo", "no": "Noise"}
    number, title, hint = None, "Results & analyses", "operating point, sweeps, AC, transient"

    def build(self):
        ctx = self.ctx; b = self.body; b.rowconfigure(1, weight=1); b.columnconfigure(0, weight=1)
        modes = tk.Frame(b, bd=0); modes.grid(row=0, column=0, sticky="ew", pady=(0, 6)); self.modes = modes; self.mode = "op"
        self.mlabel = tk.Label(modes, text="Analysis", font=ctx.f_small); self.mlabel.pack(side="left")
        self.mvar = tk.StringVar(value=self.MODES["op"])
        self.mbox = ttk.Combobox(modes, textvariable=self.mvar, values=list(self.MODES.values()), state="readonly", style="Modern.TCombobox", width=28); self.mbox.pack(side="left", padx=8)
        self.focus = Focus(self.doc); self.picker = FocusPicker(ctx, modes, self.focus); self.picker.pack(side="left", padx=(14, 0)); self.focus.listeners.append(self.focus_changed)
        self.mbox.bind("<<ComboboxSelected>>", lambda e: self.set_mode(next(k for k, v in self.MODES.items() if v == self.mvar.get())))
        box = tk.Frame(b, bd=0); box.grid(row=1, column=0, sticky="nsew"); box.columnconfigure(0, weight=1); box.rowconfigure(0, weight=1); self.box = box
        self.tree = ttk.Treeview(box, show="headings", selectmode="browse", style="Modern.Treeview", columns=("n", "v", "i", "p"))
        for c, t, w in (("n", "Name", 140), ("v", "Voltage", 90), ("i", "Current a→b", 100), ("p", "Power", 90)): self.tree.heading(c, text=t); self.tree.column(c, width=w, anchor="w" if c == "n" else "e")
        sy = ttk.Scrollbar(box, command=self.tree.yview, style="Thin.Vertical.TScrollbar"); self.tree.configure(yscrollcommand=auto(sy))
        self.tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns")
        bot = tk.Frame(b, bd=0); bot.grid(row=2, column=0, sticky="ew", pady=(6, 0)); self.bot = bot
        Btn(ctx, self.tools, "⧉", self.copy, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Copy results").pack(side="right")
        self.status = tk.Label(bot, text="", font=ctx.f_small, anchor="w", justify="left"); self.status.pack(side="left", fill="x", expand=True)
        bot.bind("<Configure>", lambda e: self.status.configure(wraplength=max(100, e.width - 20)))
        self.panel = AnalysisPanel(ctx, self.doc, b, self.status); self.panels = {"an": self.panel, "th": self.panel}
        for k, cls in (("ph", PhasorPanel), ("bo", BodePanel), ("tr", TransientPanel)): self.panels[k] = cls(ctx, self.doc, b, self.status)
        self.panels["ps"] = SweepPanel(ctx, self.doc, b, self.status); self.panels["ts"] = SweepPanel(ctx, self.doc, b, self.status, temperature=True)
        self.panels["mc"] = MonteCarloPanel(ctx, self.doc, b, self.status); self.panels["no"] = NoisePanel(ctx, self.doc, b, self.status)
        for w in {id(p): p for p in self.panels.values()}.values(): w.grid(row=1, column=0, sticky="nsew"); w.grid_remove()
        for w in {id(p): p for p in self.panels.values()}.values(): w.focus = self.focus
        self.rows = []; ctx.themed.append(self._paint); self._paint()

    def set_mode(self, m):
        self.mode = m; self.mvar.set(self.MODES[m])
        if getattr(self, "page", None) is not None: self.page.give_room(m != "op")
        for w in {id(p): p for p in self.panels.values()}.values(): w.grid_remove()
        if m == "op": self.box.grid(); self.hint_status(); return
        self.box.grid_remove(); w = self.panels[m]; w.grid()
        if w is self.panel: w.show("sweep" if m == "an" else "thevenin")
        w.apply_focus() if self.focus.active else w.refresh()
        self.status.config(text={"an": "Sweep one part's value and plot node voltages or part currents (saved in the JSON, written to the .cir as .dc).",
                                 "th": "Replace everything except the chosen part by a voltage source with a series resistor (Thevenin) or a current source in parallel (Norton).",
                                 "ph": "Every voltage and current as a phasor (peak value ∠ angle) at one frequency, with real / reactive power and the power factor.",
                                 "bo": "Magnitude and phase of node voltages, part currents or the impedance seen by a source, for a range of frequencies.",
                                 "tr": "Voltages and currents against time; sources follow their waveforms, capacitors and inductors start from the DC operating point.",
                                 "ps": "Change one part's value or setting step by step and plot what you measure (DC, AC at one frequency, or a transient statistic).",
                                 "ts": "Re-solve the circuit at each temperature. Resistors, capacitors and inductors use tc1 / tc2; diodes and transistors follow the semiconductor model.",
                                 "mc": "Many runs with random part values within their tolerance (set 'tol' in percent on a part, or a default here): spread, percentiles and yield.",
                                 "no": "Thermal, shot and channel noise at an output net across a frequency range, with each part's share. No flicker noise; op-amps are noise-free."}[m])

    def focus_changed(self):
        if self.mode == "op": self.on_doc("changed")
        else: self.panels[self.mode].apply_focus()

    def hint_status(self):
        self.on_doc("changed")

    def _paint(self):
        P = self.ctx.P; self.box.configure(bg=P["card"]); self.modes.configure(bg=P["card"]); self.mlabel.configure(bg=P["card"], fg=P["muted"]); self.picker._paint(); self.bot.configure(bg=P["card"]); self.status.configure(bg=P["card"], fg=P["muted"])
        self.tree.tag_configure("head", background=P["soft"], foreground=P["muted"])

    def on_doc(self, kind):
        if kind != "changed": return
        self.focus.prune(); self.picker.sync()
        if getattr(self, "panels", None) and self.mode != "op": self.panels[self.mode].refresh(); return
        tr = self.tree; tr.delete(*tr.get_children()); self.rows = []; d = self.doc
        if not d.valid: self.status.config(text=d.layout_error or "Fix the circuit to see results."); return
        dg = int(self.ctx.cfg.get("digits", 4))
        def add(row, tag=""): self.rows.append(row); tr.insert("", "end", values=row, tags=(tag,))
        fo = self.focus; fo.prune(); self.picker.sync()
        add(("NODE VOLTAGES", "", "", ""), "head")
        if not fo.active: add(("0 (ground)", "0 V", "", ""))
        for n in d.netlist.nets():
            if fo.allows_net(n): add((n, fmt_si(d.volts.get(n), "V", dg), "", ""))
        add(("PARTS", "", "", ""), "head")
        for p in d.netlist.parts:
            if not fo.allows_part(p.id): continue
            v, i, pw = d.results[p.id]; add((f"{p.id}  ({p.type_name})", fmt_si(v, "V", dg), fmt_si(i, "A", dg), fmt_si(pw, "W", dg)))
            if p.nterm != 2:                                              # operating region, Vbe, Ic, gm ...
                for lab, val in p.info(d.volts, {}): add((f"      {lab}", val, "", ""))
        tot = sum(r[2] for k, r in d.results.items() if r[2] > 0 and fo.allows_part(k))
        warn = f"⚠ Incomplete circuit: {len(d.netlist.floating())} unconnected terminal(s)  ·  " if d.netlist.floating() else ""
        self.status.config(text=f"{warn}DC operating point{"  ·  showing " + fo.label() if fo.active else ""}  ·  total power delivered to {"the chosen parts" if fo.active else "parts"}: {fmt_si(tot, 'W', dg)}")

    def copy(self):
        t = "\n".join("\t".join(r) for r in self.rows); self.ctx.root.clipboard_clear(); self.ctx.root.clipboard_append(t); self.ctx.root.update()
        self.status.config(text="Results copied to the clipboard.")
