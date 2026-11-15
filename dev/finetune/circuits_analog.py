"""Random analog circuits in the JSON format the AI import uses (resistor networks with a source, RC / RL, diodes)."""
import random

E12 = (1, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)


def _num(v):
    return f"{v:g}"


def _res(rng):
    m = rng.choice(E12); e = rng.choice((1, 10, 100, 1e3, 1e4, 1e5))
    v = m * e
    return (f"{_num(v / 1e6)}M" if v >= 1e6 else f"{_num(v / 1e3)}k" if v >= 1e3 else _num(v))


def _cap(rng):
    return rng.choice(("10n", "100n", "1u", "4.7u", "10u", "47u", "100p", "2.2n"))


def _ind(rng):
    return rng.choice(("1m", "10m", "100u", "4.7m", "1u", "22m"))


def generate(rng: random.Random):
    n = rng.randint(2, 4)                                       # nodes besides ground: n1..n
    nodes = ["0"] + [f"n{i}" for i in range(1, n + 1)]
    edges = []
    for i in range(1, len(nodes)):                              # a random spanning tree keeps the circuit connected
        edges.append((nodes[rng.randrange(i)], nodes[i]))
    for _ in range(rng.randint(0, 2)):                          # extra branches make loops
        a, b = rng.sample(nodes, 2)
        edges.append((a, b))
    deg = {x: 0 for x in nodes}; deg["n1"] += 1; deg["0"] += 1      # the source touches n1 and ground
    for a, b in edges: deg[a] += 1; deg[b] += 1
    for x in nodes[1:]:                                         # no dangling nodes: a real circuit has a current path through every net
        while deg[x] < 2:
            y = rng.choice([m for m in nodes if m != x])
            edges.append((x, y)); deg[x] += 1; deg[y] += 1
    count, parts = {}, []

    def add(kind, prefix, value, nd):
        count[prefix] = count.get(prefix, 0) + 1
        parts.append({"id": f"{prefix}{count[prefix]}", "type": kind, "value": value, "nodes": list(nd)} if value is not None else
                     {"id": f"{prefix}{count[prefix]}", "type": kind, "nodes": list(nd)})

    if rng.random() < 0.85: add("VoltageSource", "V", _num(rng.choice((1.5, 3.3, 5, 9, 12, 24))), ("n1", "0"))
    else: add("CurrentSource", "I", rng.choice(("1m", "10m", "2m", "500u")), ("0", "n1"))
    for a, b in edges:
        if {a, b} == {"n1", "0"} and rng.random() < 0.5: continue
        r = rng.random()
        if r < 0.72: add("Resistor", "R", _res(rng), (a, b))
        elif r < 0.82: add("Capacitor", "C", _cap(rng), (a, b))
        elif r < 0.90: add("Inductor", "L", _ind(rng), (a, b))
        else: add("Diode", "D", None, (a, b))
    if not any(p["type"] == "Resistor" for p in parts): add("Resistor", "R", _res(rng), ("n1", "n2" if n > 1 else "0"))
    return {"kind": "analog", "title": "", "components": parts}
