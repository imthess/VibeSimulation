"""The SystemVerilog page: SystemVerilog, Circuit and Truth table side by side (the VLSI page with another editor and document)."""
from vibesimulation.workspaces.verilog.workspace import VlsiPage
from vibesimulation.workspaces.systemverilog.editor.editor_box import SystemVerilogView
class SystemVerilogPage(VlsiPage):
    KEY = "systemverilog"
    NAMES = {"verilog": "SystemVerilog", "circuit": "Circuit", "table": "Truth table"}
    DOC = "sdoc"
    EDITOR_VIEW = SystemVerilogView
