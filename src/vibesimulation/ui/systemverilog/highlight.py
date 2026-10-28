"""SystemVerilog syntax colours: the Verilog colours plus the words SystemVerilog adds."""
from ..vlsi import highlight as V

SV_WORDS = frozenset(("logic bit byte shortint int longint enum struct union packed typedef package endpackage import export always_comb always_ff always_latch "
                      "unique unique0 priority inside return void assert break continue do foreach var const static final interface endinterface modport "
                      "class endclass program endprogram timeunit timeprecision").split())


class SystemVerilogHighlighter(V.VerilogHighlighter):
    WORDS = V.KEYWORDS | SV_WORDS
