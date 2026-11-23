from geo import *
items = [(0,"Pin",{}),(0,"Constant",{}),(0,"Splitter",{}),(0,"Probe",{}),(1,"Buffer",{}),(1,"XOR Gate",{}),(1,"Odd Parity",{}),(1,"Even Parity",{}),
      (2,"Multiplexer",{}),(2,"Demultiplexer",{}),(2,"Decoder",{}),(2,"Priority Encoder",{}),(2,"Bit Selector",{}),
      (3,"Adder",{}),(3,"Subtractor",{}),(3,"Multiplier",{}),(3,"Divider",{}),(3,"Negator",{}),(3,"Comparator",{}),(3,"Shifter",{}),(3,"Bit Adder",{}),(3,"Bit Finder",{}),
      (5,"LED",{}),(5,"7-Segment Display",{}),(5,"Hex Digit Display",{}),(5,"Button",{}),(5,"DipSwitch",{})]
for it in items:
    r = dump([it])
    print(it[1], "->", "FAIL" if any("Exception" in l or "at com" in l for l in r) or not r else "ok")
    if r and r[0].startswith("COMP"): print("  ", r[0][:200])
