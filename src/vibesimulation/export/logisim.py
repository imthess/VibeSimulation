"""Circuit -> Logisim-evolution 3.8 ``.circ`` file."""
from xml.sax.saxutils import escape, quoteattr

from ..components.gates.gate_base import Gate
from ..layout.engine import LayoutEngine

LIB = {"Wiring": 0, "Gates": 1, "Plexers": 2, "Arithmetic": 3, "Memory": 4, "Input/Output": 5}

HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="3.8.0" version="1.0">
  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Plexers" name="2"/>
  <lib desc="#Arithmetic" name="3"/>
  <lib desc="#Memory" name="4"/>
  <lib desc="#I/O" name="5"/>
  <lib desc="#TTL" name="A"/>
  <lib desc="#TCL" name="7"/>
  <lib desc="#Base" name="8"/>
  <lib desc="#BFH-Praktika" name="9"/>
  <lib desc="#Input/Output-Extra" name="B"/>
  <lib desc="#Soc" name="C"/>
  <main name="@MAIN@"/>
  <options>
    <a name="showgrid" val="true"/>
    <a name="simulate" val="true"/>
    <a name="showghosts" val="true"/>
    <a name="zoom" val="1.0"/>
  </options>
  <mappings>
    <tool lib="8" map="Button2" name="Poke Tool"/>
    <tool lib="8" map="Button3" name="Menu Tool"/>
    <tool lib="8" map="Ctrl Button1" name="Menu Tool"/>
  </mappings>
  <toolbar>
    <tool lib="8" name="Poke Tool"/>
    <tool lib="8" name="Edit Tool"/>
    <tool lib="8" name="Wiring Tool"/>
    <tool lib="8" name="Text Tool"/>
    <sep/>
    <tool lib="0" name="Pin">
      <a name="tristate" val="false"/>
    </tool>
    <tool lib="0" name="Pin">
      <a name="facing" val="west"/>
      <a name="output" val="true"/>
    </tool>
    <sep/>
    <tool lib="1" name="NOT Gate"/>
    <tool lib="1" name="AND Gate"/>
    <tool lib="1" name="OR Gate"/>
    <tool lib="1" name="XOR Gate"/>
    <tool lib="1" name="NAND Gate"/>
    <tool lib="1" name="NOR Gate"/>
    <sep/>
    <tool lib="4" name="D Flip-Flop"/>
    <tool lib="4" name="Register"/>
  </toolbar>
"""


def _open(name):
    return f'  <circuit name={quoteattr(name)}>\n    <a name="circuit" val={quoteattr(name)}/>\n    <a name="appearance" val="classic"/>\n'


HEADER = HEAD.replace("@MAIN@", "main") + _open("main")        # (kept for the dev tests: a file start that ends inside the main circuit)
FOOTER = "  </circuit>\n</project>\n"


def _comp(lib, x, y, name, **attrs):
    a = "".join((f'      <a name="{k}">{escape(v[1])}</a>\n' if isinstance(v, tuple) else f'      <a name="{k}" val={quoteattr(str(v))}/>\n') for k, v in attrs.items())
    return f'    <comp lib="{lib}" loc="({x},{y})" name="{name}">\n{a}    </comp>\n'


def _comp_sub(x, y, name, **attrs):
    a = "".join(f'      <a name="{k}" val={quoteattr(str(v))}/>\n' for k, v in attrs.items())
    return f'    <comp loc="({x},{y})" name={quoteattr(name)}>\n{a}    </comp>\n'


def circuit_xml(name, layout, circuit):
    _no_rough(layout)
    body = _open(name)
    outs = {o.name for o in circuit.outputs}
    for pin, x, y in layout.inputs:
        a = {"appearance": "NewPins", "label": pin.name, "tristate": "false"}
        if pin.width != 1: a["width"] = pin.width
        body += _comp(0, x, y, "Pin", **a)
    for pl in layout.parts:
        c = pl.comp
        attrs = dict(c.logisim_attrs())
        sigs = [s for s in c.outs.values() if s]
        if isinstance(c, Gate) and len(sigs) == 1 and sigs[0] not in outs:
            attrs["label"] = sigs[0]          # name internal gate outputs so they show in Logisim's own tables
        if c.facing != "east": attrs["facing"] = c.facing          # the way the user turned the part
        if getattr(c, "is_sub", False): body += _comp_sub(pl.x, pl.y, c.attrs["circuit"], **attrs); continue
        body += _comp(LIB[c.library], pl.x, pl.y, c.logisim_name, **attrs)
    for pin, x, y in layout.outputs:
        a = {"appearance": "NewPins", "facing": "west", "label": pin.name, "output": "true"}
        if pin.width != 1: a["width"] = pin.width
        body += _comp(0, x, y, "Pin", **a)
    for x1, y1, x2, y2, _ in layout.wires:
        body += f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>\n'
    return body + "  </circuit>\n"


def _no_rough(layout):
    if getattr(layout, "rough", False): raise ValueError("This circuit is too large for the automatic wire layout, so it cannot be written as a .circ file with clean wires.")


def layout_to_xml(layout, circuit, name="main"):
    _no_rough(layout)
    return HEAD.replace("@MAIN@", escape(name)) + circuit_xml(name, layout, circuit) + "</project>\n"


def to_circ(circuit, name="main"):
    """Lay the circuit out and return the .circ text (raises ValueError if it cannot be drawn)."""
    return layout_to_xml(LayoutEngine().build(circuit), circuit, name)


def project_to_circ(circuits, main):
    """circuits: {name: Circuit with its layout applied}. Subcircuits are written first."""
    order, seen = [], set()

    def visit(n):
        if n in seen: return
        seen.add(n)
        for c in circuits[n].components:
            if getattr(c, "is_sub", False) and c.attrs["circuit"] in circuits: visit(c.attrs["circuit"])
        order.append(n)
    for n in circuits: visit(n)
    return HEAD.replace("@MAIN@", escape(main)) + "".join(circuit_xml(n, LayoutEngine().build(circuits[n]), circuits[n]) for n in order) + "</project>\n"
