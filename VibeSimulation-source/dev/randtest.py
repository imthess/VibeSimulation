"""Random mixed circuits: our simulation vs real Logisim."""
import random, sys, time
sys.path.insert(0, "src"); sys.path.insert(0, "dev")
from vibesimulation.core.model import Circuit, IOPin
from vibesimulation.components import ComponentRegistry as R
from vibesimulation.export.logisim import to_circ
from semtest import logisim, val

POOL = [("AND", {"inputs": 2}), ("OR", {"inputs": 3}), ("XOR", {"inputs": 2}), ("NOT", {}), ("NAND", {"inputs": 2}), ("NOR", {"inputs": 2}), ("XNOR", {"inputs": 2}),
        ("Adder", {"width": 1}), ("Adder", {"width": 2}), ("Adder", {"width": 3}), ("Subtractor", {"width": 2}), ("Comparator", {"width": 2}), ("Comparator", {"width": 3, "mode": "signed"}),
        ("MUX", {"select": 1, "width": 1}), ("MUX", {"select": 1, "width": 2}), ("MUX", {"select": 2, "width": 1}), ("DEMUX", {"select": 1, "width": 1}), ("DEMUX", {"select": 2, "width": 1}),
        ("DECODER", {"select": 1}), ("DECODER", {"select": 2}), ("ENCODER", {"select": 2}), ("ENCODER", {"select": 1}), ("Negator", {"width": 2}), ("Shifter", {"width": 4, "shift": "rl"}),
        ("BitAdder", {"width": 3, "inputs": 2}), ("Splitter", {"widths": [1, 1]}), ("Splitter", {"widths": [2, 1]}), ("Combiner", {"widths": [1, 1]}), ("Combiner", {"widths": [2, 2]}),
        ("Multiplier", {"width": 2}), ("BitFinder", {"width": 4}), ("ODDPARITY", {"inputs": 3}), ("Constant", {"width": 2, "value": 2})]

def rand_circuit(rng):
    ins = [IOPin(chr(65 + i), rng.choice([1, 1, 1, 2, 3, 4])) for i in range(rng.randint(2, 4))]
    sigs = {p.name: p.width for p in ins}; comps = []
    for k in range(rng.randint(2, 7)):
        t, a = rng.choice(POOL)
        c = R.lookup(t)(f"g{k + 1}", dict(a))
        if t in ("AND", "OR", "XOR", "NAND", "NOR", "XNOR", "ODDPARITY", "NOT"):
            c.attrs["width"] = rng.choice([1, 1, 2, 3]) if t != "ODDPARITY" else 1
            if t == "ODDPARITY": c.attrs["width"] = 1
        ok = True
        for p in c.in_ports():
            cands = [s for s, w in sigs.items() if w == p.width]
            if p.optional and rng.random() < 0.5: continue
            if not cands: ok = False; break
            c.ins[p.name] = rng.choice(cands)
        if not ok: continue
        for p in c.out_ports():
            if p.optional and rng.random() < 0.6: continue
            n = f"n{k + 1}_{p.name}"; c.outs[p.name] = n; sigs[n] = p.width
        if not c.outs: continue
        comps.append(c)
    pool = [s for c in comps for s in c.outs.values()]
    if not pool: return None
    circ = Circuit(ins, [IOPin(s, 1) for s in rng.sample(pool, min(len(pool), rng.randint(1, 3)))], comps).sync()
    return circ if not circ.validate() and sum(p.width for p in ins) <= 10 else None

if __name__ == "__main__":
    seed, N = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed); done = bad = lay = 0; t0 = time.time()
    while done < N:
        c = rand_circuit(rng)
        if c is None: continue
        done += 1
        try: text = to_circ(c)
        except ValueError as e: lay += 1; print("LAYOUT FAIL", done, str(e)[:300]); continue
        open("dev/rt.circ", "w").write(text)
        head, rows = logisim(c, "rt")
        tab = c.table(12); names = tab[0] + tab[1] + tab[2]; mine = {}
        for r in tab[3]:
            d = dict(zip(names, r)); mine[tuple(d[n] for n in tab[0])] = d
        wrong = 0
        for row in rows:
            d = dict(zip(head, row)); key = tuple(val(d[n]) for n in tab[0])
            if None in key or key not in mine: continue
            for o in tab[2] + tab[1]:
                if o in d and val(d[o]) != mine[key][o]:
                    wrong += 1
                    if wrong <= 3: print('   diff', dict(zip(tab[0], key)), o, 'logisim', d[o], 'mine', mine[key][o])
        if wrong or len(rows) != len(tab[3]):
            bad += 1; print("MISMATCH", done, wrong, len(rows), len(tab[3]), [(c.type_name, c.attrs, c.ins, c.outs) for c in c.components]); open(f"dev/bad_{seed}_{done}.circ", "w").write(text)
    print("circuits", N, "layout fails", lay, "mismatches", bad, "secs", int(time.time() - t0))
