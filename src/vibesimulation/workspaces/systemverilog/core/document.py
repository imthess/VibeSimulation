"""The document of the SystemVerilog section: a VLSI document whose text is lowered to Verilog before it is compiled.

It overrides two hooks of VlsiDocument (Template Method) and adds nothing else, so the circuit, the truth table, undo, the testbench run
and the waveforms all work as they do in the VLSI section."""
from vibesimulation.workspaces.verilog.core.lexer import VError
from vibesimulation.workspaces.verilog.project.compiler import Compiled, compile_text, pins_of
from vibesimulation.workspaces.verilog.project.document import VlsiDocument
from vibesimulation.workspaces.systemverilog.core.compiler import lower
from vibesimulation.workspaces.systemverilog.core.samples import SAMPLE
from vibesimulation.workspaces.systemverilog.core.slicing import Slicer
class SvDocument(VlsiDocument):
    def known(self, circuits=None):
        """{module: port names} of the project's circuits: what `.*` may connect to when the module is in another text."""
        out = {}
        for n in (circuits if circuits is not None else self.circuits):
            pins = pins_of(n)
            if pins is not None: out[n] = pins[2]
        return out

    def compile(self, text, circuits, cur):
        try: low = lower(text, self.known(circuits))
        except VError as e: return Compiled({}, [], "", cur, errors=[(e.line or 1, e.msg)])
        result = compile_text(low.verilog, circuits, cur)
        if result.errors: return result
        result.warnings = sorted(set(result.warnings) | set(low.warnings))
        Slicer(text, low.verilog).apply(result)
        return result

    def prepare(self, text):
        try: return lower(text, self.known()).verilog
        except VError: return text

    def load_sample(self):
        self.snaps.clear(); self.tb_text = ""; self.set_verilog(SAMPLE)
