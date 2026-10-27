"""Running a circuit that remembers things (Logisim's simulator, in small).

Sequential parts (flip-flops, registers, counters, shift registers, the clock) keep a state dict. ``settle`` does what
Logisim does after every change: work out all signals, let every part that sees a clock edge (or an asynchronous
clear/preset) take its new state - all parts at the same moment, from the values *before* the edge - and repeat
until nothing changes any more. That is what makes ripple counters (one flip-flop clocking the next) work.
"""

LIMIT = 200


def fresh(circuit, old=None):
    """State for every sequential part of the circuit; parts that already have a matching state keep it."""
    new = {}
    for c in circuit.flat().components:
        if c.sequential:
            sig = c.sim_signature(); o = (old or {}).get(c.id)
            new[c.id] = o if o is not None and o.get("_sig") == sig else dict(c.init_state(), _sig=sig)
    return new


def settle(circuit, invals, st, tick=0, limit=LIMIT):
    """Returns (signal values, oscillating?). st (the state dict) is updated in place."""
    circuit = circuit.flat()
    seq = [c for c in circuit.components if c.sequential]
    if not seq: return circuit.simulate(invals), False
    for _ in range(limit):
        v = circuit.simulate(invals, st)
        new = {}
        for c in seq:
            args = {p.name: (v.get(c.ins[p.name]) if c.ins.get(p.name) is not None else p.default) for p in c.in_ports()}
            new[c.id] = c.step(dict(st[c.id]), args, tick)
        if all(new[c.id] == st[c.id] for c in seq): return v, False
        st.update(new)
    return circuit.simulate(invals, st), True


def edge(st, clk, trigger):
    """Logisim's ClockState.updateClock: remember the clock value, say whether the part is triggered now."""
    old, st["clk"] = st.get("clk"), clk
    if trigger == "falling": return old == 1 and clk == 0
    if trigger == "high": return clk == 1
    if trigger == "low": return clk == 0
    return old == 0 and clk == 1
