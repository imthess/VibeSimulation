"""Bench instruments as their own windows: function generator, oscilloscope, multimeter.

Each is a non-modal window attached to the circuit document: the generator edits a source, the scope and meter measure the circuit as it stands
(and re-read it when it changes)."""
import tkinter as tk
from tkinter import ttk

from ...analog import components as C
from ...analog import meter as ME
from ...analog import scope as SC
from ...analog.units import fmt_si, parse_value
from ..widgets import Btn

SCREEN_BG, TRACE = "#0b1a10", ("#facc15", "#22d3ee", "#f472b6", "#86efac")


class Instrument(tk.Toplevel):
    """Template: subclasses fill ``build(body)`` and may react to ``on_doc``."""
    NAME = "Instrument"

    def __init__(self, ctx, doc):
        super().__init__(ctx.root); self.ctx, self.doc = ctx, doc; P = ctx.P
        self.title(self.NAME); self.configure(bg=P["card"]); self.vars = {}; self.labels = []
        self.body = tk.Frame(self, bg=P["card"]); self.body.pack(fill="both", expand=True, padx=14, pady=12)
        self.build(self.body); self.bind("<Escape>", lambda e: self.destroy())
        self._sub = doc.subscribe(self._changed) if hasattr(doc, "subscribe") else None
        self.protocol("WM_DELETE_WINDOW", self.close); self.on_doc("changed")

    def close(self):
        try:
            if self._sub is not None and hasattr(self.doc, "unsubscribe"): self.doc.unsubscribe(self._sub)
        except Exception: pass
        self.destroy()

    def _changed(self, kind="changed"):
        try:
            if self.winfo_exists(): self.on_doc(kind)
        except tk.TclError: pass

    def build(self, body): raise NotImplementedError
    def on_doc(self, kind): pass

    def lab(self, parent, text, **kw):
        P = self.ctx.P; l = tk.Label(parent, text=text, bg=P["card"], fg=kw.pop("fg", P["muted"]), font=kw.pop("font", self.ctx.f_small), **kw); return l

    def field(self, parent, name, text, init, w=8, choices=None, side="left"):
        self.lab(parent, text).pack(side=side, padx=(6, 2)); self.vars[name] = v = tk.StringVar(value=str(init))
        if choices is not None: e = ttk.Combobox(parent, textvariable=v, values=choices, state="readonly" if choices else "normal", style="Modern.TCombobox", width=w)
        else: e = ttk.Entry(parent, textvariable=v, style="Modern.TEntry", width=w)
        e.pack(side=side, ipady=1); return e

    def get(self, k): return self.vars[k].get().strip()
    def row(self, parent=None):
        f = tk.Frame(parent or self.body, bg=self.ctx.P["card"]); f.pack(fill="x", pady=3); return f
    def netlist(self):
        nl = self.doc.netlist
        return nl if nl is not None and self.doc.valid else None


class FunctionGenerator(Instrument):
    NAME = "Function generator"

    def build(self, body):
        r = self.row(); self.field(r, "src", "Source", "", 8, [], ); self.combo = r.winfo_children()[-1]; self.vars["src"].trace_add("write", lambda *a: self.load())
        r = self.row(); self.field(r, "wave", "Waveform", "sine", 9, list(C.Waveform.WAVES)); self.field(r, "freq", "Frequency (Hz)", "1k", 8)
        r = self.row(); self.field(r, "ac", "Amplitude (peak)", "1", 8); self.field(r, "value", "DC offset", "0", 8)
        r = self.row(); self.field(r, "duty", "Duty (square, 0..1)", "0.5", 6); self.field(r, "phase", "Phase (°)", "0", 6)
        r = self.row(); Btn(self.ctx, r, "Apply to circuit", self.apply, "primary", pady=4, padx=14, font=self.ctx.f_small).pack(side="left", padx=6)
        self.msg = self.lab(r, ""); self.msg.pack(side="left", padx=8)
        self.shape = tk.Canvas(body, width=360, height=110, highlightthickness=0, bg=SCREEN_BG); self.shape.pack(pady=(8, 0))
        for k in ("wave", "freq", "ac", "value", "duty", "phase"): self.vars[k].trace_add("write", lambda *a: self.preview())

    def sources(self):
        nl = self.netlist(); return [p for p in nl.parts if isinstance(p, C.Waveform)] if nl else []

    def on_doc(self, kind):
        ids = [p.id for p in self.sources()]; self.combo["values"] = ids
        if ids and self.get("src") not in ids: self.vars["src"].set(ids[0])
        elif not ids: self.msg.config(text="Place a voltage or current source first.")
        self.load()

    def load(self):
        p = next((q for q in self.sources() if q.id == self.get("src")), None)
        if p is None: return
        self.vars["value"].set(str(p.value))
        for k in ("ac", "freq", "phase", "wave", "duty"): self.vars[k].set(str(p.extra[k]))

    def apply(self):
        try:
            for k in ("value", "ac", "freq", "phase", "duty"): parse_value(self.get(k))
            if parse_value(self.get("freq")) <= 0: raise ValueError("The frequency must be greater than 0.")
            d = parse_value(self.get("duty"))
            if not 0 < d < 1: raise ValueError("The duty must be between 0 and 1 (exclusive).")
        except ValueError as ex: self.msg.config(text=str(ex), fg=self.ctx.P["bad"] if "bad" in self.ctx.P else "red"); return
        pid = self.get("src")
        def go(nl):
            q = nl.part(pid); q.value = self.get("value")
            for k in ("ac", "freq", "phase", "wave", "duty"): q.extra[k] = self.get(k)
        self.doc.edit(go); self.msg.config(text=f"{pid} updated.", fg=self.ctx.P["muted"])

    def preview(self):
        c = self.shape; c.delete("all")
        try:
            q = C.Waveform("Vprev", ["a", "0"], self.get("value") or "0", ac=self.get("ac"), freq=self.get("freq"), wave=self.get("wave"), duty=self.get("duty"), phase=self.get("phase"))
            f = parse_value(self.get("freq")); amp = abs(parse_value(self.get("ac"))) + abs(parse_value(self.get("value"))) or 1.0
            ys = [q.at(2.0 / f * k / 359) for k in range(360)]
        except Exception: return
        for k in range(1, 4): c.create_line(0, 110 * k / 4, 360, 110 * k / 4, fill="#16351f")
        pts = []
        for k, y in enumerate(ys): pts += [k, 55 - y / amp * 45]
        c.create_line(*pts, fill=TRACE[0], width=2); c.create_text(6, 6, text=f"2 periods, ±{fmt_si(amp, 'V', 3)}", anchor="nw", fill="#86efac", font=self.ctx.f_small)


class Oscilloscope(Instrument):
    NAME = "Oscilloscope"
    W, H = 640, 400

    def build(self, body):
        self.data = None
        r = self.row(); self.field(r, "tdiv", "Time/div", "200u", 6); self.field(r, "delay", "Delay", "0", 6)
        self.field(r, "tsrc", "Trigger", "A", 3, ["A", "B", "C", "D"]); self.field(r, "level", "level", "0", 5); self.field(r, "slope", "", "rising", 7, ["rising", "falling"]); self.field(r, "tmode", "", "auto", 6, ["auto", "normal"])
        Btn(self.ctx, r, "Run", self.run, "primary", pady=3, padx=14, font=self.ctx.f_small).pack(side="left", padx=8)
        self.chan = []
        for i, name in enumerate("ABCD"):
            r = self.row(); col = TRACE[i]; tk.Label(r, text=f" {name} ", bg=col, fg="#000", font=self.ctx.f_small).pack(side="left")
            self.field(r, f"p{i}", "probe", "" if i else "", 9, []); self.chan.append(r.winfo_children()[-1])
            self.field(r, f"vdiv{i}", "V/div", "1", 5); self.field(r, f"off{i}", "offset", "0", 5); self.field(r, f"cp{i}", "", "dc", 4, ["dc", "ac", "gnd"])
        self.screen = tk.Canvas(body, width=self.W, height=self.H, highlightthickness=0, bg=SCREEN_BG); self.screen.pack(pady=(8, 4))
        self.reads = tk.Label(body, text="", bg=self.ctx.P["card"], fg=self.ctx.P["text"], font=self.ctx.f_small, justify="left", anchor="w"); self.reads.pack(fill="x")
        self.grid_()

    def on_doc(self, kind):
        nl = self.netlist()
        if nl is None: return
        names = [""] + [f"V({n})" for n in nl.nets()] + [f"I({p.id})" for p in nl.parts]
        for c in self.chan: c["values"] = names
        if not any(self.get(f"p{i}") for i in range(4)) and len(names) > 1: self.vars["p0"].set(names[1]); self.vars["p1"].set(names[-1] if names[-1].startswith("V(") else "")
        if self.data is not None: self.run(quiet=True)

    def grid_(self, tdiv=None):
        c = self.screen; c.delete("all"); W, H = self.W, self.H
        for i in range(11): c.create_line(W * i / 10, 0, W * i / 10, H, fill="#1f4d2b" if i not in (0, 10) else "#2f7a42")
        for j in range(9): c.create_line(0, H * j / 8, W, H * j / 8, fill="#1f4d2b" if j not in (0, 8) else "#2f7a42")
        c.create_line(0, H / 2, W, H / 2, fill="#3f9d57"); c.create_line(W / 2, 0, W / 2, H, fill="#3f9d57")

    def run(self, quiet=False):
        nl = self.netlist()
        if nl is None: self.reads.config(text="Fix the circuit first."); return
        try:
            chans = [{"probe": self.get(f"p{i}"), "vdiv": parse_value(self.get(f"vdiv{i}")), "offset": parse_value(self.get(f"off{i}")), "coupling": self.get(f"cp{i}")} for i in range(4) if self.get(f"p{i}")]
            if not chans: raise ValueError("Choose a probe for channel A.")
            if any(c["vdiv"] <= 0 for c in chans): raise ValueError("Volts per division must be greater than 0.")
            idx = {name: k for k, name in enumerate(n for i, n in enumerate("ABCD") if self.get(f"p{i}"))}
            ts = self.get("tsrc")
            if ts not in idx: raise ValueError(f"The trigger source {ts} has no probe.")
            trig = {"source": idx[ts], "level": parse_value(self.get("level")), "slope": self.get("slope"), "mode": self.get("tmode")}
            self.data = SC.capture(nl, chans, self.get("tdiv"), trig, parse_value(self.get("delay")))
            self.letters = list(idx)
        except ValueError as ex: self.reads.config(text=str(ex)); return
        self.draw()

    def draw(self):
        d = self.data; self.grid_(); c = self.screen; W, H = self.W, self.H
        if not d["triggered"] and d["channels"][0]["y"] is None: self.reads.config(text="Waiting for a trigger (normal mode): no edge crossed the level."); c.create_text(W / 2, H / 2, text="NO TRIGGER", fill="#facc15", font=self.ctx.f_title); return
        lines = []
        for k, ch in enumerate(d["channels"]):
            col = TRACE["ABCD".index(self.letters[k])]; n = len(ch["y"]); pts = []
            for j, y in enumerate(ch["y"]): pts += [W * j / (n - 1), H / 2 - (y + ch["offset"]) / ch["vdiv"] * (H / 8)]
            pts = [max(-50.0, min(H + 50.0, v)) if i % 2 else v for i, v in enumerate(pts)]
            c.create_line(*pts, fill=col, width=2); r = ch["read"]
            lines.append(f"{self.letters[k]} {ch['probe']}: Vpp {fmt_si(r['vpp'], '', 4)}  max {fmt_si(r['vmax'], '', 4)}  min {fmt_si(r['vmin'], '', 4)}  avg {fmt_si(r['avg'], '', 4)}  RMS {fmt_si(r['rms'], '', 4)}" + (f"  f {fmt_si(r['freq'], 'Hz', 4)}" if r["freq"] else ""))
        c.create_text(8, 6, text=f"{fmt_si(d['tdiv'], 's', 3)}/div  ·  " + ("triggered" if d["triggered"] else "free run (no trigger found)"), anchor="nw", fill="#86efac", font=self.ctx.f_small)
        self.reads.config(text="\n".join(lines))


class Multimeter(Instrument):
    NAME = "Multimeter"

    def build(self, body):
        r = self.row(); self.field(r, "mode", "Mode", "vdc", 6, list(ME.MODES))
        self.field(r, "a", "+", "", 7, []); self.ca = r.winfo_children()[-1]; self.field(r, "b", "−", "0", 7, []); self.cb = r.winfo_children()[-1]
        self.field(r, "part", "part", "", 7, []); self.cp = r.winfo_children()[-1]
        for k in ("mode", "a", "b", "part"): self.vars[k].trace_add("write", lambda *a: self.read())
        self.lcd = tk.Label(body, text="----", bg="#a7c957", fg="#14290a", font=("Courier", 34, "bold"), width=14, anchor="e", padx=10, pady=8); self.lcd.pack(pady=8)
        self.info = self.lab(body, ""); self.info.pack()

    def on_doc(self, kind):
        nl = self.netlist()
        if nl is None: self.info.config(text="Fix the circuit first."); return
        nets = ["0"] + list(nl.nets()); self.ca["values"] = nets; self.cb["values"] = nets; self.cp["values"] = [p.id for p in nl.parts]
        if not self.get("a") and len(nets) > 1: self.vars["a"].set(nets[1])
        if not self.get("part") and nl.parts: self.vars["part"].set(nl.parts[0].id)
        self.read()

    def read(self):
        nl = self.netlist()
        if nl is None: return
        m = self.get("mode")
        try: r = ME.read(nl, m, self.get("a") or None, self.get("b") or "0", self.get("part") or None)
        except ValueError as ex: self.lcd.config(text="----"); self.info.config(text=str(ex)); return
        self.lcd.config(text=r["text"]); self.info.config(text=ME.MODES[m][0] + (f" through {self.get('part')}" if m in ("idc", "iac") else f" between {self.get('a')} and {self.get('b') or '0'}"))


INSTRUMENTS = {"Function generator": FunctionGenerator, "Oscilloscope": Oscilloscope, "Multimeter": Multimeter}


def open_instrument(ctx, doc, name, store):
    """One window per instrument: raise it if it is already open."""
    w = store.get(name)
    try:
        if w is not None and w.winfo_exists(): w.deiconify(); w.lift(); return w
    except tk.TclError: pass
    store[name] = w = INSTRUMENTS[name](ctx, doc); return w
