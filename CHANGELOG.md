# Changelog

## 1.4.0

### Glass look (whole app, light and dark)

- A soft gradient backdrop behind the window, frosted floating panels with a lit rim and soft shadow, a floating glass icon rail with a cream highlight on the current page, a pill-shaped menu bar and status bar, pill buttons, and the Import & AI page, Home page and Settings in the same style. Default accent is now "Sand" (cream in dark mode, charcoal in light).
- **Background you can change:** Settings > Appearance > Background: presets (Aurora, Sky, Lilac, Sunset, Mint, Rose, Slate), any colour you pick, or your own picture (blurred behind the panels), with an Intensity slider.
- Smaller gaps between panes; pane titles stand alone (the small hint text is gone); the bottom status bar is off by default; the line under a drawing only appears for warnings.
- All rounded shapes and round buttons are drawn anti-aliased (smooth edges); panel contents match the panel colour, so corners stay clean.
- Settings > Appearance > **Glass look** turns it off for flat panels. It needs Pillow, which the app already requires.
- New test `guitest50`.

### Logisim editor

- **Tools like Logisim:** arrow (select / move / wire from a wire), pencil (wire) and hand (poke inputs, drag pans) buttons beside undo / redo. In the arrow tool a click on an input no longer flips it; use the hand.
- **Arrange button (▦):** tidily re-arranges the whole circuit and keeps every connection.
- **Pin dots:** inputs and outputs show a coloured dot; drag from it to start a wire.
- **Loose output pins:** a dropped output pin stays unconnected until you wire it (no auto-wiring). It is ignored by the truth table and other tabs until connected.
- **Moving parts:** a part you move stays where you put it when another part is added or moved; dragging a gate in a finished circuit keeps its connections and only re-routes the wires (no stray branches). Wiring from the middle of a wire works like Logisim (branch).
- **Selection box** now selects parts, input / output pins and wires (select all and Delete too).

### Multisim

- Drag from the list like Logisim (double-click no longer adds); a ghost shows where the part lands and it is nudged off any part it would overlap.
- Fit, + and - buttons; **Show results for** takes several parts; labels never block placement.
- Transistors, op-amps and other multi-terminal parts are fully wired and stay wired when moved; symbols sit on the grid and are drawn cleaner.

### Both

- **Properties panel** at the bottom of the left side bar (label, number of inputs, value, waveform, ... changes apply at once).

### Earlier in 1.4.0

- Drag a part from the explorer onto the canvas; Logisim-style rubber band, pan (middle button / Space) and wheel zoom; Multisim wheel zoom, pan, Home to fit, Ctrl+Z / Ctrl+Y.
- Verilog testbenches accept `reg [7:0] a = 8'hA5` and `localparam` in a module header.
- **Import & AI tab:** new soft-card look with a large picture preview (double-click to enlarge, zoom and drag in a viewer window), tidier buttons, and **automatic provider detection**: paste an API key and the provider (Gemini, Claude, OpenAI, OpenRouter, Groq) is chosen for you.
- **Multisim "Show results for":** pick the parts and nets you care about (for example only R2) and every analysis follows: DC table, AC phasors, Bode, transient, DC / parameter / temperature sweeps, Monte Carlo and noise.
- **Verilog and SystemVerilog, simulator-style tools:** a simulation settings window (top module, language standard, `-D` defines, `-I` include folders, timescale, time limit, generated-testbench options, warnings to switch off) that also shows the equivalent Icarus Verilog, Verilator and Vivado xsim command lines; one shared preprocessor (`` `define ``, `` `ifdef ``, `` `include ``, macros with arguments); a waveform viewer with radix choice, cursors A / B with distance, a signal list and **Save VCD** (opens in GTKWave and Surfer); Verilator-style warning codes such as `[WIDTH]` and `[UNUSED]`. These are our own implementations of the features, not those tools.
- **New folder layout:** `src/vibesimulation/workspaces/` has one folder per workspace (`logisim`, `multisim`, `verilog`, `systemverilog`, `ai_import`), each split by role (`circuit`, `json_view`, `truth_table`, `engine`, ...). Shared code (`core`, `components`, `layout`, `export`, `imports`, `product`, `ui`) stays where it was. Imports changed accordingly; nothing else did.
- **Tests:** `python dev/run_all.py` runs everything and prints one table; new `keytest`, `simsettingstest`, `guitest45`, `guitest46`. `guitest33` was updated for the duty-cycle field of the source form.

## 1.3.1

- **AI import:** the API key can be remembered in the operating system's keychain (optional `pip install keyring`; never written to the settings file).
- **PNG export:** `export/png.py` draws a digital or analog circuit as a picture with Pillow.
- **Accuracy tools** in `dev/finetune/`: a generator of training pictures with exact answers, a scorer, an evaluator for Ollama models, and a QLoRA training script (training script not yet run). See its README.
- **Release workflow:** pushing a `v*` tag builds the Windows, macOS and Linux apps on GitHub and attaches them to the release (first run not yet seen).

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
