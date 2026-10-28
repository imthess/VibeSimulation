import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog.document import SAMPLE
from vibesimulation.analog.layout import SchematicBuilder
from vibesimulation.export.pdf import make_analog_pdf
import json
nl, e = parse(json.dumps(SAMPLE)); assert not e and not nl.validate()
nl.part("R3").pos = (60, 40)
v, r = nl.solve(); L = SchematicBuilder().build(nl)
open("/tmp/pv/a.pdf", "wb").write(make_analog_pdf(nl, L, v, r))
print("ok")
