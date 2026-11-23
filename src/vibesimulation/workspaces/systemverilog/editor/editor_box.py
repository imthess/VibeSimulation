"""SystemVerilog pane 1: the editor. Everything but the title, the hints and the colours is the Verilog editor's."""
from vibesimulation.workspaces.verilog.editor.verilog_box import VerilogView
from vibesimulation.workspaces.systemverilog.editor.highlight import SystemVerilogHighlighter
class SystemVerilogView(VerilogView):
    number, title, hint = None, "SystemVerilog", "lowered to Verilog, then drawn as a circuit"
    NAME = "SystemVerilog"
    HIGHLIGHTER = SystemVerilogHighlighter
    TB_HINT = "Testbench: write a module with `initial` / `always`, #delays, $display, $finish (assert and $error work too). Press ▶ Run below."
