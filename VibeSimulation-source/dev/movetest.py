import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.core.document import Document, SAMPLE
from vibesimulation.core import commands as C
from vibesimulation.core.serializer import dumps, parse
from vibesimulation.layout.engine import LayoutEngine
from vibesimulation.export.logisim import to_circ
d = Document(); d.load_sample(); assert d.valid
pl = {p.comp.id: (p.x, p.y) for p in d.layout.parts}; print(pl)
x, y = pl["g3"]
d.run(C.MovePart("g3", x + 60, y + 90)); print("valid", d.valid, d.layout_error)
print({p.comp.id: (p.x, p.y) for p in d.layout.parts}); print(d.text)
assert d.state['pos'] and '"pos"' not in d.text
to_circ(d.circuit)
d.undo(); assert '"pos"' not in d.text
d.redo(); d.run(C.ClearPositions()); assert '"pos"' not in d.text and d.valid
print("ok")
