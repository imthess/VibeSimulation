# Changelog

## 1.4.0

- **Sharp on Windows / any display**: the app now opts in to per-monitor DPI awareness before the window is created (no more blurry, bitmap-stretched text), scales its default window size, side bar, rail, Home tiles and file dialog with the display scale, and clamps the window to the screen. Set `VIBE_UI_SCALE=1.5` (0.75–3) to force a scale.
- **Text files are always UTF-8**: settings, saved keys and Trash info are read/written as UTF-8, so names with accents or non-Latin characters no longer fail on Windows code pages.
- macOS note: keyboard shortcuts use Control (not Command).

### IC window, second round (from your annotated screenshots)

- **X-ray look**: chips are taller (more rectangular), the inside of unused gates is drawn in white and no longer says "unused", the blue tie lines are gone (a pin held high or low is just tinted), and the chip name and "n/m gates used" are bigger and darker.
- **The IC view is editable like the circuit box**: click an input to flip it, drag chips and terminals anywhere (wires re-route; **Arrange** puts them back), click a pin and **Rewire pin…** (or double-click it) to make its gate read another signal, **Change IC…** (or right-click) turns a chip's gates into another type (7410 -> 7411 ...). These edits are written to the circuit, so the Gate view, the JSON and the truth table update at once, and edits made there rebuild the chips. The X-ray view can be dragged too, but its rewiring still never changes the circuit.
- Removed **Reuse spare gates** and **74283 adder**: they could change the logic. Chips are always built one-to-one with the gates.
- **Summary** now lists only the Logisim parts of the circuit and the chips that replace each (no breadboard, resistors or jumper wires).
- **Logisim files with several circuits**: a circuit that holds separate, unconnected circuits side by side (a gate version and a chip version) is split into tabs ('main', 'main (2)'), In4 / Out2 style names restart at 1 in each. Logisim **TTL gate chips** (7400, 7402, 7404, 7408, 7410, 7411, 7420 ...) are read as gates; the pin positions are not stored in the file, so they are found from where wires end on the chip (check the result; send the .circ if a chip is misread).
- **Download .circ / Save JSON ask which circuits (tabs) to include**: all, one, or any selection (circuits a chosen circuit uses are added automatically).
- AI import: the OpenRouter model list used a wrong address (HTTP 404 in the activity log), so the live list never loaded; fixed. A thinking model that spends all its tokens reasoning (finish_reason "length", empty answer) now gets one retry with a bigger limit, and a clear message otherwise.

### IC view (Logisim): three views of one circuit, chips drawn like Logisim's TTL parts

- The **IC** button of the circuit box opens the IC window (Logisim tab only; it hides while another workspace is shown). Tabs: **Summary** (Logisim only), **Gate view**, **IC view**, **X-ray**, Chips, Wiring, IC library. The Breadboard tab is gone.
- **Gate view**: your circuit as gates, live, as in the Logisim tab. **IC view**: the same circuit with chips instead of gates (the chip count is worked out automatically and every wire is routed by itself). **X-ray**: the same circuit and the same wires, with each chip opened up so the gates inside it and the pin each one uses are drawn. All three follow the circuit and its JSON at once, and show live values (click an input to flip it; truth-table play runs the gates and the chips together: `chips ✓`).
- **Chips look like Logisim-evolution's**: dark body, notch at the top, a square on every pin, the part number turned on its side, and a tiny VCC / GND mark beside the two power pins.
- **One VCC and one GND per chip** (fixed): every unused input that must be held high or low is wired (red = +5 V, blue = GND) to the chip's own VCC or GND pin instead of showing a GND / +5V label on many pins. A test checks every chip of the library has exactly one of each and that every tie wire ends on it.
- **X-ray editing**: click a pin to follow its signal, double-click (or right-click) to rewire it to another signal, GND, +5 V or nothing. Rewiring changes only the chip version, never the gate circuit or its JSON; gate or JSON changes rebuild the IC and X-ray views and keep your rewiring where it still fits. Chips can be dragged up or down in the IC and X-ray views (view only).
- 65 chips of Logisim-evolution's TTL library plus the 7483 are in the library; gates of any width, flip-flops, registers, counters, shift registers, multiplexers, decoders, adders, comparators and hex displays map to chips; parts without a chip are drawn as yellow blocks, never dropped silently.
- **Circuit tabs (Logisim)**: a tab strip above the panes keeps several circuits open (click to edit, x to close, + for a new circuit, right-click to rename / close / delete).
- Export: build guide, IC view / X-ray view / chip diagram pictures, parts list and wiring list. Tests: `dev/ic_test.py`, `dev/ic_catalog_check.py`, `dev/guitest57.py`.

**Verified: Verilog / SystemVerilog input and output** (`dev/hdliotest.py`, `dev/guitest56.py`): 24 Verilog and 16 SystemVerilog designs (gates, mux, adders, decoders, encoders, shifts, functions, generate, hierarchy, counters, FSMs, LFSR, enum / struct / package / inside / compound operators): the ports the program shows equal the source, every output equals iverilog's for random inputs, and .v / .sv files open, save and reopen with the same inputs and outputs. Not supported, and refused with a line number: variable part select `w[i*4 +: 4]`, non-zero reset values, bit chosen by a variable on the left, `'{...}` inside an expression, `pkg::type` in a port.

## Activity page (the </> icon above Settings)

- A live log of what happens in the background: pictures loaded, scan results, every request sent (service, model, size, options), "still waiting" lines with the seconds, the answer, tokens, key checks and errors. Keys are never shown.
- Views: **Log**, **Tokens** (the token history moved here from Settings), **Findings** (plain-words diagnosis and what to try) and **Details** (system, AI settings, the last request and answer, long text shortened).
- **Download .md / .pdf**, Copy all, Clear, Follow new lines, Problems only. Tools: **Test connection** and **Test model** (time the service and the model without a picture).
- The Import page stops a conversion that goes on far longer than the service's time limit (watchdog), and the time limit now really works with OpenRouter's keep-alive messages (the cause of the endless "processing").

## Fixes after first use

- **+ / - buttons for scan contrast and line strength** next to Adjust crop on the Import page.
- **The API key is remembered**: saved as soon as it is accepted (not only when you press Convert). Without the optional `keyring` package it goes to a private file (`~/.vibesimulation-keys`, owner-only, lightly scrambled, not encrypted).
- **A conversion can no longer run for ever**: the Convert button becomes **Stop** while the AI works, a cloud request is given up after 3 minutes with a clear message, and the model list check waits 25 s instead of 8 s.
- The Settings rows no longer repeat the category name (it is shown only in search results and Commonly Used).

## Import & AI: fewer tokens, a cleaner picture (all options in Settings > AI & Import)

- **Scan on import**: every picture is cropped to the circuit, shadows are flattened, the paper becomes white and the lines dark, and the size is limited to about 1200 px, like a document scanner. A **Scanned / Original** switch under the picture shows exactly what is sent and turns the scan off. **Adjust crop** opens a frame you drag (move, corners, edges; Automatic; Whole picture). Settings: scan on/off, look (black & white, grey, colour), contrast, line strength, size, crop on/off and margin, flatten shadows.
- **Real token usage**: the number of tokens the service reports is shown after each conversion (in, out, hidden thinking) and kept in a history (Settings > AI & Import > Token usage and history, with a list, totals and Clear; recording can be turned off).
- **Limit the AI's hidden thinking** (on by default): Gemini gets a small thinking budget, OpenRouter and OpenAI o-series/GPT-5 are told to think "low". If a service refuses the option the request is repeated without it.
- **OpenRouter model choice**: the best free picture model by default; "Free router" only when you choose it (it was the default before and could pick a slow thinking model).
- **Short answer format** (on by default): the AI writes a few short lines instead of JSON (about 40% fewer answer tokens). JSON answers still work.
- **Convert pictures to**: choose the tab yourself in Settings instead of "Auto", which costs a longer instruction.
- **A different AI for the AI button**: e.g. a local Ollama model for the button and a cloud model for pictures (Settings > AI & Import > Use a different AI for the AI button; its key is stored apart from the picture key).

## Import & AI: paste a key and nothing else

- The provider is detected from the key (now also Google's newer `AQ.` keys); if the key's shape is unknown, the provider you chose is used. A key is never sent to a service it does not belong to.
- The key is checked against the service and its **live model list** is loaded, so only models that exist today are offered, and the best picture-capable one is chosen for you (for Gemini: the newest stable Flash). A model you pick yourself is kept.
- If a chosen model has been retired, Convert and the AI button retry once with the best live model and show which one was used.
- A key the service rejects is reported in plain words. Works the same for Gemini, OpenAI, Claude, Groq and OpenRouter; Ollama still lists what is installed.

## Drag and drop

- Dropping a part from the explorer onto the circuit now picks the dragged part itself instead of depending on the row being selected, so a drop always places the part.

## Each tab owns its code (no behaviour change)

- Logisim now contains its own `core/`, `components/`, `layout/`, `export/` and `imports/`; Multisim has `core/`, `analysis/`, `components/`, `layout/`, `export/` and `imports/`; Verilog and SystemVerilog have `core/` (the language) and Verilog has `export/`; Import & AI has `core/` and `imports/`.
- The few generic pieces several tabs really share (drawing interface, wire routing, PDF/PNG writers) are in `common/`; the PDF and PNG reports are split so each tab owns its own.
- Verilog/SystemVerilog import the Logisim circuit model explicitly, so nothing is copied.

## Project reorganised (no behaviour change)

- Every tab now has its own folder under `workspaces/`: Home, Logisim, Multisim, Verilog, SystemVerilog, Import & AI and Settings.
- Settings: each setting is its own folder (`workspaces/settings/<category>/<setting>/`), listed in order in `registry.py`.
- The window shell `ui/` is sorted into `window/`, `navigation/`, `look/`, `controls/`, `panels/`, `views/` and `assistant/`; the About box, gallery and recovery code are together in `product/`.
- The 570-line assistant file is split into `controller`, `fab`, `bar` and `backdrop`; imports are now absolute everywhere.
- Removed an unused leftover function in the Logisim truth table.

## Smoother floating button and prompt bar

- One outline per area: the prompt bar no longer draws its own border ring next to the text box's outline (the soft shadow remains), and the focus outline is a single thin line.
- The bar and the round button no longer overlap; there is a clear gap between them.
- The picture behind the button and bar is now painted exactly (layer by layer) instead of sampled coarsely, so no rectangular patches show around them.
- Round and pill buttons (including the send button) use anti-aliased edges instead of jagged polygons.

## Import & AI: a built-in prompt for every tab, and your own prompt

- The picture prompt now exists for each workspace: **Logisim** (logic JSON), **Multisim** (analog JSON), **Verilog** and **SystemVerilog** (code), plus **Auto**, which decides between Logisim and Multisim as before. Pick the target in **Convert to** under the picture; the button reads "Convert picture to code" for the two code tabs.
- **Prompt: Built-in | My own.** Built-in sends the prompt written for that tab. My own shows that tab's instruction in an editable box so you can describe your picture in your own words ("this is a hand-drawn half adder, call the inputs a and b"); **Reset text** brings the built-in back. The output-format rules are always added, so the answer can still be opened. Each tab remembers its own text.
- Verilog / SystemVerilog answers are compiled before they are used; if they do not compile they go back to the AI with the compiler's messages (up to two tries). Still broken: the code is put into the editor with the faulty lines marked.
- Four result buttons (Logisim, Multisim, Verilog, SystemVerilog) open what the AI made. New test `guitest52`.

## AI assistant button (every page except Import & AI)

- The button is now a transparent, frosted-glass circle; only the star has colour. It is not shown on Import & AI, which has its own prompt options.
- A round glass button with the Import & AI star floats at the bottom right of every page except Import & AI (Settings > Appearance > AI assistant button turns it off; **Ctrl+J** opens and closes it). Click it and a wide prompt bar opens next to it, like the prompt box of an AI chat site.
- Describe the change in your own words and it is applied to what you are working on: the **Logisim circuit** (its JSON, drawing and truth table follow), the **Multisim circuit**, the **Verilog** or **SystemVerilog** code (the circuit follows), or the **testbench** when the Test tab is shown. The target follows the page; the chip in the bar changes it, also from Home, Import or Settings.
- **Edit** changes the document (one Undo step, **Undo** button in the bar); **Ask** only answers questions about the circuit or code. Text you selected in the editor, or parts you selected in the drawing, tell the AI where you mean.
- Answers are checked before they are used. A circuit that does not validate or code that does not compile is sent back to the AI with the problems, up to three tries, so mistakes usually repair themselves.
- Uses the provider, model and key of the Import & AI page (gear button in the bar shows them).
- The button and the bar are drawn smoothly over whatever is behind them (no square corners on any page). New test `guitest51`.

## Glass look (whole app, light and dark)

- A soft gradient backdrop behind the window, frosted floating panels with a lit rim and soft shadow, a floating glass icon rail with a cream highlight on the current page, a pill-shaped menu bar and status bar, pill buttons, and the Import & AI page, Home page and Settings in the same style. Default accent is now "Sand" (cream in dark mode, charcoal in light).
- **Background you can change:** Settings > Appearance > Background: presets (Aurora, Sky, Lilac, Sunset, Mint, Rose, Slate), any colour you pick, or your own picture (blurred behind the panels), with an Intensity slider.
- Smaller gaps between panes; pane titles stand alone (the small hint text is gone); the bottom status bar is off by default; the line under a drawing only appears for warnings.
- All rounded shapes and round buttons are drawn anti-aliased (smooth edges); panel contents match the panel colour, so corners stay clean.
- Settings > Appearance > **Glass look** turns it off for flat panels. It needs Pillow, which the app already requires.
- New test `guitest50`.

## Logisim editor

- **Tools like Logisim:** arrow (select / move / wire from a wire), pencil (wire) and hand (poke inputs, drag pans) buttons beside undo / redo. In the arrow tool a click on an input no longer flips it; use the hand.
- **Arrange button (▦):** tidily re-arranges the whole circuit and keeps every connection.
- **Pin dots:** inputs and outputs show a coloured dot; drag from it to start a wire.
- **Loose output pins:** a dropped output pin stays unconnected until you wire it (no auto-wiring). It is ignored by the truth table and other tabs until connected.
- **Moving parts:** a part you move stays where you put it when another part is added or moved; dragging a gate in a finished circuit keeps its connections and only re-routes the wires (no stray branches). Wiring from the middle of a wire works like Logisim (branch).
- **Selection box** now selects parts, input / output pins and wires (select all and Delete too).

### Both

- Drag a part from the explorer onto the circuit; Logisim-style rubber band, pan (middle button / Space) and wheel zoom; Multisim wheel zoom, pan, Home to fit, Ctrl+Z / Ctrl+Y.
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
