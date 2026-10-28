"""Subcircuits: flatten + simulate (no GUI)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vibesimulation.components
from vibesimulation.core.document import Document
import json
d = Document()
d.load_text('{"inputs":["a","b"],"outputs":["s","c"],"gates":[{"id":"x","type":"XOR","in":["a","b"],"out":"s"},{"id":"n","type":"AND","in":["a","b"],"out":"c"}]}')
d.rename_circuit("main", "half")
print(d.add_circuit("main"))
d.set_text(json.dumps({"inputs":["A","B","Cin"],"outputs":["S","Cout"],"gates":[
 {"id":"h1","type":"Circuit","circuit":"half","in":{"a":"A","b":"B"},"out":{"s":"s1","c":"c1"}},
 {"id":"h2","type":"Circuit","circuit":"half","in":{"a":"s1","b":"Cin"},"out":{"s":"S","c":"c2"}},
 {"id":"o","type":"OR","in":["c1","c2"],"out":"Cout"}]}))
print(d.errors, d.layout_error, d.valid)
for a in range(2):
  for b in range(2):
    for c in range(2):
      v = d.circuit.simulate({"A":a,"B":b,"Cin":c}); assert v["S"]==(a+b+c)&1 and v["Cout"]==(a+b+c)>>1,(a,b,c,v)
print("table", d.circuit.table()[0:3])
print(d.project_text()[:300])
t=d.project_text(); st=d.project_state()
d2=Document(); d2.load_project(t, st); print(d2.cur, d2.circuit_names(), d2.valid, d2.circuit.simulate({"A":1,"B":1,"Cin":1}))
d.switch("half"); print(d.cur, d.valid)
print(d.delete_circuit("half"))
d.switch("main"); d.add_circuit("self"); 
d.set_text(json.dumps({"inputs":["a"],"outputs":["y"],"gates":[{"id":"u","type":"Circuit","circuit":"main","in":{"A":"a"},"out":{"S":"y"}}]}))
print(d.errors)
print("OK")
