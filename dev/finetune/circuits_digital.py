"""Random logic circuits in the JSON format the AI import uses (the answer the model must learn to write)."""
import random

GATES = ("AND", "OR", "NAND", "NOR", "XOR", "XNOR", "NOT")
WEIGHTS = (4, 4, 3, 3, 2, 1, 3)
INPUT_SETS = (["A", "B", "C", "D"], ["a", "b", "c", "d"], ["X0", "X1", "X2", "X3"], ["P", "Q", "R", "S"], ["I0", "I1", "I2", "I3"])
OUTPUT_SETS = (["Y", "Z", "W"], ["F", "G", "H"], ["Out", "Out2", "Out3"], ["Q", "S", "T"], ["O1", "O2", "O3"])


def generate(rng: random.Random, max_gates=10):
    names = rng.choice(INPUT_SETS)
    n_in = rng.choice((2, 2, 3, 3, 4))
    inputs = names[:n_in]
    n_gates = rng.randint(1, max_gates)
    sigs, unused, gates = list(inputs), set(inputs), []
    for k in range(1, n_gates + 1):
        t = rng.choices(GATES, WEIGHTS)[0]
        fan = 1 if t == "NOT" else min(len(sigs), rng.choice((2, 2, 2, 3)))
        pool = sorted(unused)
        pick = rng.sample(pool, min(fan, len(pool)))
        rest = [s for s in sigs if s not in pick]
        pick += rng.sample(rest, fan - len(pick)) if fan > len(pick) else []
        rng.shuffle(pick)
        out = f"n{k}"
        gates.append({"id": f"g{k}", "type": t, "in": pick, "out": out})
        unused -= set(pick); sigs.append(out); unused.add(out)
    sinks = [g for g in gates if g["out"] in unused]
    while len(sinks) > 3:                                       # merge sinks until at most three outputs remain
        a, b = sinks.pop(), sinks.pop()
        k = len(gates) + 1
        g = {"id": f"g{k}", "type": rng.choice(("AND", "OR", "XOR")), "in": [a["out"], b["out"]], "out": f"n{k}"}
        gates.append(g); sinks.append(g)
    outs = rng.choice(OUTPUT_SETS)[:len(sinks)]
    for g, o in zip(sinks, outs): g["out"] = o
    return {"kind": "digital", "inputs": list(inputs), "outputs": list(outs), "gates": gates}
