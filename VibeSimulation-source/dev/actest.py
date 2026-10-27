import sys, math, cmath
import os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog import ac
def mk(parts):
    nl,e=parse('{"components":%s}'%parts); assert not e,e; return nl
# RC low-pass
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"1","nodes":["in","0"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["in","out"]},{"id":"C1","type":"Capacitor","value":"1u","nodes":["out","0"]}]')
prep=ac.prepare(nl)
for f in (10,159.1549,1000,10000):
    pt=ac.point(prep,f); H=pt["V"]["out"]; ex=1/(1+1j*2*math.pi*f*1e-3)
    print(f,abs(H),abs(ex),math.degrees(cmath.phase(H)),math.degrees(cmath.phase(ex))); assert abs(H-ex)<1e-9
sw=ac.sweep(nl,1,1e5,200); m=ac.metrics(sw["f"],sw["V"]["out"]); print(m); assert abs(m["f_high"]-159.15)<1.5 and m["kind"]=="low-pass"
print(m["rolloff_db_per_dec"])
# series RLC bandpass across R
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"1","nodes":["in","0"]},{"id":"L1","type":"Inductor","value":"10m","nodes":["in","a"]},{"id":"C1","type":"Capacitor","value":"1u","nodes":["a","out"]},{"id":"R1","type":"Resistor","value":"10","nodes":["out","0"]}]')
sw=ac.sweep(nl,100,5000,400); m=ac.metrics(sw["f"],sw["V"]["out"]); f0=1/(2*math.pi*math.sqrt(10e-3*1e-6)); Q=math.sqrt(10e-3/1e-6)/10
print(m, f0, Q); assert abs(m["f0"]-f0)/f0<0.01 and abs(m["q"]-Q)/Q<0.03
pt=ac.point(ac.prepare(nl),f0); print(ac.power_summary(ac.prepare(nl),pt)) # P=0.05, pf=1
from vibesimulation.analog import transient as T
# RC step: V source 0 -> value step? use DC 5 with cap initial from op => steady. Use square wave source instead.
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"1","freq":"100","wave":"square","nodes":["in","0"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["in","out"]},{"id":"C1","type":"Capacitor","value":"1u","nodes":["out","0"]}]')
r=T.run(nl,0.004,4000)
# first half-period: in=+1 (sin>=0). out = 1-exp(-t/tau)
import math
for tt in (0.0005,0.001,0.002):
    k=round(tt/0.004*4000); ex=1-math.exp(-tt/1e-3); print("rc",tt,r["V"]["out"][k],ex); assert abs(r["V"]["out"][k]-ex)<2e-3
# AC vs transient cross-check: sine drive on RLC, compare steady amplitude
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"2","freq":"1000","phase":"30","nodes":["in","0"]},{"id":"R1","type":"Resistor","value":"100","nodes":["in","a"]},{"id":"L1","type":"Inductor","value":"10m","nodes":["a","out"]},{"id":"C1","type":"Capacitor","value":"2u","nodes":["out","0"]},{"id":"R2","type":"Resistor","value":"500","nodes":["out","0"]}]')
r=T.run(nl,0.03,30000); st=T.stats(r["t"],r["V"]["out"],0.02); pt=ac.point(ac.prepare(nl),1000); H=pt["V"]["out"]
print("tran peak",st["max"],st["min"],"ac",abs(H)); assert abs(st["max"]-abs(H))/abs(H)<2e-3 and abs(-st["min"]-abs(H))/abs(H)<2e-3
# phase check: value at a time t equals |H| sin(wt + arg)
w=2*math.pi*1000; k=29000; t=r["t"][k]; ex=abs(H)*math.sin(w*t+cmath.phase(H)); print(r["V"]["out"][k],ex); assert abs(r["V"]["out"][k]-ex)<3e-3*abs(H)
print("freq",T.frequency(r["t"],r["V"]["out"]))
# half-wave rectifier
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"5","freq":"50","nodes":["in","0"]},{"id":"D1","type":"Diode","nodes":["in","out"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["out","0"]}]')
r=T.run(nl,0.04,4000); st=T.stats(r["t"],r["V"]["out"]); print(st); assert 4.2<st["max"]<4.5 and st["min"]>-1e-6
# energy: inductor current ramp  V=1 -> L=1 -> i=t  (DC op: L is a short so use step via square? skip)
print("TRAN OK")
from vibesimulation.export.pdf import make_analog_pdf
from vibesimulation.analog.layout import SchematicBuilder
nl=mk('[{"id":"V1","type":"VoltageSource","value":"0","ac":"1","freq":"1k","nodes":["in","0"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["in","out"]},{"id":"C1","type":"Capacitor","value":"1u","nodes":["out","0"]}]')
prep=ac.prepare(nl); pt=ac.point(prep,1000); v,res=nl.solve()
d=make_analog_pdf(nl,SchematicBuilder().build(nl),v,res,phasors=(pt,ac.power_summary(prep,pt))); assert d[:4]==b"%PDF"; print("PDF OK",len(d))
