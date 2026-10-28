"""Multisim analyses of AC circuits: frequency response (Bode), phasors at one frequency (with power and a phasor diagram) and transient."""
import cmath
import csv
import io
import math
import tkinter as tk
from tkinter import ttk

from ...analog import ac as AC
from ...analog import components as C
from ...analog import transient as TR
from ...analog.solver import SolveError as SolveError_
from ...analog.units import fmt_si, parse_value
from ..theme import auto
from ..widgets import Btn
from .plot import COLORS, Plot


def fmt_ph(z, unit, digits=4):
    """'1.414 V ∠ -45°'"""
    if z is None: return "—"
    if abs(z) < 1e-15: return f"0 {unit}"
    return f"{fmt_si(abs(z), unit, digits)} ∠ {math.degrees(cmath.phase(z)):.4g}°"


class Base(tk.Frame):
    """Shared bits: themed frames / labels, the probe list, saving the settings into the circuit JSON."""
    KEY = ""

    def __init__(self, ctx, doc, master, status):
        super().__init__(master, bd=0); self.ctx, self.doc, self.status = ctx, doc, status
        self.frames, self.labels, self.vars, self._busy, self.data = [self], [], {}, False, None
        ctx.themed.append(self._paint)

    def frame(self, parent=None):
        f = tk.Frame(parent or self, bd=0); self.frames.append(f); return f

    def lab(self, parent, text):
        l = tk.Label(parent, text=text, font=self.ctx.f_small); self.labels.append(l); l.pack(side="left", padx=(6, 2)); return l

    def field(self, parent, name, text, init, w=7, choices=None):
        self.lab(parent, text); self.vars[name] = v = tk.StringVar(value=str(init))
        if choices is not None: e = ttk.Combobox(parent, textvariable=v, values=choices, state="readonly" if choices else "normal", style="Modern.TCombobox", width=w)
        else: e = ttk.Entry(parent, textvariable=v, style="Modern.TEntry", width=w); e.bind("<Return>", lambda ev: self.run())
        e.pack(side="left", ipady=1); return e

    def get(self, k): return self.vars[k].get().strip()

    def probe_list(self, parent, height=2):
        lb = tk.Listbox(parent, selectmode="extended", height=height, exportselection=False, bd=0, highlightthickness=1, font=self.ctx.f_small)
        lb.bind("<<ListboxSelect>>", lambda e: self.plot()); self.lists = getattr(self, "lists", []) + [lb]; return lb

    def fill_probes(self, lb, names):
        if list(lb.get(0, "end")) == names: return
        keep = {lb.get(i) for i in lb.curselection()}; lb.delete(0, "end")
        for i, t in enumerate(names):
            lb.insert("end", t)
            if t in keep: lb.selection_set(i)

    def selected(self, lb): return [lb.get(i) for i in lb.curselection()]

    def save(self, cfg):
        self._busy = True
        try: self.doc.edit(lambda nl: nl.analysis.__setitem__(self.KEY, cfg))
        finally: self._busy = False
        return self.doc.netlist is not None and self.doc.valid

    def saved(self):
        nl = self.doc.netlist; return ((nl.analysis or {}).get(self.KEY) or {}) if nl else {}

    def ready(self):
        if self.doc.netlist is None or not self.doc.valid: self.status.config(text="Fix the circuit first (see the JSON box)."); return False
        return True

    def _paint(self):
        P = self.ctx.P
        for w in self.frames: w.configure(bg=P["card"])
        for l in self.labels: l.configure(bg=P["card"], fg=P["muted"])
        for lb in getattr(self, "lists", []): lb.configure(bg=P["field"], fg=P["text"], selectbackground=P["accent"], selectforeground=P["accent_fg"], highlightbackground=P["border"], highlightcolor=P["accent"])
        for n in ("note", "res"):
            w = getattr(self, n, None)
            if w is not None: w.configure(bg=P["card"], fg=P["text"])
        self.plot()

    def plot(self): pass
    def refresh(self): pass
    def save_csv(self, name, rows):
        out = io.StringIO(); w = csv.writer(out); w.writerows(rows)
        from ..actions import FileActions
        p = FileActions(self.ctx, self.doc, None)._save("Save table", ".csv", name, out.getvalue())
        if p: self.ctx.say("Saved", p)


class BodePanel(Base):
    KEY = "ac"

    def __init__(self, ctx, doc, master, status):
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(3, weight=1); self.rowconfigure(4, weight=1)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        self.field(t, "from", "from", "10", 6); self.field(t, "to", "to", "100k", 6); self.field(t, "points", "n", "81", 4); self.field(t, "scale", "", "log", 5, ["log", "lin"])
        t2 = self.frame(); t2.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        Btn(ctx, t2, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left")
        Btn(ctx, t2, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).pack(side="left", padx=4)
        self.field(t2, "mag", "gain", "dB", 6, ["dB", "linear"])
        self.probes = self.probe_list(t2); self.probes.pack(side="left", fill="x", expand=True, padx=4)
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(100, e.width - 10)))
        self.pm = Plot(self, ctx); self.pp = Plot(self, ctx); self.pm.grid(row=3, column=0, sticky="nsew", pady=(4, 2)); self.pp.grid(row=4, column=0, sticky="nsew", pady=(2, 2))
        self._paint()

    def refresh(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return
        self.fill_probes(self.probes, [f"V({n})" for n in nl.nets()] + [f"I({p.id})" for p in nl.parts] + [f"I({p.id}.{sh})" for p in nl.parts if p.nterm != 2 for sh in p.short] + [f"Z({p.id})" for p in nl.parts if isinstance(p, C.VoltageSource)])
        sv = self.saved()
        if sv and not self._busy:
            for k in ("from", "to", "points", "scale"):
                if k in sv: self.vars[k].set(str(sv[k]))
        if not self.data and not self.selected(self.probes):
            nets = [i for i, t in enumerate(self.probes.get(0, "end")) if t.startswith("V(")]
            if nets: self.probes.selection_set(nets[-1])
        if not any(isinstance(p, C.Waveform) and p.is_ac() for p in nl.parts): self.status.config(text="Give a source an AC amplitude first: right-click it > Edit source.")

    def run(self):
        if not self.ready(): return
        try:
            cfg = {"from": self.get("from"), "to": self.get("to"), "points": int(self.get("points")), "scale": self.get("scale") or "log"}
            f1, f2 = parse_value(cfg["from"]), parse_value(cfg["to"])
            if not 2 <= cfg["points"] <= 2000: raise ValueError("points must be between 2 and 2000")
            if f1 <= 0 or f2 <= f1: raise ValueError("the range must satisfy 0 < from < to")
        except ValueError as ex: self.status.config(text=f"Frequency sweep: {ex}"); return
        if not self.save(cfg): return
        try: self.data = AC.sweep(self.doc.netlist, f1, f2, cfg["points"], cfg["scale"] == "log")
        except ValueError as ex: self.data = None; self.status.config(text=str(ex)); self.plot(); return
        self.refresh(); self.plot()
        self.status.config(text=f"Frequency response from {cfg['from']} Hz to {cfg['to']} Hz ({cfg['points']} points). Magnitudes are peak values; 1 V source → the plot is the gain.")

    def evaluator(self, t):
        """f -> the probe's phasor, for refining the peak and the -3 dB points between the sweep's samples."""
        try: prep = AC.prepare(self.doc.netlist)
        except ValueError: return None
        k = t[2:-1]; tm = {f"{p.id}.{sh}": (p.id, j) for p in prep[0] if p.nterm != 2 for j, sh in enumerate(p.short)}
        def fn(f):
            pt = AC.point(prep, f)
            if t[0] == "V": return pt["V"][k]
            if k in tm: return pt["parts"][tm[k][0] + "#t"][tm[k][1]]
            r = pt["parts"][k]
            return r["i"] if t[0] == "I" else (-r["v"] / r["i"] if abs(r["i"]) > 1e-30 else None)
        return fn

    def curves(self):
        d = self.data; out = []
        if not d: return out
        for t in self.selected(self.probes):
            k = t[2:-1]; zs = d["V"].get(k) if t[0] == "V" else (d["I"].get(k) if t[0] == "I" else d["Z"].get(k))
            if zs: out.append((t, zs))
        return out

    def plot(self):
        if not hasattr(self, "pp"): return
        cv = self.curves()
        if not cv:
            m = "Set a range, press Run, then pick what to plot." if not self.data else "Pick something to plot."
            self.pm.clear(m); self.pp.clear(""); self.note.config(text=""); return
        f = self.data["f"]; db = self.get("mag") == "dB"
        mags = [(t, [(AC.db(z) if db else abs(z)) if z is not None else None for z in zs]) for t, zs in cv]
        units = {("Ω" if t[0] == "Z" else "A" if t[0] == "I" else "V") for t, _ in cv}
        self.pm.show(f, mags, "Hz", "dB" if db else (units.pop() if len(units) == 1 else ""), self.data["log"], "Magnitude" + (" (dB re 1 unit)" if db else ""), legend=True)
        self.pp.show(f, [(t, AC.unwrap_deg(zs)) for t, zs in cv], "Hz", "°", self.data["log"], "Phase", legend=False)
        t, zs = cv[0]; m = AC.metrics(f, zs, self.evaluator(t)); dg = int(self.ctx.cfg.get("digits", 4)); hz = lambda x: fmt_si(x, "Hz", dg)
        txt = f"{t}: {m['kind']}; largest magnitude {fmt_si(m['peak'], '', dg)} ({AC.db(m['peak']):.3g} dB) at {hz(m['f_peak'])}"
        if m["kind"] == "low-pass": txt += f"; −3 dB at {hz(m['f_high'])}"
        elif m["kind"] == "high-pass": txt += f"; −3 dB at {hz(m['f_low'])}"
        elif m["kind"] == "band-pass": txt += f"; centre {hz(m['f0'])}, −3 dB at {hz(m['f_low'])} and {hz(m['f_high'])}, bandwidth {hz(m['bw'])}, Q = {m['q']:.4g}"
        if m["rolloff_db_per_dec"] is not None: txt += f"; edge slope {m['rolloff_db_per_dec']:.3g} dB/decade"
        self.note.config(text=txt + ("   (several curves: this line describes the first)" if len(cv) > 1 else ""))

    def csv(self):
        cv = self.curves()
        if not cv: self.ctx.say("Frequency response", "Run a sweep and pick what to plot first."); return
        head = ["f (Hz)"] + [h for t, _ in cv for h in (f"{t} magnitude", f"{t} phase (deg)")]; rows = [head]
        ph = [AC.unwrap_deg(zs) for _, zs in cv]
        for k, f in enumerate(self.data["f"]): rows.append([f] + [x for j, (_, zs) in enumerate(cv) for x in ("" if zs[k] is None else abs(zs[k]), "" if ph[j][k] is None else ph[j][k])])
        self.save_csv("frequency_response.csv", rows)


class PhasorPanel(Base):
    KEY = "ac"

    def __init__(self, ctx, doc, master, status):
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(2, weight=3); self.rowconfigure(4, weight=2)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        self.field(t, "f", "frequency", "1k", 8)
        Btn(ctx, t, "Solve", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left", padx=6)
        self.field(t, "rms", "show", "peak", 5, ["peak", "RMS"])
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        box = self.frame(); box.grid(row=2, column=0, sticky="nsew", pady=4); box.columnconfigure(0, weight=1); box.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, show="headings", selectmode="extended", style="Modern.Treeview", columns=("n", "v", "i", "p", "q"), height=6)
        for c, tx, w in (("n", "Name", 56), ("v", "Voltage", 170), ("i", "Current a→b", 170), ("p", "P", 84), ("q", "Q", 96)): self.tree.heading(c, text=tx); self.tree.column(c, width=w, minwidth=40, anchor="w" if c == "n" else "e", stretch=c in ("v", "i"))
        sy = ttk.Scrollbar(box, command=self.tree.yview, style="Thin.Vertical.TScrollbar"); self.tree.configure(yscrollcommand=auto(sy)); self.tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.plot())
        self.res = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.res.grid(row=3, column=0, sticky="ew")
        self.bind("<Configure>", lambda e: (self.note.configure(wraplength=max(100, e.width - 10)), self.res.configure(wraplength=max(100, e.width - 10))))
        self.dia = Plot(self, ctx); self.dia.grid(row=4, column=0, sticky="nsew", pady=(2, 0)); self.rows = {}; self.pt = None
        self._paint()

    def refresh(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return
        if not self.pt:
            f = next((p.freq() for p in nl.parts if isinstance(p, C.Waveform) and p.is_ac()), None)
            if f: self.vars["f"].set(f"{f:g}")

    def run(self):
        if not self.ready(): return
        try:
            f = parse_value(self.get("f"))
            if f <= 0: raise ValueError("the frequency must be greater than 0")
            prep = AC.prepare(self.doc.netlist); self.pt = AC.point(prep, f); pw = AC.power_summary(prep, self.pt)
        except ValueError as ex: self.status.config(text=str(ex)); return
        self.fill(pw, prep)

    def fill(self, pw, prep):
        dg = int(self.ctx.cfg.get("digits", 4)); k = 1 / math.sqrt(2) if self.get("rms") == "RMS" else 1.0; tr = self.tree; tr.delete(*tr.get_children()); self.rows = {}
        def add(name, v=None, i=None, s=None, head=False, key=None):
            iid = tr.insert("", "end", values=(name, "" if v is None else fmt_ph(v * k, "V", dg), "" if i is None else fmt_ph(i * k, "A", dg),
                                              "" if s is None else fmt_si(s.real, "W", dg), "" if s is None else fmt_si(s.imag, "var", dg)), tags=("head",) if head else ())
            if key: self.rows[iid] = (key, v, i)
        add("NODES", head=True)
        for n in sorted(self.pt["V"]):
            if n != "0": add(n, v=self.pt["V"][n], key=f"V({n})")
        add("PARTS", head=True)
        for p in self.doc.netlist.parts:
            r = self.pt["parts"][p.id]; add(f"{p.id}", v=r["v"], i=r["i"], s=r["s"], key=p.id)
            if p.nterm != 2:
                for j, sh in enumerate(p.short): add(f"   {p.id}.{sh}", i=self.pt["parts"][p.id + "#t"][j], key=f"{p.id}.{sh}")
        tr.tag_configure("head", background=self.ctx.P["soft"], foreground=self.ctx.P["muted"])
        f = self.pt["f"]; txt = f"At {fmt_si(f, 'Hz', dg)} the sources deliver P = {fmt_si(pw['P'], 'W', dg)}, Q = {fmt_si(pw['Q'], 'var', dg)}, S = {fmt_si(pw['S'], 'VA', dg)}"
        if pw["pf"] is not None: txt += f", power factor {pw['pf']:.4g} ({'leading' if pw['leading'] else 'lagging'})" if abs(pw["Q"]) > 1e-3 * max(pw["S"], 1e-30) else f", power factor {pw['pf']:.4g}"
        zs = [(p.id, self.pt["parts"][p.id]) for p in self.doc.netlist.parts if isinstance(p, C.VoltageSource) and p.is_ac()]
        if zs:
            r = zs[0][1]; z = -r["v"] / r["i"] if abs(r["i"]) > 1e-30 else None
            if z is not None: txt += f".   Impedance seen by {zs[0][0]}: {fmt_ph(z, 'Ω', dg)} ({fmt_si(z.real, 'Ω', dg)} {'+' if z.imag >= 0 else '−'} j{fmt_si(abs(z.imag), 'Ω', dg)})"
        self.res.config(text=txt); self.status.config(text="Select rows to draw their phasors. Magnitudes are " + ("RMS." if k != 1 else "peak (RMS = peak / √2)."))
        self.plot()

    def plot(self):
        if not hasattr(self, "dia"): return
        c = self.dia; c.delete("all"); c.configure(bg=self.ctx.P["canvas"]); W, H = c.winfo_width(), c.winfo_height(); P = self.ctx.P
        sel = [self.rows[i] for i in self.tree.selection() if i in self.rows]
        if not sel or W < 60 or H < 60:
            if W > 60 and H > 30: c.create_text(W / 2, H / 2, text="Phasor diagram: select rows above." if self.pt else "Press Solve.", fill=P["muted"], font=self.ctx.f_small)
            return
        vecs = []
        for j, (name, v, i) in enumerate(sel):
            if v is not None and abs(v) > 1e-15: vecs.append((f"V {name}" if not name.startswith("V(") else name, v, "V"))
            if i is not None and abs(i) > 1e-15: vecs.append((f"I {name}", i, "A"))
        if not vecs: return
        mv = max([abs(z) for _, z, u in vecs if u == "V"] or [1.0]); mi = max([abs(z) for _, z, u in vecs if u == "A"] or [1.0])
        cx, cy, R = W / 2, H / 2, min(W, H) / 2 - 22
        c.create_line(8, cy, W - 8, cy, fill=P["border"]); c.create_line(cx, 6, cx, H - 6, fill=P["border"]); c.create_oval(cx - R, cy - R, cx + R, cy + R, outline=P["border"])
        for j, (nm, z, u) in enumerate(vecs):
            col = COLORS[j % len(COLORS)]; L = abs(z) / (mv if u == "V" else mi) * R; a = cmath.phase(z); ex, ey = cx + L * math.cos(a), cy - L * math.sin(a)
            c.create_line(cx, cy, ex, ey, fill=col, width=2, arrow="last", dash=(4, 3) if u == "A" else None)
            c.create_text(ex + 4 * math.cos(a), ey - 4 * math.sin(a), text=nm, fill=col, font=self.ctx.f_small, anchor="sw" if math.cos(a) >= 0 else "se")
        if any(u == "A" for _, _, u in vecs): c.create_text(6, 4, text=f"dashed: currents, scaled so the largest ({fmt_si(mi, 'A', 3)}) = the largest voltage ({fmt_si(mv, 'V', 3)})", anchor="nw", fill=P["muted"], font=self.ctx.f_small)


class TransientPanel(Base):
    KEY = "tran"

    def __init__(self, ctx, doc, master, status):
        super().__init__(ctx, doc, master, status); self.columnconfigure(0, weight=1); self.rowconfigure(3, weight=1)
        t = self.frame(); t.grid(row=0, column=0, sticky="ew")
        self.field(t, "stop", "stop time", "10m", 7); self.field(t, "steps", "steps", "1000", 6); self.field(t, "method", "", "trap", 6, ["trap", "euler"])
        t2 = self.frame(); t2.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        Btn(ctx, t2, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left")
        Btn(ctx, t2, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).pack(side="left", padx=4)
        self.field(t2, "from", "stats from", "0", 6)
        self.probes = self.probe_list(t2); self.probes.pack(side="left", fill="x", expand=True, padx=4)
        self.note = tk.Label(self, text="", font=ctx.f_small, anchor="w", justify="left"); self.note.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(100, e.width - 10)))
        self.pl = Plot(self, ctx); self.pl.grid(row=3, column=0, sticky="nsew", pady=4)
        self._paint()

    def refresh(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return
        self.fill_probes(self.probes, [f"V({n})" for n in nl.nets()] + [f"I({p.id})" for p in nl.parts] + [f"I({p.id}.{sh})" for p in nl.parts if p.nterm != 2 for sh in p.short])
        sv = self.saved()
        if sv and not self._busy:
            for k in ("stop", "steps", "method"):
                if k in sv: self.vars[k].set(str(sv[k]))
        elif not sv and not self.data:
            f = next((p.freq() for p in nl.parts if isinstance(p, C.Waveform) and p.is_ac()), None)
            if f: self.vars["stop"].set(f"{5 / f:g}"); self.vars["steps"].set("1000")
        if not self.data and not self.selected(self.probes):
            nets = [i for i, t in enumerate(self.probes.get(0, "end")) if t.startswith("V(")]
            if nets: self.probes.selection_set(nets[-1])

    def run(self):
        if not self.ready(): return
        try:
            cfg = {"stop": self.get("stop"), "steps": int(self.get("steps")), "method": self.get("method") or "trap"}
            ts = parse_value(cfg["stop"])
            if ts <= 0: raise ValueError("the stop time must be greater than 0")
            if not 2 <= cfg["steps"] <= 20000: raise ValueError("steps must be between 2 and 20000")
        except ValueError as ex: self.status.config(text=f"Transient: {ex}"); return
        if not self.save(cfg): return
        self.configure(cursor="watch"); self.update_idletasks()
        try: self.data = TR.run(self.doc.netlist, ts, cfg["steps"], cfg["method"])
        except (ValueError, SolveError_) as ex: self.data = None; self.status.config(text=str(ex)); self.plot(); return
        finally: self.configure(cursor="")
        self.refresh(); self.plot()
        self.status.config(text=f"Transient 0 → {cfg['stop']} s in {cfg['steps']} steps ({'trapezoidal' if cfg['method'] == 'trap' else 'backward Euler'}). Start: the DC operating point.")

    def curves(self):
        d = self.data; out = []
        if not d: return out
        for t in self.selected(self.probes):
            k = t[2:-1]; ys = d["V"].get(k) if t[0] == "V" else d["I"].get(k)
            if ys: out.append((t, ys))
        return out

    def plot(self):
        if not hasattr(self, "pl"): return
        cv = self.curves()
        if not cv: self.pl.clear("Set the stop time, press Run, then pick what to plot." if not self.data else "Pick something to plot."); self.note.config(text=""); return
        units = {"A" if t[0] == "I" else "V" for t, _ in cv}
        self.pl.show(self.data["t"], cv, "s", units.pop() if len(units) == 1 else "", False, "", legend=True)
        try: t0 = parse_value(self.get("from") or "0")
        except ValueError: t0 = 0.0
        t, ys = cv[0]; st = TR.stats(self.data["t"], ys, t0); dg = int(self.ctx.cfg.get("digits", 4)); u = "A" if t[0] == "I" else "V"
        if st:
            fr = TR.frequency([x for x in self.data["t"] if x >= t0], [y for x, y in zip(self.data["t"], ys) if x >= t0])
            self.note.config(text=f"{t} from {fmt_si(t0, 's', 3)}: mean {fmt_si(st['mean'], u, dg)}, RMS {fmt_si(st['rms'], u, dg)}, min {fmt_si(st['min'], u, dg)}, max {fmt_si(st['max'], u, dg)}, peak-to-peak {fmt_si(st['pp'], u, dg)}"
                                  + (f", frequency ≈ {fmt_si(fr, 'Hz', 3)}" if fr else "") + ("   (several curves: this line describes the first)" if len(cv) > 1 else ""))

    def csv(self):
        d = self.data
        if not d: self.ctx.say("Transient", "Run the simulation first."); return
        rows = [["t (s)"] + [f"V({n})" for n in d["V"]] + [f"I({p})" for p in d["I"]]]
        for k, t in enumerate(d["t"]): rows.append([t] + [d["V"][n][k] for n in d["V"]] + [d["I"][p][k] for p in d["I"]])
        self.save_csv("transient.csv", rows)

