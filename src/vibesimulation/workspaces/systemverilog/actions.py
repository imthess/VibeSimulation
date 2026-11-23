"""File actions of the SystemVerilog page: the VLSI actions with .sv files."""
from vibesimulation.workspaces.systemverilog.core.samples import BLANK
from vibesimulation.workspaces.verilog.actions import VlsiActions
class SystemVerilogActions(VlsiActions):
    LABELS = {"open": "Open SystemVerilog file (.sv)…", "save": "Save SystemVerilog…", "export": "SystemVerilog (.sv)"}
    EXT, DIALOG_EXTS, BLANK = ".sv", [".sv", ".svh", ".v", ".txt"], BLANK
