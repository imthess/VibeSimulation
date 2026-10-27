"""Multisim analyses: parameter sweep, temperature sweep, Monte Carlo, noise.

The first three share a "what to measure" strip (DC / AC / transient plus the probes); noise has its own."""
import tkinter as tk
from tkinter import ttk

from ...analog import components as C
from ...analog import measure as M
from ...analog import montecarlo as MC
from ...analog import noise as NZ
from ...analog import sweeps as SW
from ...analog.units import fmt_si, parse_value
from ..widgets import Btn
from .ac_panels import Base
from .plot import COLORS, Plot


class SpecBase(Base):
    """Panel with a measurement strip: kind, ac frequency / transient stop and statistic, probe list."""

    def spec_strip(self, parent):
        t = self.frame(parent); self.field(t, "kind", "measure", "dc", 5, ["dc", "ac", "tran"]); self.field(t, "f", "f", "1k", 6); self.field(t, "stop", "stop", "10m", 6)
        self.field(t, "stat", "stat", "final", 6, list(M.STATS)); self.probes = self.probe_list(t); self.probes.pack(side="left", fill="x", expand=True, padx=4)
        self.vars["kind"].trace_add("write", lambda *a: None); return t

    def spec(self):
        pr = self.selected(self.probes)
        if not pr: raise ValueError("Pick at least one probe in the list.")
        k = self.get("kind"); s = {"kind": k, "probes": pr}
        if k == "ac": s["f"] = self.get("f")
        if k == "tran": s.update(stop=self.get("stop"), steps=400, stat=self.get("stat"))
        return s

    def fill(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return False
        self.fill_probes(self.probes, [f"V({n})" for n in nl.nets()] + [f"I({p.id})" for p in nl.parts])
        if not self.selected(self.probes):
            nets = [i for i, t in enumerate(self.probes.get(0, "end")) if t.startswith("V(")]
            if nets: self.probes.selection_set(nets[-1])
        return True

    def pretty(self, label):
        return label

    def text_table(self, parent, cols, widths):
        box = self.frame(parent); box.columnconfigure(0, weight=1); box.rowconfigure(0, weight=1)
        tr = ttk.Treeview(box, show="headings", style="Modern.Treeview", columns=[c for c, _ in cols], height=5)
        for (c, t), w in zip(cols, widths): tr.heading(c, text=t); tr.column(c, width=w, minwidth=40, anchor="e")
        sy = ttk.Scrollbar(box, command=tr.yview, style="Thin.Vertical.TScrollbar"); tr.configure(yscrollcommand=sy.set); tr.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns")
        return box, tr


class SweepPanel(SpecBase):
    """KEY 'psweep' (one part's value or setting) or 'tsweep' (temperature)."""
    def __init__(self, ctx, doc, master, status, temperature=False):
        self._combos = {}; self.temp = temperature; self.KEY = "tsweep" if temperature else "psweep"
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(4, weight=1)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        if temperature: self.field(t, "from", "from °C", "-40", 6); self.field(t, "to", "to °C", "125", 6)
        else:
            self.field(t, "part", "part", "", 8, []); self.field(t, "param", "setting", "value", 8, []); self.field(t, "from", "from", "100", 7); self.field(t, "to", "to", "10k", 7)
            self.vars["part"].trace_add("write", lambda *a: self.fill_params())
        self.field(t, "n", "n", "21", 4)
        if not temperature: self.field(t, "log", "", "log", 5, ["log", "lin"])
        Btn(ctx, t, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left", padx=6)
        Btn(ctx, t, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).pack(side="left")
        self.spec_strip(self).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(100, e.width - 10)))
        self.pl = Plot(self, ctx); self.pl.grid(row=4, column=0, sticky="nsew", pady=(4, 2))
        self._paint()

    def field(self, parent, name, text, init, w=7, choices=None):
        e = super().field(parent, name, text, init, w, choices)
        if choices is not None and name in ("part", "param"): self._combos[name] = e
        return e

    def fill_params(self):
        nl = self.doc.netlist
        if nl is None or "param" not in self._combos: return
        ps = [k for pid, k in SW.sweepable(nl) if pid == self.get("part")]
        self._combos["param"]["values"] = ps
        if ps and self.get("param") not in ps: self.vars["param"].set(ps[0])

    def refresh(self):
        if not self.fill(): return
        nl = self.doc.netlist
        if not self.temp and "part" in self._combos:
            ids = sorted({pid for pid, _ in SW.sweepable(nl)}); self._combos["part"]["values"] = ids
            if self.get("part") not in ids and ids: self.vars["part"].set(ids[0])
            self.fill_params()
        sv = self.saved()
        if sv and not self._busy:
            for k in ("part", "param", "from", "to", "n", "log"):
                if k in sv and k in self.vars: self.vars[k].set(str(sv[k]))
        self.plot()

    def run(self):
        if not self.ready(): return
        nl = self.doc.netlist
        try:
            spec = self.spec(); n = int(self.get("n")); a, b = parse_value(self.get("from")), parse_value(self.get("to"))
            if self.temp: xs = SW.values(a, b, n); cfg = {"from": self.get("from"), "to": self.get("to"), "n": n}; r = SW.temperature_sweep(nl, xs, spec)
            else:
                cfg = {"part": self.get("part"), "param": self.get("param"), "from": self.get("from"), "to": self.get("to"), "n": n, "log": self.get("log")}
                xs = SW.values(a, b, n, self.get("log") == "log"); r = SW.parameter_sweep(nl, cfg["part"], cfg["param"], xs, spec)
        except ValueError as ex: self.status.config(text=str(ex)); return
        self.data = r; cfg["spec"] = spec; self.save(cfg); self.plot()
        self.note.config(text=("" if not r["failed"] else f"{r['failed']} of {len(xs)} points could not be solved and are left out of the plot."))
        self.status.config(text=f"{'Temperature' if self.temp else 'Parameter'} sweep: {len(xs)} points of {r['label']}.")

    def plot(self):
        if not hasattr(self, "pl"): return
        d = self.data
        if not d: self.pl.clear("Choose what to measure, then press Run."); return
        ser = [(k, v) for k, v in d["series"].items()]
        self.pl.show(d["x"], ser, "°C" if self.temp else "", "", not self.temp and self.get("log") == "log", d["label"], legend=True)

    def csv(self):
        d = self.data
        if not d: self.ctx.say("Sweep", "Run a sweep first."); return
        rows = [[d["label"]] + list(d["series"])] + [[x] + ["" if d["series"][k][i] is None else d["series"][k][i] for k in d["series"]] for i, x in enumerate(d["x"])]
        self.save_csv("sweep.csv", rows)


class MonteCarloPanel(SpecBase):
    KEY = "mc"

    def __init__(self, ctx, doc, master, status):
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(4, weight=1)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        self.field(t, "runs", "runs", "200", 5); self.field(t, "tol", "default tol %", "5", 4); self.field(t, "dist", "", "gauss", 7, ["gauss", "uniform"]); self.field(t, "seed", "seed", "1", 5)
        self.field(t, "lo", "pass ≥", "", 6); self.field(t, "hi", "≤", "", 6)
        Btn(ctx, t, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left", padx=6)
        Btn(ctx, t, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).pack(side="left")
        self.spec_strip(self).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.probes.bind("<<ListboxSelect>>", lambda e: self.plot())
        box, self.tree = self.text_table(self, [("n", "Probe"), ("mean", "Mean"), ("std", "Std dev"), ("min", "Min"), ("max", "Max"), ("p5", "5 %"), ("p95", "95 %"), ("y", "Yield")], [90, 82, 82, 82, 82, 82, 82, 60])
        self.tree.column("n", anchor="w"); box.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(100, e.width - 10)))
        self.pl = Plot(self, ctx); self.pl.grid(row=4, column=0, sticky="nsew", pady=(4, 2)); self._paint()

    def refresh(self):
        self.fill()
        sv = self.saved()
        if sv and not self._busy:
            for k in ("runs", "tol", "dist", "seed", "lo", "hi"):
                if k in sv: self.vars[k].set(str(sv[k]))
        self.plot()

    def run(self):
        if not self.ready(): return
        try:
            spec = self.spec(); runs = int(self.get("runs")); tol = parse_value(self.get("tol") or "0") / 100.0
            lo = parse_value(self.get("lo")) if self.get("lo") else None; hi = parse_value(self.get("hi")) if self.get("hi") else None
            seed = int(self.get("seed")) if self.get("seed") else None
            self.status.config(text="Running…"); self.update_idletasks()
            self.data = MC.run(self.doc.netlist, spec, runs, tol, self.get("dist"), seed, (lo, hi), None)
        except ValueError as ex: self.status.config(text=str(ex)); return
        self.save({k: self.get(k) for k in ("runs", "tol", "dist", "seed", "lo", "hi")}); self.table(); self.plot()
        d = self.data; self.status.config(text=f"Monte Carlo: {runs} runs" + (f", {d['failed']} could not be solved" if d["failed"] else "") + f"; tolerance applied to {', '.join(d['tolerant'])}.")

    def table(self):
        self.tree.delete(*self.tree.get_children()); d = self.data
        for k, s in d["stats"].items():
            f = lambda v: "" if v is None else fmt_si(v, "", 4)
            self.tree.insert("", "end", values=(k, f(s["mean"]), f(s["std"]), f(s["min"]), f(s["max"]), f(s["p5"]), f(s["p95"]), "" if "yield" not in s else f"{100 * s['yield']:.1f} %"))

    def plot(self):
        if not hasattr(self, "pl"): return
        d = self.data
        if not d: self.pl.clear("Give parts a tolerance (right-click > Edit: tol), choose what to measure and press Run."); return
        sel = self.selected(self.probes); keys = [k for k in d["stats"] if any(k.endswith(s) or s in k for s in sel)] or list(d["stats"])[:1]
        k = keys[0]; h = d["stats"][k]["hist"]; e = h["edges"]; xs = [(e[i] + e[i + 1]) / 2 for i in range(len(e) - 1)]
        self.pl.show(xs, [(f"{k}: runs per bin", [float(c) for c in h["counts"]])], "", "", False, f"Distribution of {k} (nominal {fmt_si(d['nominal'].get(k), '', 4) if d['nominal'].get(k) is not None else '—'})", legend=False)

    def csv(self):
        d = self.data
        if not d: self.ctx.say("Monte Carlo", "Run it first."); return
        ks = list(d["samples"]); n = max(len(v) for v in d["samples"].values())
        self.save_csv("monte_carlo.csv", [["run"] + ks] + [[i + 1] + [d["samples"][k][i] if i < len(d["samples"][k]) else "" for k in ks] for i in range(n)])


class NoisePanel(Base):
    KEY = "noise"

    def __init__(self, ctx, doc, master, status):
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(4, weight=1)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        self.field(t, "out", "output", "", 7, []); self.field(t, "ref", "ref", "0", 6); self.field(t, "src", "input", "", 6, []); self.field(t, "from", "from", "10", 6); self.field(t, "to", "to", "100k", 6); self.field(t, "n", "n", "61", 4)
        Btn(ctx, t, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left", padx=6)
        Btn(ctx, t, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).pack(side="left")
        self.combos = [w for w in t.winfo_children() if isinstance(w, ttk.Combobox)]
        b, self.tree = SpecBase.text_table(self, self, [("p", "Part"), ("k", "Kind"), ("v", "RMS at output")], [80, 140, 120]); self.tree.column("p", anchor="w"); self.tree.column("k", anchor="w"); b.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(100, e.width - 10)))
        self.pl = Plot(self, ctx); self.pl.grid(row=4, column=0, sticky="nsew", pady=(4, 2)); self._paint()

    def refresh(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return
        nets = list(nl.nets()); srcs = [""] + [p.id for p in nl.parts if isinstance(p, (C.VoltageSource, C.CurrentSource))]
        self.combos[0]["values"] = nets; self.combos[1]["values"] = srcs
        if self.get("out") not in nets and nets: self.vars["out"].set(nets[-1])
        sv = self.saved()
        if sv and not self._busy:
            for k in ("out", "ref", "src", "from", "to", "n"):
                if k in sv: self.vars[k].set(str(sv[k]))
        self.plot()

    def run(self):
        if not self.ready(): return
        try:
            cfg = {k: self.get(k) for k in ("out", "ref", "src", "from", "to", "n")}
            self.data = NZ.run(self.doc.netlist, cfg["out"], cfg["from"], cfg["to"], int(cfg["n"]), cfg["ref"] or "0", cfg["src"] or None)
        except ValueError as ex: self.data = None; self.status.config(text=str(ex)); self.plot(); return
        self.save(cfg); d = self.data; self.tree.delete(*self.tree.get_children())
        for pid, v in sorted(d["by_part_rms"].items(), key=lambda kv: -kv[1]): self.tree.insert("", "end", values=(pid, "+".join(d["kinds"][pid]), fmt_si(v, "V", 4)))
        txt = f"Total output noise {fmt_si(d['total_rms'], 'V', 4)} RMS from {cfg['from']} Hz to {cfg['to']} Hz."
        if "inoise" in d: vals = [v for v in d["inoise"] if v is not None]; txt += f" Input-referred noise at {cfg['src']}: {fmt_si(sum(vals) / len(vals), '', 3)}/√Hz on average." if vals else ""
        self.note.config(text=txt + " Thermal, shot and channel noise only (no flicker noise; op-amps are noise-free)."); self.plot()
        self.status.config(text="Noise analysis done.")

    def plot(self):
        if not hasattr(self, "pl"): return
        d = self.data
        if not d: self.pl.clear("Pick the output net and a frequency range, then press Run."); return
        ser = [("output (V/√Hz)", d["onoise"])] + ([("input-referred", d["inoise"])] if "inoise" in d else [])
        self.pl.show(d["f"], ser, "Hz", "", True, "Noise spectral density", legend=True)

    def csv(self):
        d = self.data
        if not d: self.ctx.say("Noise", "Run the analysis first."); return
        self.save_csv("noise.csv", [["f (Hz)", "output (V/rtHz)"] + (["input-referred", "gain"] if "inoise" in d else [])] + [[f, d["onoise"][i]] + ([d["inoise"][i], d["gain"][i]] if "inoise" in d else []) for i, f in enumerate(d["f"])])
