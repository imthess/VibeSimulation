"""The Document of the VLSI section (Facade over compiler, snapshots and writer).

It *is* a normal circuit Document (so the circuit box, truth table, undo and simulation work unchanged), but Verilog is what
the user writes. ``set_verilog`` compiles text into circuits; ``verilog`` gives the text back: the user's own while the circuit is
unchanged, otherwise generated from the circuit. Its project (list of circuits) is separate from Logisim's.
"""
import vibesimulation.workspaces.logisim.core.layoutstate as LS
import vibesimulation.workspaces.logisim.core.project as PRJ
from vibesimulation.workspaces.logisim.core.document import Document
from vibesimulation.workspaces.logisim.core.model import Circuit
from vibesimulation.workspaces.logisim.core.serializer import dumps
from vibesimulation.workspaces.verilog.project.compiler import compile_text
from vibesimulation.workspaces.verilog.project.hints import lines_from_hints
from vibesimulation.workspaces.verilog.project.samples import SAMPLE
from vibesimulation.workspaces.verilog.project.simsettings import SimSettings
import vibesimulation.workspaces.verilog.core.lintcodes as lintcodes
import vibesimulation.workspaces.verilog.core.preproc as preproc
from vibesimulation.workspaces.verilog.project.testbench import merge
from vibesimulation.workspaces.verilog.project.snapshots import SnapshotStore
from vibesimulation.workspaces.verilog.export.writer import VerilogWriter, canonical
class VlsiDocument(Document):
    def __init__(self):
        super().__init__()
        self.snaps = SnapshotStore()
        self.writer = VerilogWriter()
        self.version = 0           # counts every change (lets the editor tell "my edit" from "someone else's")
        self.tb_text = ""          # the Testbench tab: modules that are run, not built into circuits
        self.problems = []         # [(severity "error"|"warning", line, message)] of the last compile
        self.partlines = {}        # module -> {part id: line} from the last compile of the text the user typed
        self.last_run = None       # the TBResult of the last Run
        self.sim_settings = SimSettings()   # simulation settings (top module, standard, -D / -I, time limit ...)

    # ---- keeping the snapshots right when the project changes
    def set_text(self, text, record=True, state=None):
        self.version += 1
        super().set_text(text, record, state)

    def load_text(self, text):
        self.snaps.clear(); super().load_text(text)

    def load_project(self, text, side=None):
        self.snaps.clear(); super().load_project(text, side)

    def rename_circuit(self, old, new):
        err = super().rename_circuit(old, new)
        if not err and old != new.strip(): self.snaps.rename(old, new.strip())
        return err

    def delete_circuit(self, name):
        err = super().delete_circuit(name)
        if not err: self.snaps.drop(name)
        return err

    def load_sample(self):
        self.snaps.clear(); self.tb_text = ""; self.set_verilog(SAMPLE)

    def new_blank(self, text):
        """A fresh project made of the given Verilog."""
        self.cur, self.circuits = "main", {"main": {"text": "", "state": {}}}
        self.snaps.clear(); self.tb_text = ""; self.last_run = None; self._hist, self._pos = [], -1
        self.set_text("", state={})
        return self.set_verilog(text)

    # ---- Verilog out
    def verilog(self, name=None):
        """Verilog of a circuit: what the user typed while the circuit is unchanged, else written from the circuit."""
        name = name or self.cur
        text = self.text if name == self.cur else self.circuits.get(name, {}).get("text", "")
        canon = canonical(text)
        typed = self.snaps.valid_text(name, canon)
        if typed is not None: return typed
        if canon is None: return self.snaps.last_text(name)
        others = {n: e["text"] for n, e in self.circuits.items() if n != name}
        return self.writer.write(name, text, others) or ""

    def verilog_project(self):
        """Every circuit of the project as one Verilog file (a module before the modules that use it)."""
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        order, seen = [], set()
        def visit(n):
            if n in seen or n not in self.circuits: return
            seen.add(n)
            c = PRJ.lookup(n)
            for comp in (c.components if c else []):
                if getattr(comp, "is_sub", False): visit(comp.attrs["circuit"])
            order.append(n)
        for n in self.circuits: visit(n)
        return "\n".join(self.verilog(n) for n in order)

    def apply_settings(self, sim=None):
        """Make the simulation settings take effect: macros / include folders for the preprocessor, warning codes that are off; then compile again."""
        if sim is not None: self.sim_settings = sim
        preproc.Config.set(self.sim_settings.defines, self.sim_settings.incdirs); lintcodes.Config.off = set(self.sim_settings.lint_off)
        self.notify("settings")

    # ---- hooks for a language that is lowered to Verilog (Template Method: the SystemVerilog document overrides these)
    def compile(self, text, circuits, cur):
        return compile_text(text, circuits, cur)

    def prepare(self, text):
        """The text as Verilog (same line numbers) for the parts that read Verilog only: testbench runs and the testbench tab."""
        return text

    # ---- Verilog in
    def set_verilog(self, text):
        """Turn Verilog text into circuits (one per module). Returns [] on success, else [(line, message)] and nothing changes."""
        self.circuits[self.cur] = {"text": self.text, "state": self.state}
        result = self.compile(text, {n: e["text"] for n, e in self.circuits.items()}, self.cur)
        if result.errors:
            self._publish(); self.problems = [("error", ln, m) for ln, m in result.errors]; self.notify("problems"); return result.errors
        if result.testbenches:                                   # testbench modules are kept in their own tab
            self.tb_text = merge(self.tb_text, result.testbenches, self.prepare); self.notify("testbench")
        if not result.circuits:                                  # the text only had testbenches
            self._publish(); self.problems = []; self.notify("problems"); return []
        if result.rename_from:
            self.snaps.drop(result.rename_from); err = self.rename_circuit(result.rename_from, result.names[0])
            if err: return [(1, err)]
        newcur, made = result.newcur, result.circuits
        for n, circ in made.items():                              # the other modules become circuits of the project
            if n == newcur: continue
            LS.apply(circ, (self.circuits.get(n) or {}).get("state") or {})
            self.circuits[n] = {"text": dumps(circ), "state": LS.extract(circ)}
            self.snaps.put(n, result.slices[n], canonical(self.circuits[n]["text"]))
        if newcur != self.cur:                                   # show the top module; a blank leftover circuit is removed
            old = self.cur; blank = not (self.circuit and (self.circuit.components or self.circuit.inputs or self.circuit.outputs))
            self.circuits[old] = {"text": self.text, "state": self.state}
            self.cur = newcur; self.invals, self.sim, self.tick_n = {}, {}, 0; self._hist, self._pos = [], -1
            if blank and old not in made and not any(old in PRJ.uses(n) for n in self.circuits if n != old):
                del self.circuits[old]; self.snaps.drop(old)
            self._publish()
            self.snaps.put(newcur, result.slices[newcur], canonical(dumps(made[newcur])))      # before set_text: the views read it when they are told
            self.set_text(dumps(made[newcur]), state=(self.circuits.get(newcur) or {}).get("state") or {})
        else:
            self._publish()
            self.snaps.put(newcur, result.slices[newcur], canonical(dumps(made[newcur])))
            self.set_text(dumps(made[newcur]), state=None)
        self.partlines.update(result.partlines)
        self.problems = [("warning", ln, lintcodes.tag(m)) for ln, m in result.warnings if lintcodes.keep(m)]
        self.notify("problems"); self.notify("circuits")
        return []

    # ---- testbench tab
    def set_testbench(self, text):
        self.tb_text = text; self.notify("testbench")

    def part_lines(self):
        """{part id: line in the Verilog shown now} for the circuit being shown."""
        canon = canonical(self.text)
        if self.snaps.valid_text(self.cur, canon) is not None: return self.partlines.get(self.cur, {})
        return lines_from_hints(self.verilog())
