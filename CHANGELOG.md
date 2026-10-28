# Changelog

## 1.3.0
- **SystemVerilog tab** (Ctrl+6): lowered to Verilog and drawn as a circuit. `logic`, `always_ff` / `always_comb`, `enum`, packed `struct`, `typedef`, packages and `import`, typed parameters, `for (int ...)`, `++` and `+=` as statements, `inside`, casts, `'0` / `'1`, functions with `return`, immediate `assert`, `$error` / `$fatal`, `.name` and `.*`, `` `define `` / `` `ifdef ``. One file per feature in `systemverilog/features/`.
- Four SystemVerilog examples, `.sv` files, autosave and recovery for the new section.
- Tests: `dev/svtest.py` (about 40 checks, many against Icarus Verilog), `dev/guitest43.py`.

## 1.2.0
- **Instruments** in Multisim: function generator (sine, square with duty, triangle, sawtooth), oscilloscope (4 channels, triggers, measurements), multimeter (DC / AC RMS, current, resistance).
- **New analyses**: parameter sweep, temperature sweep (with `tc1` / `tc2` and a thermal model for diodes and transistors), Monte Carlo (tolerances, yield, histogram), noise (thermal, shot and channel noise).
- Source dialog gains a duty setting and a sawtooth wave.

## 1.1.0
- Verilog: loops, generate, functions, memories, 64-bit values, tri-state, a testbench simulator, a bottom panel (Problems, Output, Waveform), line to part highlighting.
- Logisim `.circ` files open with a compatibility report; potentiometer and real diode models in Multisim.
- About box and optional update check, examples gallery, autosave and crash recovery, large-circuit performance work, installer files (untested on Windows / macOS).

## 1.0.0
- First release: Logisim-style editor, Multisim-style analog simulation, VLSI page, AI image import.
