"""The SystemVerilog workspace. It reuses the Verilog window (editor, circuit, truth table, bottom dock) and changes only what differs.

- ``workspace.py``, ``actions.py``   the page and its File actions (.sv files); Template Method over the Verilog page
- ``editor/``   pane 1: editor with SystemVerilog highlighting, explorer panel, snippet templates
- ``engine/``   lowering of SystemVerilog to the Verilog subset the engine understands (one file per feature in ``features/``); Adapter: ``engine/document.py``
"""
