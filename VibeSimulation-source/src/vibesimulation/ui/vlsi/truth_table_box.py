"""VLSI pane 3: the truth table of the circuit the Verilog describes (same table as Logisim's, on the VLSI document)."""
from ..logisim.truth_table import TableView


class VlsiTableView(TableView):
    number, title, hint = None, "Truth table", ""
