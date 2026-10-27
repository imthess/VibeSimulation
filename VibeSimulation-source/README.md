# VibeSimulation

Turn a photo or screenshot of a digital circuit into an editable circuit, with a truth table, a PDF export and a Logisim `.circ` download.

## How the app is laid out

- **Home**: three tiles - **Logisim** workspace, **Import & AI** (insert a picture, choose a model, convert) and **Multisim** (DC analog circuits).
- **Top menu bar** (like VS Code): File, Download (.circ, PDF, JSON, truth-table CSV), View (show/hide panes), Settings, Home.
- **Logisim workspace**: three panes - Circuit (drawn with Logisim's own symbols; click inputs, right-click parts, **Parts...** palette), Circuit JSON (editable, live) and Truth table. Each pane has its own bar with **swap** and **hide** buttons; your layout is remembered.
- **Settings**: General (theme, layout), Logisim (truth-table size, grid, intermediate signals), Multisim, AI & Import, About.

## Install

- **Ready-made app**: download the zip for your OS from the GitHub "Actions" run (or Releases) and unzip. Windows: run `VibeSimulation.exe`. macOS: open `VibeSimulation.app` (first time: right-click > Open). Linux: `./VibeSimulation`.
- **With Python 3.9+** (needs Tk; on Debian/Ubuntu `sudo apt install python3-tk`):
  `pip install .` then run `vibesimulation` (or `python -m vibesimulation` with `PYTHONPATH=src`).
- **Build it yourself** for your OS: `python packaging/build.py` (output in `dist/`).
  Pushing a tag `v*` to GitHub builds Windows, macOS and Linux automatically (`.github/workflows/build.yml`).

## VLSI section (Verilog)

A separate page on the activity bar (hexagon icon, Ctrl+5) with three panes: **1 Verilog, 2 Circuit, 3 Truth table**. It has its own document and its own list of circuits, so nothing is shared with Logisim: Logisim keeps only Circuit, JSON and Truth table.

| Where       | File                                                             | What it does                                                                                                    |
| ----------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `ui/vlsi/`  | `workspace.py`                                                   | the page, three swappable/hideable panes plus the bottom dock                                                   |
|             | `dock.py`, `problems_tab.py`, `output_tab.py`, `waveform_tab.py` | bottom panel: Problems, Output, Waveform, Run                                                                   |
|             | `verilog_box.py`, `highlight.py`                                 | pane 1: the editor (compiles after a pause, red error lines, syntax colours)                                    |
|             | `circuit_box.py`                                                 | pane 2: the circuit drawn from the Verilog; logic edits are refused (edit the Verilog), moving parts is allowed |
|             | `truth_table_box.py`                                             | pane 3                                                                                                          |
|             | `side_panel.py`, `templates.py`                                  | explorer: modules, snippet templates, `vs_` library cells (double-click to insert)                              |
|             | `actions.py`, `menus.py`                                         | open/save `.v`, downloads; the page's own menus                                                                 |
| `vlsi/`     | `document.py`                                                    | `VlsiDocument`: what the page edits (Facade)                                                                    |
|             | `compiler.py`, `snapshots.py`, `writer.py`, `samples.py`         | text -> circuits; remembers the typed text; circuit -> text; starter design                                     |
| `verilog/`  | `lexer.py`, `parser.py`, `elab.py`, `emit.py`                    | the language: tokens, syntax tree, tree -> circuit (IEEE 1364 width/sign rules), circuit -> text                |
| `ui/views/` | `code_view.py`                                                   | text editor base shared by the JSON and Verilog boxes                                                           |

## Staying coherent

- Verilog you typed is kept exactly as typed (comments, layout) while the circuit is still what that text produced. When the logic changes some other way (an undo, JSON-level change, a different module) the Verilog is written again from the circuit. Moving parts does not count.
- A mistake in your Verilog changes nothing: the circuit stays, the faulty lines turn red, your text is kept until it compiles.
- `// @name` at the end of a line names the part that statement creates; generated Verilog writes these so ids survive.
- Several `module`s become several circuits (a module used inside another is a subcircuit). A single module renames the circuit to its name. Parameters (`#(.N(8))`) make one circuit per distinct value.
- File > Open Verilog file / Save Verilog on this page; Export also gives `.circ`, PDF and CSV.

## Supported

ANSI and old-style ports, `parameter`/`localparam`, `wire`/`reg`/`integer`, vectors up to **64 bits**, `assign` (also with `#delay`, ignored), gate primitives, all operators (arithmetic incl. signed division/modulo, bitwise, reduction, logical, comparison, shifts, `?:`, concatenation, replication, `$signed`, `$unsigned`, `$clog2`, selects), `always @*` with `if`/`case`/`casez`/`casex`, **`for`/`while`/`repeat` loops (unrolled)**, **`generate for/if/case` with `genvar`**, **`function` and `task`** (inlined), **memories** (`reg [7:0] m [0:15]`: a case/initial-filled table becomes a ROM, one address read and written becomes a RAM, small arrays become registers plus a multiplexer), **tri-state** `assign y = en ? a : 1'bz` (several drivers are OR-merged), x/z literals (read as don't-care = 0, with a warning), clocked `always @(posedge/negedge clk [or posedge/negedge reset])` with `<=` or `=` (Register / D flip-flop with enable and asynchronous reset), module instances (named or positional), and **library cells** `vs_<PartType> #(.setting(value)) name (.Pin(signal), ...)` for every other Logisim part.

## Warnings

(Problems tab, they do not stop the compile): unconnected ports, width mismatches, undriven and unused signals, x/z used as don't-care, incomplete `case` (latch risk), more than one driver.

## Testbenches and waveforms

Write a module with `initial`/`always`, `#delay`, `@(posedge clk)`, `wait`, `$display/$write/$monitor/$strobe/$finish/$time/$random` in the **Test** tab of the Verilog box (or without one: a clock, a reset and random or counting inputs are generated). **Run** in the bottom panel simulates in time (`verilog/tb/`, scheduling like a real simulator: active, non-blocking, settle, wake) and fills the **Output** and **Waveform** tabs (wheel zooms, drag pans, hover reads values). Clicking a line of the design selects the part it made in the circuit and clicking a part jumps to its line.

## Still not supported

(clear error with the line): real x/z values (only don't-care = 0; bus contention is not modelled), `fork`/`join`, `$readmemh` and file I/O, real numbers, hierarchical names (`a.b.c`), non-synthesizable constructs in the design part, widths over 64 bits, latches, blocks that mix edges and levels, RAMs with different read and write addresses and more than 256 words (use `vs_RAM`), `initial` blocks that are not testbench code.

## Differences to a real simulator

Logisim parts start at 0 (Verilog starts at x); cases Verilog calls x (index out of range, divide by zero) give Logisim's value; `always @(a or b)` is read as `@*`.

## Tests

(need `iverilog`): `dev/vfuzz_expr.py`, `dev/vfuzz_proc.py`, `dev/vtest_proc.py`, `dev/vtest_roundtrip.py`, `dev/vtest_adv.py` + `dev/vtest_adv_roundtrip.py` (loops, generate, functions, memories, tri-state), `dev/vtest_tb.py` (testbench output compared with iverilog), `dev/guitest39.py` + `dev/guitest40.py` (the page and the bottom panel).

## Product basics

- **Version / About / updates**: `Help > About` shows the version (`__version__` in `src/vibesimulation/__init__.py`). Update checks are **off** until `check_updates` is true and `update_url` (JSON `{"version", "url"}` or a GitHub release URL) is set in `~/.vibesimulation.json`; nothing is contacted otherwise. Code: `product/updates.py`, `ui/product/about.py`.
- **Examples gallery** (`Help > Examples gallery`, command palette): 15 examples with a short tutorial each (5 Logisim, 4 Multisim, 5 VLSI). Data: `product/examples.py`; window: `ui/product/gallery.py`; test: `dev/exampletest.py`.
- **Autosave and crash recovery**: every 20 s the three sections are written to `~/.vibesimulation-recovery.json` (only if changed); a normal exit deletes it; after a crash the next start offers to restore. `product/recovery.py`, `ui/product/hooks.py`; tests `dev/producttest.py`, `dev/guitest41.py`.
- **Big circuits**: above 150 parts (or when the wire router needs more than 5 s) wires are drawn as simple guide lines and the status line says so; the logic is exact. Such a layout cannot be exported to `.circ` (a clear message). A 1200-gate circuit loads in about 2 s. Test: `dev/perftest.py`, timings: `dev/perf.py`.
- **Logisim `.circ` files** open directly in Logisim and VLSI (`File > Open Logisim file`); parts that cannot be imported are listed in a compatibility report instead of being dropped silently. Test: `dev/circtest.py`.
- **Multisim**: potentiometer (`Potentiometer`, `pos` 0..1) and real diode models (`"model": "1N4148" | "1N4007" | "1N5819" | "BAT54" ...`, IS and N only, no series resistance). Op-amps and transient analysis with plot were already there. Test: `dev/analogtest4.py`.
- **Installers** (untested, no Windows or macOS here): `packaging/windows/` (Inno Setup), `packaging/macos/build_dmg.sh`, signing notes in `packaging/SIGNING.md`.

## Which file does what

Paths are inside `src/vibesimulation/`. Each feature has its own file(s).

### Logisim workspace (`ui/logisim/`)

| File               | What it does                                                                                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `circuit_view.py`  | **The Logisim circuit box**: drawing, zoom/pan, click inputs, **drag parts with the mouse**, right-click menus, Tidy, download icon                                                |
| `json_box.py`      | **The JSON text box**: red error lines, live parsing (built on `ui/views/code_view.py`, the editor base it shares with the VLSI Verilog box; also the base of Multisim's JSON box) |
| `truth_table.py`   | **The truth table**: rows, Play / Repeat, copy icon, "show intermediate outputs"                                                                                                   |
| `parts_palette.py` | The **Parts** window (folders like Logisim's explorer) and the part Properties window                                                                                              |
| `parts_folders.py` | The folder list itself (Wiring, Gates, Plexers, Arithmetic, Memory, Input/Output, TTL, TCL, BFH, Input/Output Extra, System On a Chip). Edit this to move parts between folders    |
| `workspace.py`     | Puts the three Logisim boxes side by side                                                                                                                                          |

### Multisim workspace (`ui/multisim/`)

| File                | What it does                                                                                                                                                                                                          |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schematic_view.py` | **Box 1, the schematic**: drawing, drag parts, add/edit parts, PDF and `.cir` icons                                                                                                                                   |
| `json_box.py`       | **Box 2, the analog JSON**                                                                                                                                                                                            |
| `results_view.py`   | **Box 3, DC results** (node voltages, currents, power)                                                                                                                                                                |
| `workspace.py`      | Puts the three Multisim boxes side by side                                                                                                                                                                            |
| `../../analog/`     | The analog engine: `components.py` (parts), `netlist.py` (JSON, validation, SPICE), `solver.py` (DC solver), `layout.py` (schematic placement and wire stretching), `painter.py` (draws a schematic on screen or PDF) |

### AI import and file import (`ui/ai_import/`, `ai/`, `imports/`)

| File                                           | What it does                                                                                                                                                                            |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ui/ai_import/import_view.py`                  | The whole Import & AI page: image import / paste, preview, model choice, Convert (locks the page while the AI works), open `.circ` / `.cir`, Open-in-Logisim / Open-in-Multisim buttons |
| `ui/ai_import/import_page.py`                  | Wraps the view into a full-width page                                                                                                                                                   |
| `ai/providers.py`, `ai/prompt.py`              | Talking to Gemini, OpenRouter, Groq, Ollama, Claude, OpenAI, custom; the instructions sent with the picture                                                                             |
| `imports/logisim_in.py`, `imports/spice_in.py` | Read Logisim `.circ` and SPICE `.cir` files into JSON                                                                                                                                   |

### Settings (`ui/settings/`)

`page.py` is the Settings window (categories, search, rows). **Every setting is one small file in `ui/settings/items/`** (`theme.py`, `accent_colour.py`, `corner_style.py`, `density.py`, `text_size.py`, `font.py`, `side_bar_*.py`, `reduce_motion.py`, `high_contrast.py`, `status_bar.py`, `reset_appearance.py`, `auto_open.py`, `remember_window.py`, `pane_layout.py`, `recent_files.py`, `table_bits.py`, `show_intermediate.py`, `play_speed.py`, `grid.py`, `digits.py`, `ai_import.py`). To add a setting: copy one of them and add its name to `items/__init__.py`.

### Shell and shared UI (`ui/`)

`main_window.py` (window, pages, undo), `menubar.py`, `commands.py` (Ctrl+K list), `actions.py` (File/Download actions incl. both PDF exports), `pane_workspace.py` (swap/hide panes), `rail.py` (side bar), `theme.py`, `widgets.py`, `shapes.py`, `popup.py`, `file_browser.py` (open/save window), `pages/home_page.py`, `views/base.py` (base class of every box).

### Engine, independent of the window

| Folder                           | Role                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------- |
| `core/`                          | circuit model, JSON, simulation, undo commands (`MovePart`, ...), `Document` |
| `components/<library>/<part>.py` | one file per part (gates, wiring, plexers, arithmetic, io)                   |
| `layout/`                        | placement + wire routing (`engine.py` honours moved parts), `painter.py`     |
| `export/`                        | `logisim.py` (`.circ`), `pdf.py` (Logisim PDF and Multisim PDF)              |

To add a part: create a file in `components/<library>/`, subclass `Component`, decorate with `@register`, and list it in `ui/logisim/parts_folders.py`.

## Moving parts

Drag a part in the Logisim circuit or the Multisim schematic. Like in Logisim, **the wires keep their shape**: only the wires on the part's pins stretch along (with a right-angle bend); every other wire stays where it is. It snaps to the grid and the wires follow. **None of this appears in the JSON**: positions, wire routes and orientation are _layout state_ kept beside the JSON (see "Circuit and JSON" below). Undo/redo, `.circ`, `.cir` and PDF all follow. **Tidy** (or right-click > Put back in automatic place) removes the saved positions. A drop that would overlap another part, or leave wires that cannot be drawn, is refused. Input and output pins cannot be moved yet.

**Wires and pins work like in Logisim** (both workspaces, files `ui/logisim/dragging.py`, `ui/multisim/schematic_view.py`, `layout/wire_edit.py`):

- drag a **piece** of wire sideways (joined pieces stretch along); drag a **corner or open end** to reshape the wire; **Shift+drag** on a wire adds a new bend;
- drag a part's **output pin** (or **Ctrl+drag** a circuit input) onto an input pin to connect them; in Multisim drag from one part **terminal** to another to join their nets;
- Logisim circuit **input and output pins** can be moved too (a plain click on an input still toggles it);
- **click a wire to select it, press Delete to remove it**; **click a part, press Delete to remove it** (wires that fed from it are unplugged, not left dangling). Right-click a wire: _Delete this piece of wire_ or _Put wire back in automatic route_;
- **draw wires from anywhere, like Logisim**: drag from a part's output pin or a circuit input to an input pin; or press on the **middle of a wire that is not selected** and pull a new wire from that point. Drop on an input pin to connect it, or on empty space to leave a loose wire end there (it stays in the drawing; drag it onto a pin later);
- **drag the end of a wire off a gate's input pin**: drop on another pin to move the connection, on a wire or output to connect to that signal, or on empty space to disconnect it, leaving the wire end where you dropped it. To move a wire piece instead, **click it first** (it turns selected), then drag. A selected wire's loose end can be dropped on an input pin to connect it. Two different signals cannot be joined by a wire (Logisim shows an error there too). Pins may be left unconnected (a floating input reads `E` in Logisim). Strict checks (AI import) still reject floating inputs;
- Multisim works the same: select and Delete a part or a wire; drag a terminal onto another terminal or wire to move it there, onto empty space to detach it (the wire end stays where you drop it); pull from the middle of a wire onto a terminal or wire to join the two nets (a join that would short a part is refused). **A terminal left unconnected makes the circuit incomplete**: the status turns amber ("Incomplete circuit: R3 terminal 1"), the terminal gets a red ring and the results are flagged. Known limits: a dangling BJT collector or a dangling current source has no solution (the solver says so);
- in Multisim the ground wire moves and the ground symbol and net-name labels follow it.
  Routes, positions and facing are layout state (not JSON). A route that stops fitting is ignored for that wire only.

## Look and feel (Settings > Appearance)

Dark icon rail on the left (Home, Logisim, Import & AI, Multisim, Settings), soft floating panels, graphite accent by default. Menus are drawn by the app and close on any outside click, Esc or window change.
Theme (Light / Dark / follow the system), 8 accent colours (default Blue) + a custom colour, corner style (Sharp / Rounded / Pill), density (Compact / Comfortable / Spacious), text size 85-150 %, font, reduce motion, high contrast, status bar on/off. Settings has a search box (Ctrl+F). Ctrl+K opens a command palette for every action; F1 lists all keyboard shortcuts (Ctrl+N/O/S/E/P, Ctrl+1-4, Ctrl+, Ctrl+= / - / 0, F11 ...). Alt+F / Alt+D / Alt+V open the menus. Tab moves between controls, Enter/Space press them, arrow keys change segmented controls and colour swatches.

## Open / Save dialog

The in-app file dialog works like the Ubuntu Files app: sidebar (Recent, Starred, Network, Trash, Home, Documents, Music, Pictures, Videos, Downloads, drives), back/forward/up, clickable path bar (click the empty part or Ctrl+L to type a path), sortable Name/Size/Modified columns, star column, list and icon view, search (Ctrl+F), new folder, rename (F2), move to Trash / restore / delete permanently / empty Trash, hidden files (Ctrl+H), properties, type-ahead. File > Open Recent lists the last files you opened. Network shows mounted network shares only. Trash on Windows/macOS is untested.

## Multisim (analog) workspace

**Parts:** Resistor, Capacitor, Inductor, Voltage source, Current source, Diode, **Zener** (extra `vz`, default 5.1 V), **LED**, **Switch** (click it to open/close; JSON `state`), **Ammeter**, **Voltmeter**, and the four **controlled sources** VCVS, VCCS, CCVS, CCCS (`value` = gain, `control` = two nets for voltage control or a source id for current control). Meters show their reading on the schematic. The schematic is a wired ladder (source on the left, series parts along the top rail, shunt parts down to a ground rail, junction dots); parts that share a net name are connected, net `0`/`GND` is ground.

**AC circuits.** A voltage or current source can carry an AC part next to its DC level: right-click > _Edit source…_ sets `value` (DC), `ac` (peak amplitude), `freq` (Hz), `phase` (degrees) and `wave` (sine, square or triangle); it is drawn with a sine symbol and labelled, e.g. `2 V @ 1 kHz ∠30°`. The _Analysis_ menu of the results pane then has:

- **AC: phasors, power** - every node voltage and part current as peak (or RMS) magnitude ∠ angle at one frequency, real power P, reactive power Q, apparent power, power factor (leading / lagging), the impedance seen by the source, and a phasor diagram of the rows you select.
- **AC: frequency response (Bode)** - magnitude (dB or linear) and phase of node voltages, part currents or the impedance seen by a source over a log or linear range; it reports the type (low-pass, high-pass, band-pass), the -3 dB points found by solving at the crossing (not by interpolating), centre frequency, bandwidth, Q and the roll-off in dB/decade. CSV export.
- **Transient (time)** - voltages and currents against time, starting from the DC operating point (capacitors and inductors with their DC state), trapezoidal or backward-Euler integration, diodes solved by Newton at every step (a step that fails to converge is halved); mean, RMS, min, max, peak-to-peak and frequency of any waveform over a time window you choose. CSV export.
- **Parameter sweep** - change one part's value or any numeric setting (a potentiometer's `pos`, an op-amp's `gain`, ...) step by step (linear or log) and plot what you measure: DC voltages / currents, the AC magnitude and phase at one frequency, or a transient statistic (final, peak, peak-to-peak, mean, RMS, max, min). CSV export; saved as `analysis.psweep`.
- **Temperature sweep** - the same measurements re-solved at each temperature. Resistors, capacitors and inductors use `tc1` / `tc2` (per °C and per °C², about 27 °C); diodes and transistors follow the saturation-current and thermal-voltage model, so a diode's forward voltage falls about 2 mV/K. The circuit's own temperature is `analysis.temp` (default 27 °C, results unchanged at 27 °C).
- **Monte Carlo** - many runs with random part values: give resistors, capacitors and inductors a `tol` (percent) or set a default tolerance in the panel; gaussian (sigma = tol / 3, clipped at tol) or uniform, with a seed so runs repeat. Mean, standard deviation, min, max, 5 % / 95 % percentiles, a histogram and, with pass limits, the yield. CSV export of every run.
- **Noise** - thermal noise of resistors, shot noise of diodes and transistors and channel noise of FETs at an output net over a frequency range: output spectral density, input-referred noise at a chosen source, RMS over the band and each part's share. Not included: flicker (1/f) noise; op-amps are treated as noiseless.

**Instruments** (Tools menu, each its own window that follows the circuit when it changes): a **function generator** (sine, square with adjustable duty, triangle, sawtooth; frequency, amplitude, DC offset, phase; it edits the source you pick), an **oscilloscope** (up to four channels with volts/div, offset, DC / AC / ground coupling, time/div, delay, edge trigger on any channel in auto or normal mode, and readings: Vpp, max, min, average, RMS, frequency) and a **multimeter** (DC / AC RMS voltage, DC / AC RMS current through a part, and resistance with the sources switched off, reading OL for an open circuit). The scope runs a transient simulation, so it shows what the simulator computes, not a live circuit; AC readings use the frequency of the strongest AC source.
Settings are saved in the JSON (`analysis.ac`, `analysis.tran`) and written to the `.cir` as `.ac` / `.tran`; sources are exported as `DC … AC … SIN(…)` or `PULSE(…)` and read back. Phase convention: sine-referenced, so only phase _differences_ matter. Diodes, LEDs and Zeners enter the AC analysis as their small-signal conductance at the DC operating point. In AC and transient, a net still needs a DC path to ground (the same rule as SPICE). With the analysis menu on anything but the operating point the JSON pane steps aside to give the plots room (View > brings it back). An op-amp can be modelled with a VCVS of very high gain.

**What it computes (DC):** the operating point (node voltages, part currents and power) with Newton iteration, source stepping and gmin stepping for diode circuits; a **DC sweep** of any resistor or source (plot, CSV, saved in the JSON as `analysis.sweep`, written to the `.cir` as `.dc`); **Thevenin / Norton** equivalents seen by any part (linear circuits). Problems are reported in words: floating nets, voltage-source loops, a diode or LED driven past its limit, a controlled source pointing at nothing.

**Files:** download a SPICE netlist (.cir) that Multisim can import (File > Import > From SPICE netlist); the .cir importer reads R, C, L, V, I (DC, AC, SIN, and PULSE that is a square or triangle wave), D (a `.model` with `BV=` becomes a Zener), E, G, H, F and the `.dc`, `.ac` and `.tran` cards. Multisim's own `.ms14` format is proprietary and is neither read nor written.

**Verification:** the solver is checked against closed-form answers (RC, RLC resonance, Q, power factor) and, on hundreds of random circuits, against Kirchhoff's laws and power balance; the AC solver and the transient solver are checked against each other on random RLC networks (phasor = steady state of the time simulation, 63 circuits, agreement about 1e-4) and on diode circuits with a small signal. It has **not** been compared with Multisim or ngspice (neither is available where it was built), so treat numbers for strongly nonlinear circuits as unconfirmed.

**Transistors, op-amps, transformers.** Parts with three or four terminals: NPN and PNP (Ebers-Moll with Early effect, optional junction capacitances), NMOS and PMOS (level-1 square law, enhancement or depletion, optional gate capacitances), N and P JFET (Shichman-Hodges with gate junctions), IGBT (compact model: a MOS channel behind a forward drop, blocks reverse voltage, no tail current or latch-up), OpAmp (finite gain, output rails with soft limiting, single pole set by the gain-bandwidth product; supply pins are not drawn) and Transformer (primary inductance, turns ratio, coupling k). They work in the operating point, AC (small-signal, Bode, phasors) and transient analyses, and the operating table shows region, Vbe, Ic, beta, gm and so on. In the schematic these parts are placed in rows below the ladder and every pin carries a net-name label (joined by name, not by wires); drag a pin onto another to join nets, and use "Settings" to edit beta, threshold, rails and so on. A transformer's windings are 1 µΩ at DC, so the secondary needs its own ground reference. In transient, the op-amp pole is applied before the output limiter with backward Euler. SPICE export writes Q, M, J lines with `.model` cards, a transformer as two inductors plus `K`, an IGBT as an approximate N-channel MOSFET (its forward drop and reverse blocking are not exported), and the op-amp as a gain-only VCVS (rails and bandwidth are not exported). SPICE import reads Q, M, J lines with `.model` (NPN, PNP, NMOS, PMOS, NJF, PJF; W/L scale kp; CJE, CJC, CGSO, CGDO) and `K` couplings; op-amp subcircuits (X lines) are not read.

**Not included:** UJT, phototransistor, thyristors / SCR / TRIAC, Darlington pairs as one part (build them from two BJTs), MESFET, BJT transit-time (diffusion) capacitance, MOSFET body diode and body effect, level 2+ MOSFET models, three-phase sources, Fourier / THD analysis, mixed-signal parts, switches with a control input, PWL waveforms, AC analysis that uses a source's harmonic content. The models are verified against analytic results and against each other (Jacobians, KCL on random circuits, AC against transient), and against ngspice 42 (`dev/ngtest.py`, `dev/ngtest2.py`; needs `apt install ngspice`): operating points of BJT (with Early effect), PNP, NMOS (saturation and triode), PMOS, JFET and a CMOS inverter agree to within 0.1%; AC of a BJT amplifier from 10 Hz to 100 MHz agrees to 0.05% in magnitude and 0.01° in phase, MOSFET and JFET amplifiers agree exactly, and transient waveforms of a BJT amplifier and a transformer rectifier agree to within 0.1% of the amplitude. Not checked against Multisim itself. Capacitances are constant here; in SPICE the junction capacitances of a real model depend on the bias voltage (exported BJT and MOSFET files set MJE=MJC=0 and W=L=1 so ngspice uses the same constant values; a JFET's gate capacitance cannot be made constant in SPICE, so high-frequency JFET results differ from ngspice when cgs / cgd are set). The IGBT and the op-amp's rails and bandwidth have no SPICE equivalent and were not compared. Importing pictures of analog circuits is limited to the parts the AI prompt lists.

## Not supported yet

Floating-point parts, tri-state parts (controlled buffer/inverter, pull resistor, transistor, bidirectional RAM bus), Random, Keyboard/TTY/Joystick/LED bar/DOT matrix, floating (unknown) values, TTL/TCL/BFH/SoC libraries, RAM line/byte enables, A 16-input priority encoder cannot be auto-routed. The half adder is Logisim's 1-bit Adder with Cin unconnected (Logisim has no separate half-adder part).

Dev checks (need Java + `dev/logisim.jar`): `dev/geotest.py`, `dev/semtest.py`, `dev/randtest.py`.

## JSON editor and big circuits

- The JSON box shows line numbers. When the text has an error, the line it belongs to turns red (number bar and background), so "line 20" is easy to find. The error messages themselves are unchanged.
- The circuit pane has Fit, + and - buttons; the mouse wheel zooms, dragging empty space moves the drawing, double-click empty space to fit it again.
- Layouts leave more room between columns and rows, wires keep a free grid line from each other where possible and never run along the top or bottom of a gate.

## Layout: activity bar, side bar, menu bar (VS Code style)

- **Menu bar** along the top: File, Edit, View, Help on every page, and per workspace the menus of the original program. Logisim: Project, Simulate. Multisim: Place, Simulate, Transfer, Tools. Alt+F / E / V / P / L / S / T / O / H open them; the search pill (Ctrl+K) runs any command.
- **Activity bar** (left icons): one flat bar in your accent colour (Settings > Appearance sets only its size and side). The small accent tab on the edge of the side panel hides or shows the **side panel** on every page; Settings' category list is the side panel there. Drag the panel's edge to resize it. Click the active icon or press Ctrl+B for the same. The gear opens a Manage menu (Settings, Command palette, theme).
- **Side bar, Logisim**: the explorer arranged like Logisim's, with **Edit tool** and **+ Circuit** buttons on top (the circuit tabs and tool buttons are no longer in the circuit pane): the project's circuits, then the library folders (Wiring, Gates, Plexers, Arithmetic, Memory, Input/Output, ...) with Logisim's own part order. Click a part, then click in the circuit to place it (Shift keeps the tool, Esc cancels). Double-click a circuit to open it. Parts Logisim has and we cannot simulate yet are listed greyed.
- The three panes (circuit, JSON, truth table) sit 1 px apart, flat like VS Code's editor groups.
- **Side bar, Multisim**: a component database arranged Group > Family > Component, as in Multisim's Component browser, plus Place > Component in the menu bar (Tidy is in Tools). The group and family names are from memory of Multisim, not copied from the program.
- **Settings** is a page like VS Code's: a search box on top ("N settings found"), a Commonly Used tab, then the categories; every row reads _Category: Label_. The activity bar style defaults to Docked; Settings > Appearance can still float it, move it to the right, or recolour it.
- Copy and download are icons in the pane headers: copy (the two-squares icon) for the JSON, truth table and DC results; download (the arrow icon) for the .circ (Logisim) and .cir (Multisim) files. Hover an icon to see its name.

## AI import: Logisim or Multisim

The AI is asked to say whether the picture is a logic circuit or an analog one. After Convert, the matching button at the bottom of the Import page (Open in Logisim / Open in Multisim) becomes clickable and takes you to that circuit; the other stays greyed out. Both go grey again when you load or paste a new image. Settings > General can make the app jump there automatically.

## Play the truth table

Two icons in the Truth table header: Play (▶) walks through every row from the first to the last, applying each row to the circuit so you can watch it; press it again (⏸) to stop. Repeat (⟳) makes it start again from the first row after the last one. How long each row stays is set in Settings > Logisim > Play speed (1, 2, 3 or 5 seconds). Clicking a row while it plays continues from that row. "Show intermediate outputs" moved to the bottom of the pane.

## Open circuits made in Logisim or Multisim

On the Import & AI page, "Open Logisim file (.circ)" reads a circuit you built in Logisim-evolution (the main circuit; gates of any size and direction, pins, constants, splitters, tunnels, multiplexers, adders and the other built-in parts). "Open Multisim file (.cir)" reads a SPICE netlist exported from Multisim (resistors, capacitors, inductors, diodes and Zeners, DC voltage and current sources, controlled sources, a `.dc` sweep). You get the JSON, the truth table or DC results, and the same "Open in Logisim / Open in Multisim" buttons light up. Multisim's own `.ms14` files cannot be read (closed format): export the circuit as a SPICE netlist first. Things that are not supported (sub-circuits, flip-flops and memories, transistors, AC sources ...) are listed in the message instead of being silently dropped.

## Multisim PDF

Download > PDF (or the **PDF** icon on the schematic) writes the schematic on page 1, then the DC results (node voltages, every part's voltage, current and power) and the parts list.

## Circuit and JSON (independent, always in sync)

- The **JSON** holds only the logic: inputs, outputs, parts and their connections. It stays short and readable.
- The **circuit view** also remembers _layout state_: part positions, pin positions, hand-drawn wire routes and each part's orientation. It lives in `core/layoutstate.py` and is held by the Document next to the JSON text (never inside it), is part of undo/redo, and is saved beside a saved JSON as `NAME.layout.json` (read back automatically on Open). Old files that still contain `"pos"`/`"wires"` are read and cleaned.
- Editing the JSON keeps the layout of every part/wire that still exists (matched by id / signal name). Editing the circuit rewrites the JSON.
- **Empty JSON is a valid blank circuit**: right-click empty space to add an input, output, gate or any part exactly where you clicked. A circuit may be half built (no outputs yet), like in Logisim.
- If the JSON has a typo, the circuit view keeps showing the last good version and says so; fix the JSON to continue.

## Orientation, selection, keys (Logisim-style)

Click a part to select it. **R** turns it clockwise, **L** counter-clockwise, **Delete** removes it, **Esc** unselects; right-click > Facing sets east/south/west/north. Orientation uses Logisim's own rotation (`core/orient.py`: components are written once facing east and are turned by wrapping their pins, body and drawing) and is written to the `.circ` as the part's `facing`. Turning a part lets the router redraw its wires.

File map additions: `core/layoutstate.py` (extract/apply/merge layout state), `core/orient.py` (facing), `ui/actions.py` (sidecar read/write).

## Sequential logic (flip-flops, registers, counters, clock)

Parts: Wiring > **Clock**; Memory > **D / T / J-K / S-R Flip-Flop**, **Register**, **Counter**, **Shift Register** (`components/memory/`, `components/wiring/clock.py`). Pin positions, defaults and behaviour follow Logisim-evolution (classic appearance).

- **Simulator:** `core/sim.py`. Every sequential part has a state; after each change the circuit is calculated, every part that sees a clock edge (or an asynchronous Clear/Preset) takes its new state _at the same moment_, and this repeats until nothing changes (so ripple counters work). Feedback loops through flip-flops are allowed; a loop made only of gates is still an error. A loop that never settles shows "OSCILLATING".
- **Controls** (shown in the circuit header when the circuit has a clock/flip-flops): Tick half cycle (Ctrl+T), Tick full cycle (Ctrl+Shift+T), Run/Stop (Ctrl+K) at 1-32 Hz, Reset simulation (Ctrl+R). Clicking an input that feeds a clock pin also clocks the part. States are kept while you edit and are part of nothing in the JSON.
- **JSON** example: `{"id": "f", "type": "D Flip-Flop", "in": {"D": "qn", "Clk": "clk"}, "out": {"Q": "q", "Qn": "qn"}}`; optional pins (`Clr`, `Pre`, `En`, `Ld`, `UD`, `Sh`, ...) are only written when connected. Settings: `trigger` (rising/falling, D flip-flop and Register also high/low = latch), Register/Counter/Shift `width`, Counter `max`/`ongoal`, Shift `length`/`parallel`, Clock `high`/`low`/`phase`.
- **Checked against the real Logisim:** `dev/seqtest.py` exports 18 sequential circuits, runs them in `dev/logisim.jar` (`-tty table,halt`, which ticks the clocks) and compares every row with VibeSimulation: all identical. One known difference: Logisim 3.8.0 leaves the last parallel output of a Shift Register floating (a bug fixed later); VibeSimulation drives it.
- No truth table for such circuits (they depend on history).

## ROM, and importing sequential `.circ` files

- **ROM** (Memory > ROM): address bits 1-16, data bits 1-32. Contents are logic, so they are in the JSON: `"contents": {"0": 18, "1": 171}` (address: value, decimal or "0x.."; missing = 0; a plain list also works). Double-click the part (or right-click > Properties > Edit contents…) for a hex editor with _Open .hex/.txt_ (Logisim's `v2.0 raw` files too). Contents are written to and read from `.circ` files. Checked against the real Logisim (a counter addressing a ROM, run in the jar).
- **Import:** `.circ` files with Clock, flip-flops, Register, Counter, Shift Register and ROM now load, in both Logisim looks (`classic` and the default `logisim_evolution`; pin positions of the latter are verified against the real Logisim by `dev/impseqtest.py`). Not yet: RAM, tunnels with sequential parts in sub-circuits, rotated sequential parts other than the Clock.
- Not supported yet: **RAM** (its default mode uses one two-way data bus, which this simulator cannot represent yet), Random, Button/Joystick/Keyboard/TTY, TTL, subcircuits.

## Several circuits and subcircuits

A project can hold many circuits (tabs above the circuit view, **+ Circuit** adds one, right-click a tab to rename or delete it). Place a circuit inside another from
**Parts… > This project's circuits** (or right-click empty space > _Add circuit here_); its input/output pins become the part's pins. Double-click the part to open the circuit inside.
In JSON a subcircuit is `{"id": "u1", "type": "Circuit", "circuit": "half", "in": {"a": "A", "b": "B"}, "out": {"s": "S", "c": "C"}}` (pin names are the pin names of that circuit).
A project with several circuits is saved as `{"main": "name", "circuits": {"name": {...}, ...}}` (one circuit is still the plain format). Circuits that contain themselves are refused.
Simulation flattens the subcircuits (a counter inside a subcircuit counts, nested subcircuits work) and was compared with real Logisim row for row (`dev/subtest3.py`).
`.circ` export writes every circuit; import reads every circuit, in Logisim's classic subcircuit look exactly and in the newer look by reading the box width from where the wires end.
Unconnected subcircuit inputs read as 0 here (Logisim leaves them floating). Undo history is per circuit and starts again when you switch circuits.

## RAM, Button, editing several parts

RAM (Memory folder) is Logisim's default configuration: separate Din / Dout pins, optional async read, read-before/after-write, Clear pin, rising/falling/high/low trigger (`dev/seqtest.py`, `dev/ramtest.py`).
Contents start at 0; double-click the RAM while the circuit runs to read or edit them (hex editor, can load a hex file). Not supported: bidirectional bus, line/byte enables.
A Button in an imported `.circ` becomes an input pin. Editing: Ctrl+click adds a part to the selection, Shift+drag draws a selection rectangle, Ctrl+A selects all; drag one selected part to move all;
Ctrl+C / Ctrl+X / Ctrl+V copy, cut and paste (internal connections are kept, outside inputs stay connected to the same signals); Delete removes the selection.
