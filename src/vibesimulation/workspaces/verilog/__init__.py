"""The Verilog tab: write a circuit as Verilog and see it as a circuit, a truth table and waveforms.

- ``workspace.py``, ``menus.py``, ``actions.py``   the page (Verilog | Circuit | Truth table panes), its menus, File actions
- ``core/``         the language: lexer, preprocessor, parser, elaboration to circuits, lint (+ warning codes), testbench simulator (``tb/``)
- ``project/``      the document (Facade over compiler, snapshots), testbench run, simulation settings
- ``export/``       ``emit.py`` (circuit to Verilog), ``writer.py`` (save files), ``vcd.py`` (waveform dump)
- ``editor/``       pane 1: Verilog editor, syntax colours, explorer panel, snippet templates
- ``circuit/``      pane 2: the circuit drawn from the text (uses the Logisim model, parts and drawing)
- ``truth_table/``  pane 3: the truth table
- ``simulation/``   bottom dock: Problems, Output, Waveform (radix, cursors, VCD), Run, simulation settings window
"""
