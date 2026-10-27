"""File actions shared by the menu bar and the panes: open / save / download."""
import csv
import io
import os

from ..core.serializer import dumps
from ..export.logisim import to_circ
from ..export.pdf import make_analog_pdf, make_pdf

def circ_report(notes):
    """The compatibility report: one line per thing that was ignored or could not be imported."""
    if not notes: return ""
    return "\n\nCompatibility report:\n" + "\n".join("  • " + n for n in notes)


def write_sidecar(path, state):
    """The arrangement (positions, wires, orientation) goes beside the JSON as NAME.layout.json, so the JSON stays clean."""
    import json, os
    side = os.path.splitext(path)[0] + ".layout.json"
    try:
        if state and any(state.get(k) for k in state):
            with open(side, "w", encoding="utf-8") as f: json.dump(state, f)
        elif os.path.exists(side): os.remove(side)
    except OSError: pass


def read_sidecar(path):
    import json, os
    side = os.path.splitext(path)[0] + ".layout.json"
    try:
        with open(side, encoding="utf-8") as f: st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError): return {}


def load_file(doc, path):
    with open(path, encoding="utf-8") as f: text = f.read()
    if hasattr(doc, "load_project"): doc.load_project(text, read_sidecar(path))
    else: doc.set_text(text, state=read_sidecar(path))


BLANK = '{"inputs": ["A", "B"], "outputs": [], "gates": []}'


class FileActions:
    def __init__(self, ctx, doc, table_view):
        self.ctx, self.doc, self.table = ctx, doc, table_view

    def _ready(self, what):
        if not self.doc.valid:
            self.ctx.say(what, "There is no valid circuit yet. Fix the JSON or import an image first."); return False
        return True

    def _save(self, title, ext, name, data, binary=False):
        p = self.ctx.choose_file("save", title, [ext], name)
        if not p: return None
        if not p.lower().endswith(ext): p += ext
        try:
            with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as f: f.write(data)
        except Exception as e:
            self.ctx.say(title, str(e)); return None
        return p

    # ---- downloads
    def circ(self):
        if not self._ready("Download .circ"): return
        try: data = self.doc.circ_text()
        except Exception as e: self.ctx.say("Download .circ", str(e)); return
        p = self._save("Save Logisim circuit", ".circ", "circuit.circ", data)
        if p: self.ctx.say("Saved", f"{p}\n\nOpen it in Logisim-evolution with File > Open.")

    def pdf(self):
        if not self._ready("PDF"): return
        d = self.doc
        table = d.circuit.table(self.ctx.cfg.get("table_bits", 12))
        if table and not self.table.show_mid.get():            # same columns as the truth-table box: honour "Show intermediate outputs"
            ins, mids, outs, rows = table; keep = list(range(len(ins))) + list(range(len(ins) + len(mids), len(ins) + len(mids) + len(outs)))
            table = (ins, [], outs, [[r[i] for i in keep] for r in rows])
        try: data = make_pdf(d.layout, d.circuit, d.invals, table, values=d.values())
        except Exception as e: self.ctx.say("PDF", str(e)); return
        p = self._save("Save PDF", ".pdf", "circuit.pdf", data, True)
        if p: self.ctx.say("Saved", p)

    def json_save(self):
        if self.doc.text.strip() or len(self.doc.circuits) > 1:
            p = self._save("Save circuit JSON", ".json", "circuit.json", self.doc.project_text())
            if p: write_sidecar(p, self.doc.project_state()); self.ctx.say("Saved", p)

    def csv(self):
        data = getattr(self.table, "data", None)
        if not data: self.ctx.say("Truth table", "There is no truth table to save."); return
        head, rows = data
        out = io.StringIO(); w = csv.writer(out); w.writerow(head); w.writerows(rows)
        p = self._save("Save truth table", ".csv", "truth_table.csv", out.getvalue())
        if p: self.ctx.say("Saved", p)

    # ---- Logisim files
    def circ_open(self, path=None):
        """Open a Logisim .circ file straight into this section. What cannot be imported is listed in a report, never dropped silently."""
        from ..imports import load_file as read_any
        p = path or self.ctx.choose_file("open", "Open Logisim file", [".circ"])
        if not p: return False
        try: kind, text, notes = read_any(p)
        except Exception as e:
            self.ctx.say("Open Logisim file", str(e)); return False
        if kind != "digital":
            self.ctx.say("Open Logisim file", "This file is not a Logisim circuit."); return False
        if path: self.ctx.add_recent(path)
        self.doc.load_project(text) if '"circuits"' in text[:200] else self.doc.load_text(text)
        self.doc.set_inputs({})
        if not self.doc.valid:
            self.ctx.say("Open Logisim file", "The circuit was read but has a problem:\n" + "\n".join(self.doc.errors[:4]) + circ_report(notes)); return True
        if notes: self.ctx.say("Opened with notes", f"{os.path.basename(p)} was opened.{circ_report(notes)}")
        return True

    # ---- open / new
    def json_open(self, path=None):
        p = path or self.ctx.choose_file("open", "Open circuit JSON", [".json", ".txt"])
        if not p: return False
        if path: self.ctx.add_recent(path)
        try:
            load_file(self.doc, p)
        except Exception as e:
            self.ctx.say("Open", str(e)); return False
        self.doc.set_inputs({}); return True

    def new(self):
        self.doc.load_text(BLANK); self.doc.set_inputs({})


class AnalogActions:
    """File actions of the Multisim (analog) workspace."""
    BLANK = '{"components": [\n  {"id": "V1", "type": "VoltageSource", "value": "5", "nodes": ["n1", "0"]}\n]}'

    def __init__(self, ctx, doc, results_view):
        self.ctx, self.doc, self.results = ctx, doc, results_view
        self._f = FileActions(ctx, doc, None)

    def new(self): self.doc.load_text(self.BLANK)

    def cir(self):
        from ..analog.netlist import to_spice
        if self.doc.netlist is None or self.doc.errors: self.ctx.say("Download .cir", "There is no valid circuit yet."); return
        p = self._f._save("Save SPICE netlist", ".cir", "circuit.cir", to_spice(self.doc.netlist))
        if p: self.ctx.say("Saved", f"{p}\n\nIn Multisim: File > Import > From SPICE netlist. (Multisim's own .ms14 format is proprietary and cannot be written.)")

    def json_save(self):
        if self.doc.text.strip():
            p = self._f._save("Save circuit JSON", ".json", "analog_circuit.json", self.doc.text)
            if p: write_sidecar(p, self.doc.state); self.ctx.say("Saved", p)

    def json_open(self, path=None):
        p = path or self.ctx.choose_file("open", "Open circuit JSON", [".json", ".txt"])
        if not p: return False
        if path: self.ctx.add_recent(path)
        try:
            load_file(self.doc, p)
        except Exception as e: self.ctx.say("Open", str(e)); return False
        return True

    def csv(self):
        rows = getattr(self.results, "rows", None)
        if not rows: self.ctx.say("Results", "There are no results to save."); return
        out = io.StringIO(); w = csv.writer(out); w.writerow(["Name", "Voltage", "Current", "Power"]); w.writerows(rows)
        p = self._f._save("Save results", ".csv", "results.csv", out.getvalue())
        if p: self.ctx.say("Saved", p)

    def pdf(self):
        from ..analog.layout import SchematicBuilder
        d = self.doc
        if d.netlist is None or not d.valid: self.ctx.say("Download PDF", "There is no valid circuit yet: fix the JSON first."); return
        phasors = None
        try:
            from ..analog import ac as AC, components as ACC
            f = next((p.freq() for p in d.netlist.parts if isinstance(p, ACC.Waveform) and p.is_ac()), None)
            if f: prep = AC.prepare(d.netlist); pt = AC.point(prep, f); phasors = (pt, AC.power_summary(prep, pt))
        except ValueError: phasors = None
        try: data = make_analog_pdf(d.netlist, SchematicBuilder().build(d.netlist), d.volts, d.results, int(self.ctx.cfg.get("digits", 4)), phasors=phasors)
        except Exception as e: self.ctx.say("Download PDF", str(e)); return
        p = self._f._save("Save PDF", ".pdf", "multisim_circuit.pdf", data, True)
        if p: self.ctx.say("Saved", p)
    def circ(self): self.ctx.say("Download .circ", "Logisim .circ files come from the Logisim workspace. Use Download .cir here for a SPICE netlist.")
