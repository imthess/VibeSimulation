"""The SystemVerilog section of the window. It reuses the VLSI page (editor, circuit, truth table, bottom dock) and changes only what differs.

One file per box or function (design patterns: Template Method for the page / explorer / actions, which the VLSI classes define and these
override; Adapter for the document, see ``vibesimulation.systemverilog.document``):
- ``workspace.py``   the page: SystemVerilog | Circuit | Truth table panes
- ``editor_box.py``  pane 1, the editor (SystemVerilog highlighting, its own title and hints)
- ``highlight.py``   SystemVerilog syntax colours (the Verilog colours plus the new words)
- ``side_panel.py``  the explorer next to the activity bar (modules, SystemVerilog snippets, library cells)
- ``templates.py``   the snippet texts
- ``actions.py``     File actions (.sv files)
"""
