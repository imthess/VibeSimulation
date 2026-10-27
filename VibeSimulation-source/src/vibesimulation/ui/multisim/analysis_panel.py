"""Multisim analyses on top of the DC results: DC sweep (plot + CSV) and Thevenin / Norton equivalent of a chosen part."""
import csv
import io
import math
import tkinter as tk
from tkinter import ttk

from ...analog import analysis as AN
from ...analog.units import fmt_si, parse_value
from ..widgets import Btn

COLORS = ("#2f6bff", "#e5484d", "#16a34a", "#d97706", "#8b5cf6", "#0891b2", "#be185d", "#64748b")


def nice_ticks(lo, hi, n=5):
    """Round tick positions covering [lo, hi]."""
    if hi - lo < 1e-30: lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / n; mag = 10 ** math.floor(math.log10(raw)); step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag)
    t = math.ceil(lo / step - 1e-9) * step; out = []
    while t <= hi + step * 1e-9: out.append(round(t / step) * step); t += step
    return out


class AnalysisPanel(tk.Frame):
    def __init__(self, ctx, doc, master, status):
        super().__init__(master, bd=0); self.ctx, self.doc, self.status = ctx, doc, status
        self.data = None; self._busy = False
        self.columnconfigure(0, weight=1); self.rowconfigure(2, weight=1)
        v = lambda t="": tk.StringVar(value=t)
        self.part, self.a, self.b, self.n, self.load = v(), v("0"), v("10"), v("21"), v()
        top = tk.Frame(self, bd=0); top.grid(row=0, column=0, sticky="ew"); self.top = top
        self.lbl = [tk.Label(top, text="DC sweep of", font=ctx.f_small)]; self.lbl[0].pack(side="left")
        self.cb_part = ttk.Combobox(top, textvariable=self.part, state="readonly", style="Modern.TCombobox", width=6); self.cb_part.pack(side="left", padx=4)
        self.cb_part.bind("<<ComboboxSelected>>", lambda e: self.pick_part())
        for text, var, w in (("from", self.a, 6), ("to", self.b, 6), ("n", self.n, 4)):
            l = tk.Label(top, text=text, font=ctx.f_small); l.pack(side="left", padx=(6, 2)); self.lbl.append(l)
            e = ttk.Entry(top, textvariable=var, style="Modern.TEntry", width=w); e.pack(side="left", ipady=1); e.bind("<Return>", lambda ev: self.run())
        top2 = tk.Frame(self, bd=0); self.top2 = top2
        Btn(ctx, top2, "Run", self.run, "primary", pady=3, padx=12, font=ctx.f_small).pack(side="left")
        Btn(ctx, top2, "CSV", self.csv, "ghost", pady=3, padx=8, font=ctx.f_small).tip("Save the sweep as a CSV table").pack(side="left", padx=4)
        self.lbl.append(tk.Label(top2, text="plot:", font=ctx.f_small)); self.lbl[-1].pack(side="left", padx=(10, 2))
        mid = top2; self.mid = mid
        self.probes = tk.Listbox(mid, selectmode="extended", height=2, exportselection=False, bd=0, highlightthickness=1, font=ctx.f_small); self.probes.pack(side="left", fill="x", expand=True, padx=4)
        self.probes.bind("<<ListboxSelect>>", lambda e: self.plot())
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, height=120); self.canvas.grid(row=2, column=0, sticky="nsew", pady=6)
        self.canvas.bind("<Configure>", lambda e: self.plot())
        bot = tk.Frame(self, bd=0); self.bot = bot
        self.lbl.append(tk.Label(bot, text="Equivalent circuit seen by part", font=ctx.f_small)); self.lbl[-1].pack(side="left")
        self.cb_load = ttk.Combobox(bot, textvariable=self.load, state="readonly", style="Modern.TCombobox", width=6); self.cb_load.pack(side="left", padx=4)
        Btn(ctx, bot, "Find", self.thevenin, "secondary", pady=3, padx=12, font=ctx.f_small).pack(side="left")
        self.res = tk.Label(self, text="", font=ctx.f_small, anchor="nw", justify="left")
        self.bind("<Configure>", lambda e: self.res.configure(wraplength=max(100, e.width - 10)))
        self.which = "sweep"; self.show("sweep")
        ctx.themed.append(self._paint); self._paint()

    def show(self, which):
        """'sweep' (controls, plot) or 'thevenin' (load picker, result)."""
        self.which = which
        for w in (self.top, self.top2, self.canvas, self.bot, self.res): w.grid_forget()
        if which == "sweep":
            self.top.grid(row=0, column=0, sticky="ew"); self.top2.grid(row=1, column=0, sticky="ew", pady=(6, 0)); self.canvas.grid(row=2, column=0, sticky="nsew", pady=6)
            self.rowconfigure(2, weight=1); self.rowconfigure(4, weight=0)
        else:
            self.bot.grid(row=0, column=0, sticky="ew"); self.res.grid(row=1, column=0, sticky="nsew", pady=(10, 0)); self.rowconfigure(2, weight=0); self.rowconfigure(1, weight=1)

    def _paint(self):
        P = self.ctx.P
        for w in (self, self.top, self.top2, self.bot): w.configure(bg=P["card"])
        for l in self.lbl: l.configure(bg=P["card"], fg=P["muted"])
        self.res.configure(bg=P["card"], fg=P["text"]); self.canvas.configure(bg=P["canvas"])
        self.probes.configure(bg=P["field"], fg=P["text"], selectbackground=P["accent"], selectforeground=P["accent_fg"], highlightbackground=P["border"], highlightcolor=P["accent"])
        self.plot()

    # ---- keep the lists in step with the circuit
    def refresh(self):
        nl = self.doc.netlist
        if nl is None or not self.doc.valid: return
        sw = AN.sweepable_parts(nl); ids = [p.id for p in sw]
        self.cb_part.configure(values=ids); self.cb_load.configure(values=[p.id for p in nl.parts])
        saved = (nl.analysis or {}).get("sweep") or {}
        if saved.get("part") in ids and not self._busy:
            self.part.set(saved["part"]); self.a.set(str(saved.get("from", 0))); self.b.set(str(saved.get("to", 10))); self.n.set(str(saved.get("points", 21)))
        if self.part.get() not in ids: self.part.set(ids[0] if ids else ""); self.pick_part()
        if self.load.get() not in [p.id for p in nl.parts]: self.load.set(nl.parts[0].id if nl.parts else "")
        names = AN.probe_names(nl)
        if list(self.probes.get(0, "end")) != names:
            keep = {self.probes.get(i) for i in self.probes.curselection()}
            self.probes.delete(0, "end")
            for t in names: self.probes.insert("end", t)
            for i, t in enumerate(names):
                if t in keep: self.probes.selection_set(i)

    def pick_part(self):
        nl = self.doc.netlist; p = nl.part(self.part.get()) if nl else None
        if p is None: return
        try: v = p.number()
        except Exception: v = 1.0
        if p.unit == "Ω": self.a.set(fmt_plain(v / 10 or 1)); self.b.set(fmt_plain(v * 10))
        else: self.a.set("0"); self.b.set(fmt_plain(v * 2 if v else 10))

    # ---- sweep
    def run(self):
        d = self.doc
        if d.netlist is None or not d.valid: self.status.config(text="Fix the circuit first."); return
        try:
            cfg = {"part": self.part.get(), "from": self.a.get().strip(), "to": self.b.get().strip(), "points": int(self.n.get())}
            parse_value(cfg["from"]); parse_value(cfg["to"])
            if not 2 <= cfg["points"] <= 2000: raise ValueError("points must be between 2 and 2000")
            if not cfg["part"]: raise ValueError("choose the part to sweep")
        except ValueError as ex: self.status.config(text=f"Sweep: {ex}"); return
        self._busy = True
        try:
            d.edit(lambda nl: nl.analysis.__setitem__("sweep", cfg))
            if d.netlist is None or not d.valid: return
            try: self.data = AN.sweep_from_settings(d.netlist, cfg)
            except ValueError as ex: self.status.config(text=f"Sweep: {ex}"); return
        finally: self._busy = False
        if not self.probes.curselection():
            nets = [i for i, t in enumerate(self.probes.get(0, "end")) if t.startswith("V(")]
            if nets: self.probes.selection_set(nets[0])
        self.plot(); bad = len(self.data["errors"])
        self.status.config(text=f"Swept {cfg['part']} from {cfg['from']} to {cfg['to']} in {cfg['points']} points" + (f"  ·  {bad} point(s) have no solution (gaps in the plot)" if bad else ""))

    def series(self):
        """[(label, [y...])] for the selected probes."""
        if not self.data: return []
        out = []
        for i in self.probes.curselection():
            t = self.probes.get(i); k = t[2:-1]
            out.append((t, self.data["V"].get(k) if t.startswith("V(") else self.data["I"].get(k)))
        return [(t, ys) for t, ys in out if ys]

    def plot(self):
        c, P = self.canvas, self.ctx.P; c.delete("all"); W, H = c.winfo_width(), c.winfo_height()
        if W < 80 or H < 60: return
        S = self.series()
        if not S:
            c.create_text(W / 2, H / 2, text="Choose a part, a range and press Run.\nThen pick what to plot." if not self.data else "Pick something to plot.", fill=P["muted"], font=self.ctx.f_small, justify="center"); return
        xs = self.data["x"]; vals = [y for _, ys in S for y in ys if y is not None]
        if not vals: c.create_text(W / 2, H / 2, text="No point of the sweep has a solution.", fill=P["muted"], font=self.ctx.f_small); return
        y0, y1 = min(vals), max(vals); ty = nice_ticks(y0, y1 if y1 > y0 else y0 + 1); y0, y1 = min(y0, ty[0]), max(y1, ty[-1]); tx = nice_ticks(xs[0], xs[-1])
        L, R, T, B = 70, 12, 10, 24 + 14 * ((len(S) + 2) // 3); pw, ph = W - L - R, H - T - B
        if pw < 30 or ph < 20: c.create_text(W / 2, H / 2, text="Make this pane taller to see the plot.", fill=P["muted"], font=self.ctx.f_small); return
        X = lambda x: L + (x - xs[0]) / ((xs[-1] - xs[0]) or 1) * pw; Y = lambda y: T + ph - (y - y0) / ((y1 - y0) or 1) * ph
        yu = lambda t: "A" if t.startswith("I(") else "V"; unit0 = yu(S[0][0]); same = all(yu(t) == unit0 for t, _ in S)
        for t in ty: c.create_line(L, Y(t), W - R, Y(t), fill=P["border"]); c.create_text(L - 6, Y(t), text=fmt_si(t, unit0 if same else "", 3), anchor="e", fill=P["muted"], font=self.ctx.f_small)
        for t in tx: c.create_line(X(t), T, X(t), T + ph, fill=P["border"]); c.create_text(X(t), T + ph + 4, text=fmt_si(t, self.data["unit"], 3), anchor="n", fill=P["muted"], font=self.ctx.f_small)
        c.create_rectangle(L, T, W - R, T + ph, outline=P["muted"])
        for j, (t, ys) in enumerate(S):
            col, seg = COLORS[j % len(COLORS)], []
            for x, y in zip(xs, ys):
                if y is None:
                    if len(seg) > 3: c.create_line(*seg, fill=col, width=2)
                    seg = []
                else: seg += [X(x), Y(y)]
            if len(seg) > 3: c.create_line(*seg, fill=col, width=2)
            elif len(seg) == 2: c.create_oval(seg[0] - 2, seg[1] - 2, seg[0] + 2, seg[1] + 2, fill=col, outline=col)
            lx, ly = L + (j % 3) * (pw // 3), T + ph + 22 + 14 * (j // 3)
            c.create_line(lx, ly, lx + 16, ly, fill=col, width=3); c.create_text(lx + 20, ly, text=t, anchor="w", fill=P["text"], font=self.ctx.f_small)

    def csv(self):
        if not self.data: self.ctx.say("Sweep", "Run a sweep first."); return
        d = self.data; head = [f"{d['part']} ({d['unit']})".strip()] + [f"V({n})" for n in d["V"]] + [f"I({p})" for p in d["I"]]
        out = io.StringIO(); w = csv.writer(out); w.writerow(head)
        for k, x in enumerate(d["x"]): w.writerow([x] + ["" if d["V"][n][k] is None else d["V"][n][k] for n in d["V"]] + ["" if d["I"][p][k] is None else d["I"][p][k] for p in d["I"]])
        from ..actions import FileActions
        p = FileActions(self.ctx, self.doc, None)._save("Save sweep", ".csv", "dc_sweep.csv", out.getvalue())
        if p: self.ctx.say("Saved", p)

    # ---- Thevenin / Norton
    def thevenin(self):
        d = self.doc
        if d.netlist is None or not d.valid: self.res.config(text="Fix the circuit first."); return
        try: r = AN.thevenin(d.netlist, self.load.get())
        except ValueError as ex: self.res.config(text=str(ex)); return
        dg = int(self.ctx.cfg.get("digits", 4)); f = lambda x, u: "—" if x is None else fmt_si(x, u, dg)
        self.res.config(text=f"Seen from {r['load']} ({r['a']} relative to {r['b']}):  Thevenin  Vth = {f(r['voc'], 'V')},  Rth = {f(r['rth'], 'Ω')}   ·   "
                             f"Norton  In = {f(r['isc'], 'A')} in parallel with {f(r['rth'], 'Ω')}   ·   maximum power {f(r['pmax'], 'W')} into a load of {f(r['rth'], 'Ω')}")


def fmt_plain(x):
    return f"{x:.6g}"
