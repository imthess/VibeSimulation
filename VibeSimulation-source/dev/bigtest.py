import sys, os, random, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all
load_all()
from vibesimulation.core.serializer import parse, dumps
from vibesimulation.layout.engine import LayoutEngine
def big(seed, nin=8, ngates=40, nout=4):
    rng = random.Random(seed); sigs = [chr(65 + i) for i in range(nin)]; gates = []
    for k in range(ngates):
        t = rng.choice(["AND", "OR", "XOR", "NAND", "NOR", "NOT", "XNOR"])
        recent = sigs[-12:] if rng.random() < .7 else sigs
        n = 1 if t == "NOT" else rng.choice([2, 2, 3])
        ins = rng.sample(recent, min(n, len(recent)))
        o = f"n{k}"; g = {"id": f"g{k}", "type": t, "in": ins, "out": o}; gates.append(g); sigs.append(o)
    return {"inputs": sigs[:nin], "outputs": sigs[-nout:], "gates": gates}
if __name__ == "__main__":
    for seed in range(1, 6):
        c, errs = parse(json.dumps(big(seed))); print(seed, errs, c.validate()[:2])
        t = time.time()
        try:
            lay = LayoutEngine().build(c); print("  ok", round(time.time() - t, 1), "s", len(lay.wires), "wires")
        except ValueError as e: print("  FAIL", str(e)[:100], round(time.time() - t, 1))
