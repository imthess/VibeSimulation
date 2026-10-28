"""The VLSI section's model: circuits that are written as Verilog.

Files
- ``document.py``  VlsiDocument: the Document of this section (a Facade over the pieces below).
- ``compiler.py``  Verilog text -> checked circuits (no state, no UI).
- ``snapshots.py`` remembers the Verilog the user typed, as long as the circuit is still what that text produced (Memento).
- ``writer.py``    circuit -> Verilog text, cached.
- ``samples.py``   the starter design.
The language itself (lexer, parser, elaborator, emitter) lives in ``vibesimulation.verilog``.
"""
