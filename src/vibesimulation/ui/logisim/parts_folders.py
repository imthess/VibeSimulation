"""The folder tree of the Parts palette, in the order of Logisim-evolution's explorer panel.

Each entry is (label shown, registry type name). A type name of None means "Logisim has this part, VibeSimulation
cannot simulate it yet": it is listed (greyed) so the folders look like Logisim's, but it cannot be added.
Parts that exist in the registry but are not listed here are put in an "Other" folder automatically.
"""

FOLDERS = [
    ("Wiring", [("Splitter", "Splitter"), ("Combiner", "Combiner"), ("Pin", None), ("Probe", "Probe"), ("Tunnel", None), ("Pull Resistor", None),
                ("Clock", "Clock"), ("Constant", "Constant"), ("Power", "Power"), ("Ground", "Ground"), ("Transistor", None),
                ("Transmission Gate", None), ("Bit Extender", "BitExtender")]),
    ("Gates", [("NOT Gate", "NOT"), ("Buffer", "BUFFER"), ("AND Gate", "AND"), ("OR Gate", "OR"), ("NAND Gate", "NAND"), ("NOR Gate", "NOR"),
               ("XOR Gate", "XOR"), ("XNOR Gate", "XNOR"), ("Odd Parity", "ODDPARITY"), ("Even Parity", "EVENPARITY"),
               ("Controlled Buffer", None), ("Controlled Inverter", None)]),
    ("Plexers", [("Multiplexer", "MUX"), ("Demultiplexer", "DEMUX"), ("Decoder", "DECODER"), ("Priority Encoder", "ENCODER"),
                 ("Bit Selector", "BITSELECTOR")]),
    ("Arithmetic", [("Adder", "Adder"), ("Subtractor", "Subtractor"), ("Multiplier", "Multiplier"), ("Divider", "Divider"), ("Negator", "Negator"),
                    ("Comparator", "Comparator"), ("Shifter", "Shifter"), ("Bit Adder", "BitAdder"), ("Bit Finder", "BitFinder")]),
    ("Memory", [("D Flip-Flop", "D Flip-Flop"), ("T Flip-Flop", "T Flip-Flop"), ("J-K Flip-Flop", "J-K Flip-Flop"), ("S-R Flip-Flop", "S-R Flip-Flop"), ("Register", "Register"),
                ("Counter", "Counter"), ("Shift Register", "Shift Register"), ("Random", None), ("RAM", "RAM"), ("ROM", "ROM")]),
    ("Input/Output", [("Button", None), ("Joystick", None), ("Keyboard", None), ("LED", "LED"), ("7-Segment Display", "SEVENSEG"),
                      ("Hex Digit Display", "HEXDISPLAY"), ("LED Bar", None), ("DOT Matrix", None), ("TTY", None)]),
    ("TTL", [("7400-series chips (7400, 7402, 7404, 7408 …)", None)]),
    ("TCL", [("TCL components", None)]),
    ("BFH mega functions", [("BFH mega functions", None)]),
    ("Input/Output Extra", [("DIP Switch", None), ("Rotary Encoder", None), ("RGB LED", None), ("Binary to BCD / BCD to 7-segment", None)]),
    ("System On a Chip", [("Processors, bus and peripherals", None)]),
]
