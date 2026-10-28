"""Every built-in example loads, is valid and (VLSI) simulates."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.product.examples import EXAMPLES, for_section
from vibesimulation.core.document import Document
from vibesimulation.analog.document import AnalogDocument
from vibesimulation.vlsi.document import VlsiDocument
from vibesimulation.systemverilog.document import SvDocument
from vibesimulation.vlsi import simulation
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
    else: print("ok  ", m)
print(len(EXAMPLES), "examples")
for e in EXAMPLES:
    if e.section == "logisim":
        d = Document(); d.load_text(e.text); ok(d.valid and not d.errors, f"{e.key} {d.errors}")
        ok(d.has_seq() or d.circuit.table(8) is not None, f"{e.key} table")
    elif e.section == "multisim":
        d = AnalogDocument(); d.load_text(e.text); ok(d.valid and not d.errors, f"{e.key} {d.errors}")
    else:
        d = (SvDocument if e.section == "systemverilog" else VlsiDocument)(); errs = d.new_blank(e.text); ok(not errs and d.valid, f"{e.key} {errs}")
        if e.testbench: d.set_testbench(e.testbench)
        r, _ = simulation.run(d, cycles=16); ok(r.error is None, f"{e.key} runs {r.error and r.error.msg}")
    ok(len(e.steps) >= 2 and e.summary, f"{e.key} has a tutorial")
sys.exit(1 if bad else 0)
