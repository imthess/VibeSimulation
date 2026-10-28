"""Layout state: everything about a drawing that is NOT part of the circuit's logic.

Part positions, I/O pin positions, hand-drawn wire routes and part orientation (facing) live here, held by the
Document next to the JSON text instead of inside it. That keeps the JSON short and readable while the circuit
view still remembers how the user arranged things. (Old files that still carry "pos"/"wires" in their JSON are read
and moved into this state automatically.)
"""


def extract(circuit):
    """Circuit -> plain dict {"pos": {id: [x, y]}, "pins": {"in:A": [x, y]}, "wires": {net: segs}, "facing": {id: "north"}}."""
    st = {"pos": {}, "pins": {}, "wires": {}, "facing": {}}
    for c in circuit.components:
        if c.pos: st["pos"][c.id] = [int(c.pos[0]), int(c.pos[1])]
        f = getattr(c, "facing", "east")
        if f != "east": st["facing"][c.id] = f
    for kind, pins in (("in", circuit.inputs), ("out", circuit.outputs)):
        for p in pins:
            if p.pos: st["pins"][f"{kind}:{p.name}"] = [int(p.pos[0]), int(p.pos[1])]
    st["wires"] = {k: [list(x) for x in v] for k, v in circuit.wires.items()}
    return st


def apply(circuit, st):
    """Put a state onto a freshly parsed circuit (things that no longer exist are simply skipped)."""
    st = st or {}
    for c in circuit.components:
        v = st.get("pos", {}).get(c.id)
        if v: c.pos = (int(v[0]), int(v[1]))
        c.facing = st.get("facing", {}).get(c.id, "east")
    for kind, pins in (("in", circuit.inputs), ("out", circuit.outputs)):
        for p in pins:
            v = st.get("pins", {}).get(f"{kind}:{p.name}")
            if v: p.pos = (int(v[0]), int(v[1]))
    sigs = set(circuit.signals())
    circuit.wires = {k: [list(x) for x in v] for k, v in st.get("wires", {}).items() if k in sigs}
    return circuit


def has_layout(st):
    return bool(st) and any(st.get(k) for k in ("pos", "pins", "wires", "facing"))


def merge(base, over):
    """over wins; used when old-style JSON carries its own layout."""
    out = {k: dict(base.get(k, {})) for k in ("pos", "pins", "wires", "facing")}
    for k in out: out[k].update((over or {}).get(k, {}))
    return out
