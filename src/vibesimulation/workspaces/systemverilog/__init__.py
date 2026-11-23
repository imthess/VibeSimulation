"""The SystemVerilog tab. It reuses the Verilog window (editor, circuit, truth table, bottom dock) and changes only what differs.

- ``workspace.py``, ``actions.py``   the page and its File actions (.sv files); Template Method over the Verilog page
- ``editor/``   pane 1: editor with SystemVerilog highlighting, explorer panel, snippet templates
- ``core/``     lowering of SystemVerilog to the Verilog subset the Verilog core understands (one file per feature in ``features/``); Adapter: ``core/document.py``
"""
