"""The Verilog workspace: write a circuit as Verilog and see it as a circuit, a truth table and waveforms.

- ``workspace.py``, ``menus.py``, ``actions.py``   the page (Verilog | Circuit | Truth table panes), its menus, File actions
- ``editor/``       pane 1: Verilog editor, syntax colours, explorer panel, snippet templates
- ``circuit/``      pane 2: the circuit drawn from the text
- ``truth_table/``  pane 3: the truth table
- ``simulation/``   bottom dock: Problems, Output, Waveform (radix, cursors, VCD), Run, simulation settings window
- ``project/``      the document (Facade over compiler, snapshots, writer), testbench run, simulation settings, VCD writer
- ``engine/``       the language: lexer, preprocessor, parser, elaboration to circuits, lint (+ warning codes), testbench simulator
"""
