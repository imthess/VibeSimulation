"""Document for the analog workspace (same job as core.Document: text, parsed circuit, solution, undo history)."""
from ..core.events import Subject
from .netlist import Netlist, apply_state, dumps, extract_state, parse
from .solver import SolveError

SAMPLE = {"title": "Resistor ladder", "components": [
    {"id": "V1", "type": "VoltageSource", "value": "5", "nodes": ["n1", "0"]},
    {"id": "R1", "type": "Resistor", "value": "100", "nodes": ["n1", "0"]},
    {"id": "R2", "type": "Resistor", "value": "220", "nodes": ["n1", "n2"]},
    {"id": "R3", "type": "Resistor", "value": "470", "nodes": ["n2", "0"]},
    {"id": "R4", "type": "Resistor", "value": "150", "nodes": ["n2", "n3"]},
    {"id": "R5", "type": "Resistor", "value": "100", "nodes": ["n3", "0"]}]}


class AnalogDocument(Subject):
    MAX_HISTORY = 300

    def __init__(self):
        super().__init__()
        self.text, self.netlist, self.volts, self.results = "", None, {}, {}
        self.errors, self.layout_error, self.valid = [], "", False
        self.state = {"pos": {}, "wires": {}}      # layout state (positions, wire routes): kept out of the JSON text
        self._hist, self._pos = [], -1

    def set_text(self, text, record=True, state=None):
        errs, nl = [], None
        if not text.strip(): errs = ["Paste an analog circuit JSON here (see the sample), or press File > New."]
        else:
            nl, errs = parse(text)
            if nl is not None and not errs: errs = nl.validate()
        if nl is not None and not [e for e in errs if e.startswith("Not valid") or e.startswith("The JSON")]:
            legacy = extract_state(nl)
            base = state if state is not None else self.state
            if legacy["pos"] or legacy["wires"]:
                base = {"pos": {**base.get("pos", {}), **legacy["pos"]}, "wires": {**base.get("wires", {}), **legacy["wires"]}}
                text = dumps(nl)
            apply_state(nl, base)
        self.text = text
        self.errors, self.layout_error, self.valid = errs, "", False
        if not errs:
            try:
                self.volts, self.results = nl.solve(); self.netlist, self.valid = nl, True; self.state = extract_state(nl)
            except SolveError as e: self.layout_error = str(e); self.netlist = nl
        if record: self._record(text, self.state)
        self.notify("changed")

    def edit(self, fn):
        """Apply fn(netlist) to a copy and make the result the new text."""
        nl = (self.netlist or Netlist()).copy(); fn(nl); self.set_text(dumps(nl), state=extract_state(nl))

    def load_text(self, text): self.set_text(text, state={"pos": {}, "wires": {}})

    def _record(self, text, state=None):
        item = (text, state if state is not None else self.state)
        if self._hist and self._hist[self._pos] == item: return
        del self._hist[self._pos + 1:]; self._hist.append(item); self._hist = self._hist[-self.MAX_HISTORY:]; self._pos = len(self._hist) - 1

    def can_undo(self): return self._pos > 0
    def can_redo(self): return self._pos < len(self._hist) - 1

    def undo(self):
        if self.can_undo(): self._pos -= 1; self.set_text(self._hist[self._pos][0], record=False, state=self._hist[self._pos][1])

    def redo(self):
        if self.can_redo(): self._pos += 1; self.set_text(self._hist[self._pos][0], record=False, state=self._hist[self._pos][1])

    def load_sample(self):
        import json
        self.load_text(dumps(parse(json.dumps(SAMPLE))[0]))
