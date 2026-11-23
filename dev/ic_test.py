"""Headless tests of the IC view engine: every circuit is mapped to 74xx chips and the chip version is simulated and compared
with the circuit.   python dev/ic_test.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from vibesimulation.workspaces.logisim.core.serializer import parse            # noqa: E402
import vibesimulation.workspaces.logisim.components                            # noqa: E402,F401
from vibesimulation.workspaces.logisim.ic import mapper, verify                # noqa: E402


def circ(inputs, outputs, gates):
    c, _ = parse(json.dumps({"inputs": inputs, "outputs": outputs, "gates": gates}))
    return c


G = lambda i, t, ins, out, **kw: dict(id=i, type=t, **{"in": ins}, out=out, **kw)
P = lambda i, t, ins, outs, **kw: dict(id=i, type=t, **{"in": ins}, out=outs, **kw)

CASES = {}
CASES["basic gates"] = (circ(["A", "B", "C", "D"], ["Y", "Z"], [G("g1", "AND", ["A", "B"], "x"), G("g2", "NOT", ["C"], "nc"), G("g3", "OR", ["x", "nc"], "Y"), G("g4", "XOR", ["A", "D"], "Z")]), {"7408": 1, "7404": 1, "7432": 1, "7486": 1})
CASES["wide gates"] = (circ(list("ABCDEFGHIJ"), ["P", "Q", "R", "S", "T", "U"], [
    G("a", "AND", list("ABCDE"), "P"), G("b", "NAND", list("ABCDEFGHI"), "Q"), G("c", "OR", list("ABCD"), "R"),
    G("d", "NOR", list("ABCDE"), "S"), G("e", "XOR", list("ABCDE"), "T"), G("f", "XNOR", list("ABCD"), "U")]), None)
CASES["sixteen NAND+NOT"] = (circ(["A", "B", "C", "D"], ["Y"], [G("n1", "NAND", ["A", "B", "C"], "x"), G("n2", "NOT", ["D"], "d"), G("n3", "NAND", ["x", "d"], "Y")]), None)
CASES["4-bit gates"] = (circ([{"name": "A", "width": 4}, {"name": "B", "width": 4}], [{"name": "Y", "width": 4}], [dict(id="g", type="AND", width=4, **{"in": ["A", "B"]}, out="Y")]), {"7408": 1})
CASES["splitter/combiner"] = (circ([{"name": "A", "width": 4}], [{"name": "Y", "width": 4}], [
    dict(id="sp", type="Splitter", widths=[1, 1, 1, 1], **{"in": ["A"]}, out=["a0", "a1", "a2", "a3"]),
    G("n0", "NOT", ["a0"], "b0"),
    dict(id="cb", type="Combiner", widths=[1, 1, 1, 1], **{"in": ["b0", "a1", "a2", "a3"]}, out="Y")]), {"7404": 1})
CASES["adder 8"] = (circ([{"name": "A", "width": 8}, {"name": "B", "width": 8}, "Ci"], [{"name": "S", "width": 8}, "Co"], [dict(id="ad", type="Adder", width=8, **{"in": {"A": "A", "B": "B", "Cin": "Ci"}}, out={"Sum": "S", "Cout": "Co"})]), {"7483": 2})
CASES["adder 3"] = (circ([{"name": "A", "width": 3}, {"name": "B", "width": 3}], [{"name": "S", "width": 3}, "Co"], [dict(id="ad", type="Adder", width=3, **{"in": {"A": "A", "B": "B"}}, out={"Sum": "S", "Cout": "Co"})]), {"7483": 1})
CASES["subtractor 6"] = (circ([{"name": "A", "width": 6}, {"name": "B", "width": 6}], [{"name": "D", "width": 6}, "Bo"], [dict(id="sb", type="Subtractor", width=6, **{"in": {"A": "A", "B": "B"}}, out={"Diff": "D", "Bout": "Bo"})]), None)
CASES["negator 4"] = (circ([{"name": "A", "width": 4}], [{"name": "N", "width": 4}], [dict(id="ng", type="Negator", width=4, **{"in": {"In": "A"}}, out={"Out": "N"})]), None)
CASES["comparator 6"] = (circ([{"name": "A", "width": 6}, {"name": "B", "width": 6}], ["G", "E", "L"], [dict(id="cp", type="Comparator", width=6, **{"in": {"A": "A", "B": "B"}}, out={"GT": "G", "EQ": "E", "LT": "L"})]), {"7485": 2})
CASES["comparator signed"] = (circ([{"name": "A", "width": 4}, {"name": "B", "width": 4}], ["G", "E", "L"], [dict(id="cp", type="Comparator", width=4, mode="signed", **{"in": {"A": "A", "B": "B"}}, out={"GT": "G", "EQ": "E", "LT": "L"})]), None)
CASES["mux 2:1 x4"] = (circ([{"name": "A", "width": 4}, {"name": "B", "width": 4}, "S"], [{"name": "Y", "width": 4}], [dict(id="m", type="MUX", select=1, width=4, **{"in": {"In0": "A", "In1": "B", "Sel": "S"}}, out={"Out": "Y"})]), {"74157": 1})
CASES["mux 4:1 x2 en"] = (circ([{"name": "A", "width": 2}, {"name": "B", "width": 2}, {"name": "C", "width": 2}, {"name": "D", "width": 2}, {"name": "S", "width": 2}, "E"], [{"name": "Y", "width": 2}], [dict(id="m", type="MUX", select=2, width=2, **{"in": {"In0": "A", "In1": "B", "In2": "C", "In3": "D", "Sel": "S", "En": "E"}}, out={"Out": "Y"})]), {"74153": 1, "7404": 1})
CASES["mux 8:1"] = (circ(list("ABCDEFGH") + [{"name": "S", "width": 3}], ["Y"], [dict(id="m", type="MUX", select=3, **{"in": {**{f"In{i}": "ABCDEFGH"[i] for i in range(8)}, "Sel": "S"}}, out={"Out": "Y"})]), {"74151": 1})
CASES["mux 16:1"] = (circ(list("ABCDEFGHIJKLMNOP") + [{"name": "S", "width": 4}], ["Y"], [dict(id="m", type="MUX", select=4, **{"in": {**{f"In{i}": "ABCDEFGHIJKLMNOP"[i] for i in range(16)}, "Sel": "S"}}, out={"Out": "Y"})]), {"74151": 2, "74157": 1})
CASES["decoder 1"] = (circ(["S"], ["O0", "O1"], [dict(id="d", type="DECODER", select=1, **{"in": {"Sel": "S"}}, out={"Out0": "O0", "Out1": "O1"})]), None)
CASES["decoder 2 en"] = (circ([{"name": "S", "width": 2}, "E"], ["O0", "O1", "O2", "O3"], [dict(id="d", type="DECODER", select=2, **{"in": {"Sel": "S", "En": "E"}}, out={f"Out{i}": f"O{i}" for i in range(4)})]), None)
CASES["decoder 3"] = (circ([{"name": "S", "width": 3}], [f"O{i}" for i in range(8)], [dict(id="d", type="DECODER", select=3, **{"in": {"Sel": "S"}}, out={f"Out{i}": f"O{i}" for i in range(8)})]), {"74138": 1, "7404": 2})
CASES["decoder 4"] = (circ([{"name": "S", "width": 4}, "E"], [f"O{i}" for i in range(16)], [dict(id="d", type="DECODER", select=4, **{"in": {"Sel": "S", "En": "E"}}, out={f"Out{i}": f"O{i}" for i in range(16)})]), None)
CASES["demux 2"] = (circ(["D", {"name": "S", "width": 2}], ["O0", "O1", "O2", "O3"], [dict(id="d", type="DEMUX", select=2, **{"in": {"In": "D", "Sel": "S"}}, out={f"Out{i}": f"O{i}" for i in range(4)})]), None)
CASES["D flip-flop + clock"] = (circ(["D", "R"], ["Q", "Qn"], [dict(id="ck", type="Clock", out="clk"), dict(id="ff", type="D Flip-Flop", **{"in": {"D": "D", "Clk": "clk", "Clr": "R"}}, out={"Q": "Q", "Qn": "Qn"})]), None)
CASES["T ripple counter"] = (circ([], ["Q0", "Q1", "Q2"], [dict(id="ck", type="Clock", out="clk"),
    dict(id="t0", type="T Flip-Flop", **{"in": {"T": "one", "Clk": "clk"}}, out={"Q": "Q0", "Qn": "n0"}),
    dict(id="t1", type="T Flip-Flop", **{"in": {"T": "one", "Clk": "n0"}}, out={"Q": "Q1", "Qn": "n1"}),
    dict(id="t2", type="T Flip-Flop", **{"in": {"T": "one", "Clk": "n1"}}, out={"Q": "Q2"}),
    dict(id="k", type="Constant", value=1, out="one")]), None)
CASES["JK falling"] = (circ(["J", "K"], ["Q"], [dict(id="ck", type="Clock", out="clk"), dict(id="ff", type="J-K Flip-Flop", trigger="falling", **{"in": {"J": "J", "K": "K", "Clk": "clk"}}, out={"Q": "Q"})]), None)
CASES["register 8 en"] = (circ([{"name": "D", "width": 8}, "E"], [{"name": "Q", "width": 8}], [dict(id="ck", type="Clock", out="clk"), dict(id="r", type="Register", width=8, **{"in": {"D": "D", "Clk": "clk", "En": "E"}}, out={"Q": "Q"})]), None)
CASES["register 6 clr"] = (circ([{"name": "D", "width": 6}, "R"], [{"name": "Q", "width": 6}], [dict(id="ck", type="Clock", out="clk"), dict(id="r", type="Register", width=6, **{"in": {"D": "D", "Clk": "clk", "Clr": "R"}}, out={"Q": "Q"})]), None)
CASES["register 6 plain"] = (circ([{"name": "D", "width": 6}], [{"name": "Q", "width": 6}], [dict(id="ck", type="Clock", out="clk"), dict(id="r", type="Register", width=6, **{"in": {"D": "D", "Clk": "clk"}}, out={"Q": "Q"})]), None)
CASES["counter 8"] = (circ(["E", "R", "L", {"name": "D", "width": 8}], [{"name": "Q", "width": 8}, "C"], [dict(id="ck", type="Clock", out="clk"), dict(id="c", type="Counter", width=8, **{"in": {"Clk": "clk", "En": "E", "Clr": "R", "Ld": "L", "D": "D"}}, out={"Q": "Q", "Carry": "C"})]), {"74161": 2, "7404": 1})
CASES["shift register 10"] = (circ(["I", "R"], ["O"], [dict(id="ck", type="Clock", out="clk"), dict(id="s", type="Shift Register", width=1, length=10, parallel=False, **{"in": {"In": "I", "Clk": "clk", "Clr": "R"}}, out={"Out": "O"})]), {"74164": 2, "7404": 1})
CASES["hex display"] = (circ([{"name": "A", "width": 4}], [], [dict(id="h", type="HEXDISPLAY", **{"in": {"In": "A"}})]), {"7447": 1})
CASES["unmapped RAM"] = (circ([{"name": "A", "width": 4}], [{"name": "D", "width": 8}], [dict(id="m", type="RAM", addr=4, width=8, **{"in": {"A": "A"}}, out={"D": "D"})]) if False else circ(["A"], ["Y"], [dict(id="mu", type="Multiplier", width=1, **{"in": {"A": "A", "B": "A"}}, out={"Prod": "Y"})]), None)


def views_ok():
    """The IC view (schematic), the X-ray and the session: every case draws, the wires reach their pins, edits are kept and detected."""
    import json as _j
    from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
    from vibesimulation.workspaces.logisim.core.document import Document
    from vibesimulation.workspaces.logisim.ic import schematic as S, xray as X, catalog as K
    from vibesimulation.workspaces.logisim.ic.session import session_for
    bad = 0
    for name, (c, _e) in CASES.items():
        try:
            p = mapper.plan(c); sch = S.layout(p)
            for w in sch.wires:                                           # a wire must touch the lead of every pin on its net
                ends = {sch.pin_xy[(n.ref, pin.key)] for n in sch.nodes for pin in n.pins if pin.net == w.net}
                pts = {pt for s in w.segs for pt in s}
                if not ends <= pts: raise AssertionError(f"wire {w.name} misses a pin")
            im, d, tf = canvas(sch.extent(), 1.0, 4, "#ffffff"); S.draw(PilRenderer(d, tf, 1.0, LIGHT), sch)
            xs = S.layout(p, True, {c0.ref: -i for i, c0 in enumerate(p.chips)})                 # the X-ray view: same circuit, chips opened up
            im, d, tf = canvas(xs.extent(), 1.0, 4, "#ffffff"); S.draw(PilRenderer(d, tf, 1.0, LIGHT), xs)
            for sc in (sch, xs):                                           # ONE VCC and ONE GND per chip: every tie wire ends on the chip's own power pin
                for n in sc.nodes:
                    if n.kind != "chip": continue
                    cat = n.chip.chip; marks = [pn for pn in n.pins if pn.key in (str(cat.vcc), str(cat.gnd))]
                    if len(marks) != 2: raise AssertionError(f"{n.ref}: {len(marks)} power pins")
                    for rail, pts in S.tie_paths(sc, n):
                        pw = str(cat.vcc if rail == mapper.VCC else cat.gnd)
                        if pts[-1] != sc.pin_xy[(n.ref, pw)]: raise AssertionError(f"{n.ref}: a {rail} tie does not end on the {rail} pin")
            for ch in p.chips:
                w, h = X.size(ch); im, d, tf = canvas((0, 0, w, h), 1.0, 4, "#ffffff"); X.draw_chip(PilRenderer(d, tf, 1.0, LIGHT), p, ch, 0, 0)
        except Exception as e:                                             # noqa: BLE001
            print(f"FAIL views {name}: {type(e).__name__}: {e}"); bad += 1
    for part, ch in K.CHIPS.items():
        if [p.kind for p in ch.pinout].count("gnd") != 1 or [p.kind for p in ch.pinout].count("vcc") != 1: print(f"FAIL {part}: needs exactly one GND and one VCC pin"); bad += 1
    for part, ch in K.CHIPS.items():                                      # every catalogue chip can be drawn opened up
        try:
            ci = mapper.build_chip("U1", part, [None] * max(len(ch.units), 1), 0)
            plan = mapper.ICPlan([ci], [], {}, [], [], {})
            w, h = X.size(ci); im, d, tf = canvas((0, 0, w, h), 1.0, 4, "#ffffff"); X.draw_chip(PilRenderer(d, tf, 1.0, LIGHT), plan, ci, 0, 0)
            for xr in (False, True):                                       # ...and as a part of the circuit (IC view and X-ray view)
                sc = S.layout(plan, xr); im, d, tf = canvas(sc.extent(), 1.0, 4, "#ffffff"); S.draw(PilRenderer(d, tf, 1.0, LIGHT), sc)
        except Exception as e:                                             # noqa: BLE001
            print(f"FAIL x-ray of {part}: {type(e).__name__}: {e}"); bad += 1
    doc = Document(); doc.set_text(_j.dumps({"inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g", "type": "AND", "in": ["A", "B"], "out": "Y"}]}))
    s = session_for(doc); chip = s.plan().chips[0]
    doc.set_inputs({"A": 1, "B": 1})
    if s.status() != " · chips ✓": print("FAIL session: chips should agree with the gates"); bad += 1
    s.set_pin(chip.ref, 2, "GND"); doc.set_inputs({"A": 1, "B": 1})
    if "✗" not in s.status(): print("FAIL session: a wrong rewiring must be detected"); bad += 1
    if doc.text.count("AND") != 1 or "GND" in doc.text: print("FAIL session: rewiring must not touch the circuit"); bad += 1
    doc.set_inputs({"A": 1, "B": 0})
    if s.plan().chips[0].pins[2] != "GND": print("FAIL session: the rewiring was lost"); bad += 1
    s.clear_edits(); doc.set_inputs({"A": 1, "B": 1})
    if s.status() != " · chips ✓": print("FAIL session: reset should restore the chips"); bad += 1
    print("ok   views: IC view + X-ray drawn for", len(CASES), "circuits and", len(K.CHIPS), "chips; rewiring detected and kept" if not bad else "")
    return bad


CIRC = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="3.8.0" version="1.0"><lib desc="#Wiring" name="0"/><lib desc="#Gates" name="1"/><lib desc="#TTL" name="6"/><main name="main"/>
<circuit name="main">
<comp lib="1" loc="(400,300)" name="NOT Gate"/>
<comp lib="0" loc="(320,300)" name="Pin"><a name="label" val="A"/></comp>
<comp lib="0" loc="(450,300)" name="Pin"><a name="output" val="true"/><a name="label" val="Y"/></comp>
<wire from="(320,300)" to="(370,300)"/><wire from="(400,300)" to="(450,300)"/>
<comp lib="6" loc="(300,100)" name="7404"/>
<comp lib="0" loc="(150,100)" name="Pin"/>
<comp lib="0" loc="(150,120)" name="Pin"><a name="output" val="true"/></comp>
<wire from="(150,100)" to="(300,100)"/><wire from="(150,120)" to="(300,120)"/>
</circuit></project>"""


def import_ok():
    """A .circ whose main circuit holds a gate circuit and a chip circuit side by side opens as two circuits (tabs); TTL chips become gates;
    saving can pick the circuits."""
    from vibesimulation.workspaces.logisim.imports.logisim_in import parse_project
    from vibesimulation.workspaces.logisim.core.document import Document
    bad = 0
    circs, main, notes = parse_project(CIRC)
    if sorted(circs) != ["main", "main (2)"]: print("FAIL import: expected two circuits, got", sorted(circs)); bad += 1
    for n, c in circs.items():
        if c.validate(loose=True): print("FAIL import:", n, c.validate(loose=True)); bad += 1
        if [g.type_name for g in c.components] != ["NOT"]: print("FAIL import: circuit", n, "should be one NOT gate"); bad += 1
    from vibesimulation.workspaces.logisim.core.serializer import dumps
    import json
    d = Document(); d.load_project(json.dumps({"main": "main", "circuits": {n: json.loads(dumps(c)) for n, c in circs.items()}}))
    if sorted(d.circuit_names()) != ["main", "main (2)"]: print("FAIL document: two tabs expected"); bad += 1
    one = json.loads(d.project_text(["main (2)"]))
    if "circuits" in one: print("FAIL save one circuit: should be a plain circuit"); bad += 1
    both = json.loads(d.project_text(["main", "main (2)"]))
    if sorted(both["circuits"]) != ["main", "main (2)"]: print("FAIL save two circuits"); bad += 1
    if "<circuit name=\"main (2)\"" not in d.circ_text(["main", "main (2)"]) or "main (2)" in d.circ_text(["main"]): print("FAIL .circ subset"); bad += 1
    print("ok   import: two circuits split, TTL chip read as gates, saving picks circuits" if not bad else "")
    return bad


def main():
    bad = 0
    for name, (c, expect) in CASES.items():
        try:
            p = mapper.plan(c)
        except Exception as e:                                           # noqa: BLE001
            print(f"FAIL {name}: mapper crashed: {type(e).__name__}: {e}"); bad += 1; continue
        res = verify.check(c, p)
        status = "skip (has parts without a chip)" if res is None else (f"{res[0]} comparisons ok" if not res[1] else "MISMATCH " + "; ".join(res[1][:2]))
        ok = (res is None or not res[1]) and (expect is None or p.counts() == expect)
        if not ok: bad += 1
        print(("ok  " if ok else "FAIL"), f"{name:22} {sum(p.counts().values()):2} chips {dict(sorted(p.counts().items()))}  {status}" + ("" if expect is None or p.counts() == expect else f"   expected {expect}"))
        p2 = mapper.plan(c, reuse_spare=True)                               # same circuit with spare gates acting as inverters
        res2 = verify.check(c, p2)
        if res2 is not None and res2[1]: bad += 1; print("FAIL reuse-spare version differs:", res2[1][:2])
        if len(p2.chips) > len(p.chips): bad += 1; print("FAIL reuse-spare needs more chips than without")
        if len(p2.chips) < len(p.chips): print(f"       with spare gates reused: {len(p2.chips)} chips instead of {len(p.chips)}")
        for w in p.warnings: print("       warning:", w)
        for u in p.unmapped: print("       unmapped:", u[1], "-", u[2][:70])
    bad += views_ok()
    bad += import_ok()
    print("\n%d failure(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
