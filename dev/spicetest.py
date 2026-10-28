import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.imports.spice_in import spice_to_json
from vibesimulation.analog.netlist import parse, to_spice
T="""test
V1 1 0 DC 10
R1 1 2 1k
D1 0 2 DZ5
E1 3 0 2 0 2
R2 3 0 1k
G1 4 0 2 0 1m
R3 4 0 2k
H1 5 0 V1 100
R4 5 0 1k
F1 6 0 V1 2
R5 6 0 1k
.model DZ5 D(BV=5.1 IBV=1m)
.dc V1 0 10 1
.end
"""
j,notes=spice_to_json(T); print(notes); nl,e=parse(j); print(e or nl.validate()); v,_=nl.solve(); print(v)
print(nl.analysis); print(to_spice(nl))
assert abs(v["2"]-5.14)<0.05 and abs(v["3"]-2*v["2"])<1e-6 and abs(v["4"]+v["2"]*1e-3*2e3)<1e-4 and abs(v["5"]+100*(10-v["2"])/1e3)<1e-4
assert type(nl.part("D1")).__name__=="Zener" and nl.part("D1").extra["vz"]=="5.1"
nl2,e=parse(to_spice and j); 
from vibesimulation.export.pdf import make_analog_pdf
from vibesimulation.analog.layout import SchematicBuilder
d=make_analog_pdf(nl,SchematicBuilder().build(nl),v,nl.solve()[1]); print("pdf bytes",len(d)); assert d[:4]==b"%PDF"
print("SPICE OK")
