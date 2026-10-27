"""The VLSI section of the window: write a circuit as Verilog and see it as a circuit.

One file per box or function:
- ``workspace.py``        the page: Verilog | Circuit | Truth table panes
- ``verilog_box.py``      pane 1, the Verilog editor
- ``highlight.py``        Verilog syntax colours (used by the editor)
- ``circuit_box.py``      pane 2, the circuit drawn from the Verilog (read-only for logic)
- ``truth_table_box.py``  pane 3, the truth table
- ``side_panel.py``       the explorer next to the activity bar (modules, templates, library cells)
- ``templates.py``        the snippet texts the explorer inserts
- ``actions.py``          File actions (open / save a .v file, downloads)
- ``menus.py``            the top-bar menus of this page
"""
