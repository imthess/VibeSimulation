"""The explorer of the SystemVerilog page: the VLSI explorer with SystemVerilog snippets and its own document."""
from vibesimulation.workspaces.verilog.editor.side_panel import VlsiExplorer
from vibesimulation.workspaces.systemverilog.editor.templates import TEMPLATES
class SystemVerilogExplorer(VlsiExplorer):
    DOC, PAGE, TEMPLATES = "sdoc", "systemverilog", TEMPLATES
    NEW_MODULE = "module {n} (\n  input  logic a,\n  output logic y\n);\n  assign y = a;\nendmodule\n"
