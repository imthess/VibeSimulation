"""The Logisim tab (digital logic). ``workspace.py`` is the page; everything it needs lives in this folder:

- ``core/``         the circuit model: parts and wires, JSON, simulation, undo commands, ``Document``
- ``components/``   one file per part (gates, wiring, plexers, arithmetic, io, memory) and the part registry
- ``layout/``       placement of parts and wires, and the painter that draws a circuit
- ``circuit/``      the circuit pane (drawing, dragging, parts palette, memory editor)
- ``json_view/``    the JSON pane        - ``truth_table/``  the truth-table pane
- ``imports/``      read a Logisim ``.circ`` file          - ``export/``  write ``.circ``, PDF report and PNG picture

Verilog and SystemVerilog reuse this model, parts and drawing, so they import from here."""
