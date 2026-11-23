import subprocess, sys, re, json
sys.path.insert(0, ".")
HEADER = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../new/base.py")).read().split('HEADER = """')[1].split('"""')[0]
FOOT = "  </circuit>\n</project>\n"
def gen(items):
    body = ""; x = 200
    for i, (lib, name, attrs) in enumerate(items):
        a = "".join(f'      <a name="{k}" val="{v}"/>\n' for k, v in attrs.items())
        body += f'    <comp lib="{lib}" loc="({x},{300 + (i % 2) * 400})" name="{name}">\n{a}    </comp>\n'
        x += 250 if i % 2 else 0
    return HEADER + body + FOOT
def dump(items, path="geo.circ"):
    open(path, "w").write(gen(items))
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "logisim.jar:.", "Dump", path], capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l.startswith(("COMP", "  END"))] + ([out.stderr[-400:]] if "Exception" in out.stderr else [])
if __name__ == "__main__":
    items = [(0,"Pin",{}),(0,"Constant",{}),(0,"Splitter",{}),(0,"Probe",{}),(1,"Buffer",{}),(1,"XOR Gate",{}),(1,"Odd Parity",{}),(1,"Even Parity",{}),
      (2,"Multiplexer",{}),(2,"Demultiplexer",{}),(2,"Decoder",{}),(2,"Priority Encoder",{}),(2,"Bit Selector",{}),
      (3,"Adder",{}),(3,"Subtractor",{}),(3,"Multiplier",{}),(3,"Divider",{}),(3,"Negator",{}),(3,"Comparator",{}),(3,"Shifter",{}),(3,"Bit Adder",{}),(3,"Bit Finder",{}),
      (5,"LED",{}),(5,"7-Segment Display",{}),(5,"Hex Digit Display",{}),(5,"Button",{}),(5,"DipSwitch",{})]
    for l in dump(items): print(l)
