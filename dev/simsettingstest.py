"""Verilog / SystemVerilog simulator-style features without a window: preprocessor, VCD, settings and command lines, warning codes, Run with settings."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.workspaces.verilog.engine.lexer import VError
from vibesimulation.workspaces.verilog.engine import preproc, lintcodes
from vibesimulation.workspaces.verilog.project.document import VlsiDocument
from vibesimulation.workspaces.verilog.project import simulation
from vibesimulation.workspaces.verilog.project.vcd import to_vcd, parse_vcd
from vibesimulation.workspaces.verilog.project.simsettings import SimSettings, parse_defines, format_defines
from vibesimulation.workspaces.systemverilog.engine.document import SvDocument
ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def raises(f):
    try: f(); return None
    except VError as e: return e.msg
# --- preprocessor
T = "`define W 4\n`define MAX(a,b) ((a)>(b)?(a):(b))\n`timescale 1ns/1ps\nmodule m(input [`W-1:0] a, output y);\n`ifdef FAST\nassign y = a[0];\n`else\nassign y = `MAX(a[0],a[1]); // `W stays\n`endif\nendmodule\n"
preproc.Config.set()
r = preproc.preprocess(T); chk("line count unchanged", r.count("\n") == T.count("\n")); chk("macro and function-like macro expanded", "[4-1:0]" in r and "((a[0])>(a[1])?(a[0]):(a[1]))" in r)
chk("`else branch taken without -DFAST", "assign y = a[0];" not in r and "`W stays" in r); chk("timescale passes through", "`timescale 1ns/1ps" in r)
preproc.Config.set({"FAST": "1"}); r = preproc.preprocess(T); chk("-DFAST takes the `ifdef branch", "assign y = a[0];" in r and "MAX" not in r.split("endmodule")[0].split("assign y")[1][:5] or "assign y = a[0];" in r)
preproc.Config.set()
chk("`ifndef / `elsif", "A" in preproc.preprocess("`define Z\n`ifndef Z\nX\n`elsif Z\nA\n`else\nB\n`endif\n").split("\n")[4])
chk("undefined macro is an error with its line", "`NOPE" in (raises(lambda: preproc.preprocess("module m;\nwire w = `NOPE;\nendmodule")) or ""))
chk("missing `endif is an error", raises(lambda: preproc.preprocess("`ifdef A\nx")) is not None)
chk("wrong macro argument count is an error", raises(lambda: preproc.preprocess("`define F(a,b) a+b\nwire w = `F(1);")) is not None)
d = tempfile.mkdtemp(); open(os.path.join(d, "defs.vh"), "w").write("`define BITS 8\n// comment\nparameter P = 3;\n")
r = preproc.preprocess('`include "defs.vh"\nwire [`BITS-1:0] x;', {}, [d]); chk("`include found through -I, defines inside it work, lines kept", "parameter P = 3;" in r.split("\n")[0] and "[8-1:0]" in r and r.count("\n") == 1)
chk("missing include names the fix", "Include folders" in (raises(lambda: preproc.preprocess('`include "nope.vh"', {}, [])) or ""))
# --- the design compiles with macros
doc = VlsiDocument(); doc.apply_settings(SimSettings(defines={"W": "4"}))
errs = doc.set_verilog("`define N 2\nmodule andn(input [`N-1:0] a, output y);\nassign y = &a;\nendmodule\n"); chk("Verilog with `define compiles", not errs and doc.valid)
chk("the user's text is kept as typed", "`define N 2" in doc.verilog())
sv = SvDocument(); errs = sv.set_verilog("`define N 2\nmodule andn(input logic [`N-1:0] a, output logic y);\n  assign y = &a;\nendmodule\n"); chk("SystemVerilog with `define compiles", not errs and sv.valid)
# --- run with settings
doc = VlsiDocument(); doc.new_blank("module inv(input a, output y);\nassign y = ~a;\nendmodule\n"); doc.apply_settings(SimSettings(cycles=5, period=10, stimulus="count"))
res, text = simulation.run(doc); chk("generated run uses the cycles setting", res.error is None and res.end_time >= 40 and res.end_time <= 80)
doc.apply_settings(SimSettings(cycles=5, period=10, max_time=25)); res, _ = simulation.run(doc); chk("time limit stops the run", res.truncated or res.end_time <= 30)
doc.apply_settings(SimSettings(top="nope")); res, _ = simulation.run(doc); chk("an unknown top module is reported", res.error is not None and "nope" in res.error.msg)
doc.apply_settings(SimSettings())
# --- VCD
res, _ = simulation.run(doc, cycles=4); v = to_vcd(res, "1ns", date=False)
chk("VCD has header, scope, vars", all(k in v for k in ("$timescale 1ns $end", "$scope module top $end", "$enddefinitions $end", "$var wire 1")))
w, waves = parse_vcd(v); chk("VCD round trip keeps every signal", set(waves) == {n for n in res.order if n in res.waves})
chk("VCD round trip keeps every value change", all([(int(t), x) for t, x in res.waves[n]] == waves[n] for n in waves))
# --- settings / commands
s = SimSettings(top="tb", standard="2012", defines={"W": "8", "FAST": ""}, incdirs=["inc"], lint_off=["WIDTH"]); cmds = s.commands(files=("a.sv",), sv=True)
chk("iverilog line", cmds["Icarus Verilog (iverilog + vvp)"][0].startswith("iverilog -g2012") and "-DW=8" in cmds["Icarus Verilog (iverilog + vvp)"][0] and "-Iinc" in cmds["Icarus Verilog (iverilog + vvp)"][0] and "-s tb" in cmds["Icarus Verilog (iverilog + vvp)"][0])
chk("verilator line", "--top-module tb" in cmds["Verilator"][0] and "-Wno-WIDTH" in cmds["Verilator"][0] and "--language 1800-2017" in cmds["Verilator"][0])
chk("xsim lines", cmds["Vivado xsim"][0].startswith("xvlog -sv") and "xelab tb" in cmds["Vivado xsim"][1])
chk("settings round trip", SimSettings.from_dict(s.to_dict()) == s); chk("bad settings are caught", SimSettings(cycles=0).problems() and not SimSettings().problems())
chk("define parsing", parse_defines("-DA=1 B\nC=x") == {"A": "1", "B": "", "C": "x"} and parse_defines(format_defines({"A": "1", "B": ""})) == {"A": "1", "B": ""})
try: parse_defines("9x"); bad = False
except ValueError: bad = True
chk("bad macro name rejected", bad)
# --- warning codes
doc = VlsiDocument(); doc.apply_settings(SimSettings())
doc.set_verilog("module w(input [7:0] a, output [3:0] y, output z);\nassign y = a;\nassign z = a[0];\nendmodule\n")
ws = [m for s_, ln, m in doc.problems if s_ == "warning"]; chk("warnings carry a Verilator-style code", ws and all(m.startswith("[") for m in ws) and any(m.startswith("[WIDTH]") for m in ws))
doc.apply_settings(SimSettings(lint_off=["WIDTH"])); doc.set_verilog("module w(input [7:0] a, output [3:0] y, output z);\nassign y = a;\nassign z = a[0];\nendmodule\n")
chk("switching a code off hides it", not any(m.startswith("[WIDTH]") for _, _, m in doc.problems))
doc.apply_settings(SimSettings()); preproc.Config.set(); lintcodes.Config.off = set()
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
