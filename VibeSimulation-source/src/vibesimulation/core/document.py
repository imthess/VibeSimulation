"""The Document: single source of truth for the JSON text, the circuit parsed from it and its undo history.

Views (import box, JSON box, circuit view, truth table) never talk to each other. They all read the
Document and subscribe to its changes (Observer pattern), which keeps them in sync.
"""
from .events import Subject
from . import layoutstate as LS
from . import sim as SIM
from . import project as PRJ
from .model import Circuit
from .serializer import dumps, parse

SAMPLE = {"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [
    {"id": "g1", "type": "NAND", "in": ["A", "B", "C"], "out": "n1"},
    {"id": "g2", "type": "NOT", "in": ["C"], "out": "n2"},
    {"id": "g3", "type": "NOR", "in": ["n1", "n2"], "out": "Y"}]}


class Document(Subject):
    MAX_HISTORY = 300

    def __init__(self):
        super().__init__()
        self.text = ""
        self.circuit = None        # last successfully parsed + validated circuit
        self.layout = None         # its drawing
        self.errors = []           # problems with the current text
        self.layout_error = ""
        self.valid = False
        self.invals = {}           # current input values (what the user toggled)
        self.sim = {}              # remembered values of flip-flops, registers, counters ... {part id: state}
        self.tick_n = 0            # how many clock ticks (half cycles) have happened
        self.oscillating = False   # a feedback loop that never settles
        self.vals = {}             # signal values after the last calculation
        self.state = LS.extract(Circuit())     # layout state: positions, wires, orientation (kept out of the JSON text)
        self._hist, self._pos = [], -1
        self.cur = "main"                      # the circuit being edited; a project can hold several (subcircuits)
        self.circuits = {"main": {"text": "", "state": {}}}

    # ------------------------------------------------------------------ loading text
    def set_text(self, text, record=True, state=None):
        """Replace the JSON text; re-parse, re-validate and re-draw it; notify the views.

        The layout state (where parts/wires are and which way they face) is kept in self.state, NOT in the text.
        state=None keeps the current layout for parts/wires that still exist; state={} (see load_text) starts fresh.
        An empty text is a valid blank circuit, so the circuit view can be edited from nothing."""
        from ..layout.engine import LayoutEngine
        errs, circuit = [], None
        if not text.strip():
            circuit = Circuit()
        else:
            circuit, errs = parse(text)
            if circuit is not None and not errs:
                errs = circuit.validate(loose=True)
        if circuit is not None and not errs:
            legacy = LS.extract(circuit)                       # old files: "pos"/"wires" written inside the JSON
            base = state if state is not None else self.state
            if LS.has_layout(legacy):
                base = LS.merge(base, legacy)
                text = dumps(circuit)                          # ...and removed from the visible text
            LS.apply(circuit, base)
        self.text = text
        self.circuits[self.cur] = {"text": text, "state": self.state}
        self._publish()
        self.errors, self.layout_error, self.valid = errs, "", False
        if not errs:
            try:
                self.layout = LayoutEngine().build(circuit)
                self.circuit, self.valid = circuit, True
                self.state = LS.extract(circuit)
                self.circuits[self.cur]["state"] = self.state
                self._prune_inputs()
                self.sim = SIM.fresh(circuit, self.sim)
                self._settle()
            except ValueError as e:
                self.layout_error = str(e)
        if record:
            self._record(text, self.state)
        self.notify("changed")

    def load_text(self, text):
        """A different circuit (New / Open / Import): nothing of the old layout is kept (and the project is just this one circuit)."""
        self.cur, self.circuits = "main", {"main": {"text": "", "state": {}}}
        self._hist, self._pos = [], -1
        self.set_text(text, state={})

    # ------------------------------------------------------------------ the project: several circuits
    def _publish(self):
        PRJ.set_project({n: e["text"] for n, e in self.circuits.items()}, self.cur)

    def circuit_names(self):
        return list(self.circuits)

    def switch(self, name):
        """Edit another circuit of the project (undo history is per circuit and starts again)."""
        if name not in self.circuits or name == self.cur: return
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        self.cur = name
        self.invals, self.sim, self.tick_n = {}, {}, 0
        self._hist, self._pos = [], -1
        e = self.circuits[name]
        self._publish()
        self.set_text(e["text"], state=e["state"] or {})
        self.notify("circuits")

    def add_circuit(self, name, text=""):
        """New circuit; returns an error message or None."""
        name = name.strip()
        if not name: return "Give the circuit a name."
        if name in self.circuits: return f"There is already a circuit called '{name}'."
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        self.circuits[name] = {"text": text, "state": {}}
        self.switch(name); return None

    def _rewrite(self, fn):
        """Apply fn(circuit) to every circuit's parts (used when one is renamed); layout is kept."""
        for n, e in self.circuits.items():
            if n == self.cur or not e["text"].strip(): continue
            c, errs = parse(e["text"])
            if c is None: continue
            fn(c)
            e["text"] = dumps(c)

    def rename_circuit(self, old, new):
        new = new.strip()
        if old not in self.circuits: return "No such circuit."
        if not new: return "Give the circuit a name."
        if new != old and new in self.circuits: return f"There is already a circuit called '{new}'."
        if new == old: return None
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        def fix(c):
            for p in c.components:
                if getattr(p, "is_sub", False) and p.attrs["circuit"] == old: p.attrs["circuit"] = new
        self._rewrite(fix)
        self.circuits = {(new if n == old else n): e for n, e in self.circuits.items()}
        was = self.cur
        if self.cur == old: self.cur = new
        self._publish()
        if self.cur != was or True:
            e = self.circuits[self.cur]; self.set_text(e["text"], record=False, state=e["state"] or {})
        self.notify("circuits"); return None

    def delete_circuit(self, name):
        if name not in self.circuits: return "No such circuit."
        if len(self.circuits) == 1: return "A project needs at least one circuit."
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        users = [n for n in self.circuits if n != name and name in PRJ.uses(n)]
        if users: return f"'{name}' is used inside {', '.join(users)}: remove it from there first."
        if name == self.cur: self.switch(next(n for n in self.circuits if n != name))
        del self.circuits[name]; self._publish(); self.notify("circuits"); return None

    def project_text(self):
        """Everything to save: just the circuit's JSON if the project has one circuit, else {"main": ..., "circuits": {...}}."""
        import json
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        if len(self.circuits) == 1: return self.text
        parts = []
        for n, e in self.circuits.items():
            t = e["text"]
            try: json.loads(t)
            except ValueError: t = ""
            if not t.strip(): t = '{"inputs": [], "outputs": [], "gates": []}'
            body = "\n".join(("    " + ln if i else ln) for i, ln in enumerate(t.rstrip("\n").split("\n")))
            parts.append(f'    {json.dumps(n)}: {body}')
        return '{\n  "main": ' + json.dumps(self.cur) + ',\n  "circuits": {\n' + ",\n".join(parts) + "\n  }\n}\n"

    def circ_text(self):
        """The whole project as a Logisim .circ file (raises ValueError naming the circuit that is not valid)."""
        from ..export.logisim import project_to_circ, to_circ
        if len(self.circuits) == 1: return to_circ(self.circuit)
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        out = {}
        for n, e in self.circuits.items():
            if n == self.cur: out[n] = self.circuit; continue
            c, errs = parse(e["text"]) if e["text"].strip() else (Circuit(), [])
            if c is not None and not errs: errs = c.validate(loose=True)
            if errs: raise ValueError(f"circuit '{n}': {errs[0]}")
            LS.apply(c, e["state"] or {}); out[n] = c
        return project_to_circ(out, self.cur)

    def project_state(self):
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        if len(self.circuits) == 1: return self.state
        return {"circuits": {n: e["state"] for n, e in self.circuits.items() if e["state"]}}

    def load_project(self, text, side=None):
        """Open saved text: one circuit's JSON, or a project with several circuits."""
        import json
        side = side or {}
        try: raw = json.loads(text)
        except ValueError: raw = None
        if isinstance(raw, dict) and isinstance(raw.get("circuits"), dict) and raw["circuits"]:
            states = side.get("circuits", {}) if isinstance(side.get("circuits"), dict) else {}
            self.circuits = {}
            for n, d in raw["circuits"].items():
                c, errs = parse(d) if isinstance(d, dict) else (None, ["x"])
                self.circuits[str(n)] = {"text": dumps(c) if c is not None and not errs else json.dumps(d, indent=1), "state": states.get(n, {})}
            main = raw.get("main") if raw.get("main") in self.circuits else next(iter(self.circuits))
            self.cur = main; self._hist, self._pos = [], -1
            self.invals, self.sim, self.tick_n = {}, {}, 0
            self._publish()
            self.set_text(self.circuits[main]["text"], state=self.circuits[main]["state"] or {})
            self.notify("circuits")
        else:
            self.load_text(text)
            if side: self.set_text(self.text, state=side)

    def set_circuit(self, circuit):
        self.set_text(dumps(circuit), state=LS.extract(circuit))

    def _prune_inputs(self):
        names = {p.name: p.width for p in self.circuit.inputs}
        self.invals = {k: v for k, v in self.invals.items() if k in names}

    # ------------------------------------------------------------------ editing
    def run(self, command):
        """Apply a Command to a copy of the current circuit; the result becomes the new text."""
        c = self.circuit.copy()
        command.apply(c)
        c.sync()
        self.set_text(dumps(c), state=LS.extract(c))

    # ------------------------------------------------------------------ input values and the clock
    def has_seq(self):
        try: return bool(self.circuit) and self.circuit.has_seq()
        except ValueError: return False

    def _settle(self):
        if self.circuit is None: self.vals, self.oscillating = {}, False; return
        self.vals, self.oscillating = SIM.settle(self.circuit, self.invals, self.sim, self.tick_n)

    def set_input(self, name, value):
        self.invals[name] = value
        self._settle(); self.notify("values")

    def set_inputs(self, values):
        self.invals = dict(values)
        self._settle(); self.notify("values")

    def tick(self, half_cycles=1):
        """Logisim's Simulate > Tick Half Cycle (1) / Tick Full Cycle (2): clocks move on, parts that see an edge change."""
        if not self.valid: return
        for _ in range(half_cycles):
            self.tick_n += 1; self._settle()
        self.notify("values")

    def set_memory(self, cid, mem):
        """Change the contents of a RAM while the circuit runs (Logisim: the hex editor)."""
        flat = self.circuit.flat() if self.circuit else None
        st = self.sim.get(cid)
        if st is None or flat is None or "mem" not in st: return
        st["mem"] = {int(a): int(v) for a, v in mem.items() if v}
        self._settle(); self.notify("values")

    def reset_sim(self):
        """Logisim's Simulate > Reset Simulation: every part forgets, the clock starts again."""
        if self.circuit is None: return
        self.sim, self.tick_n = SIM.fresh(self.circuit), 0
        self._settle(); self.notify("values")

    def values(self):
        if self.circuit is None: return {}
        return self.vals if self.has_seq() else self.circuit.simulate(self.invals)

    # ------------------------------------------------------------------ history (Memento = the text)
    def _record(self, text, state=None):
        item = (text, state if state is not None else self.state)
        if self._hist and self._hist[self._pos] == item:
            return
        del self._hist[self._pos + 1:]
        self._hist.append(item)
        self._hist = self._hist[-self.MAX_HISTORY:]
        self._pos = len(self._hist) - 1

    def can_undo(self): return self._pos > 0
    def can_redo(self): return self._pos < len(self._hist) - 1

    def undo(self):
        if self.can_undo():
            self._pos -= 1
            self.set_text(self._hist[self._pos][0], record=False, state=self._hist[self._pos][1])

    def redo(self):
        if self.can_redo():
            self._pos += 1
            self.set_text(self._hist[self._pos][0], record=False, state=self._hist[self._pos][1])

    def load_sample(self):
        import json
        from .serializer import parse as p
        c, _ = p(json.dumps(SAMPLE))
        self.set_circuit(c)
