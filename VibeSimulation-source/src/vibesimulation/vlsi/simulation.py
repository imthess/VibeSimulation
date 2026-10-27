"""Running a design in time (the Run button): a testbench from the Testbench tab, or a generated one."""
from ..verilog.lexer import VError
from ..verilog.tb import run_testbench
from ..verilog.tb.result import TBResult
from .stimulus import generate_testbench
from .testbench import testbench_names


def run(doc, cycles=64, period=10, mode="random", max_time=200000, use_written=True):
    """-> (TBResult, text that was run). With a testbench written by the user it is used (use_written); otherwise one is made."""
    design = doc.verilog_project()
    if not design.strip():
        r = TBResult(); r.error = VError("there is no design to simulate yet", 1); return r, ""
    written = doc.tb_text if use_written and testbench_names(doc.tb_text) else ""
    if written:
        text = design + "\n" + written; top = testbench_names(written)[-1]
    else:
        tb = generate_testbench(doc.cur, doc.circuit, cycles, period, mode)
        text = design + "\n" + tb; top = "vs_auto_tb"
    return run_testbench(text, top=top, max_time=max_time), text
