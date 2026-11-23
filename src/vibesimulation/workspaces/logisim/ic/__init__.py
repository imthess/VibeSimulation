"""IC view: turns a Logisim-style circuit into real 74xx chips and shows how to wire them on a breadboard.

- ``catalog``    every chip of Logisim-evolution 5.0.0's TTL library (title, pinout, functional units)
- ``mapper``     circuit -> chips (which ICs, how many, which pin goes to which signal)
- ``verify``     behaviour models of the chips, to prove the chip version works like the drawn circuit
- ``breadboard`` the breadboard picture (drawn through the shared Renderer, so screen and PNG look the same)
- ``report``     bill of materials, wiring list and netlist as text / CSV
- ``view``       the "IC view" window
"""
