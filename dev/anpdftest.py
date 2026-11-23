import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.workspaces.multisim.core.netlist import parse
from vibesimulation.workspaces.multisim.core.document import SAMPLE
from vibesimulation.workspaces.multisim.layout.schematic_layout import SchematicBuilder
from vibesimulation.workspaces.multisim.export.pdf import make_analog_pdf
import json
nl, e = parse(json.dumps(SAMPLE)); assert not e and not nl.validate()
nl.part("R3").pos = (60, 40)
v, r = nl.solve(); L = SchematicBuilder().build(nl)
open("/tmp/pv/a.pdf", "wb").write(make_analog_pdf(nl, L, v, r))
print("ok")
