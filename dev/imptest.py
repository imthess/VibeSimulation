"""Round trip: random circuit -> our .circ -> import -> same truth table?"""
import random, sys, itertools
sys.path.insert(0, "src"); sys.path.insert(0, "dev")
from vibesimulation.components import load_all
load_all()
from vibesimulation.core.serializer import parse
from vibesimulation.export.logisim import to_circ
from vibesimulation.imports.logisim_in import circ_to_json
from randtest import rand_circuit

def table(c):
    t = c.table(12)
    names = t[0] + t[1] + t[2]
    outs = sorted(t[2])
    return {tuple(r[names.index(n)] for n in t[0]): tuple(r[names.index(o)] for o in outs) for r in t[3]}, t[0], outs

seed, N = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed); done = bad = 0
while done < N:
    c = rand_circuit(rng)
    if c is None: continue
    try: text = to_circ(c)
    except ValueError: continue
    done += 1
    try:
        js, notes = circ_to_json(text)
        c2, errs = parse(js)
        errs = errs or c2.validate()
        if errs: raise ValueError(errs)
        a, ia, oa = table(c); b, ib, ob = table(c2)
        # same input names/order, outputs matched by name
        if ia != ib or oa != ob: raise ValueError(f"pins differ {ia}/{ib} {oa}/{ob}")
        if a != b: raise ValueError("truth tables differ")
    except Exception as e:
        bad += 1; print("FAIL", done, str(e)[:300]); open(f"dev/imp_bad_{seed}_{done}.circ", "w").write(text)
        print([ (k.type_name, k.attrs, k.ins, k.outs) for k in c.components][:8])
print("round trips", done, "failures", bad)
