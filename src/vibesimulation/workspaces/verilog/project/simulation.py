"""Running a design in time (the Run button): a testbench from the Testbench tab, or a generated one."""
from vibesimulation.workspaces.verilog.core.lexer import VError
from vibesimulation.workspaces.verilog.core.tb import run_testbench
from vibesimulation.workspaces.verilog.core.tb.result import TBResult
from vibesimulation.workspaces.verilog.project.stimulus import generate_testbench
from vibesimulation.workspaces.verilog.project.testbench import testbench_names
def run(doc, cycles=None, period=None, mode=None, max_time=None, use_written=True):
    """-> (TBResult, text that was run). With a testbench written by the user it is used (use_written); otherwise one is made."""
    sim = doc.sim_settings; cycles = cycles or sim.cycles; period = period or sim.period; mode = mode or sim.stimulus; max_time = max_time or sim.max_time
    design = doc.verilog_project()
    if not design.strip():
        r = TBResult(); r.error = VError("there is no design to simulate yet", 1); return r, ""
    written = doc.tb_text if use_written and testbench_names(doc.tb_text, doc.prepare) else ""
    if written:
        text = doc.prepare(design + "\n" + written); top = testbench_names(written, doc.prepare)[-1]
    else:
        tb = generate_testbench(doc.cur, doc.circuit, cycles, period, mode)
        text = doc.prepare(design) + "\n" + tb; top = "vs_auto_tb"
    if sim.top:                                                  # the user named the module to simulate (like iverilog -s / xelab <top>)
        top = sim.top
    return run_testbench(text, top=top, max_time=max_time), text
