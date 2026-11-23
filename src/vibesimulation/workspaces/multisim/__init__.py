"""The Multisim tab (analog circuits). ``workspace.py`` is the page; everything it needs lives in this folder:

- ``core/``         the circuit model: ``netlist.py`` (JSON, validation, SPICE text), ``solver.py`` (DC), ``document.py``, ``units.py``
- ``analysis/``     AC, transient, noise, thermal, Monte Carlo, sweeps, measurements, meters, scope
- ``components/``   the parts: ``basic.py`` (R, C, L, sources ...) and ``active.py`` (diodes, transistors, op-amps ...)
- ``layout/``       schematic placement and wire stretching (``schematic_layout.py``), the painter (``painter.py``)
- ``schematic/``    the schematic pane          - ``json_view/``  the JSON pane          - ``results/``  DC / AC / transient result panels
- ``imports/``      read a SPICE netlist (``.cir``)          - ``export/``  PDF report and PNG picture"""
