# VibeSimulation 1.4.0

A feature release: multi-circuit tabs, a complete 74xx chip window, and sharp rendering on high-DPI displays.

## Highlights

- **Circuit tabs.** Projects and Logisim `.circ` files that contain several circuits open as tabs. Open, close, add and rename circuits like browser tabs. **Download .circ** and **Save JSON** let you choose which circuits to include.
- **IC window (Logisim).** One circuit shown three ways:
  - **Gate view**: the circuit as gates.
  - **IC view**: real 74xx chips drawn like Logisim's TTL parts, one VCC and one GND pin each, wired automatically. Fully editable (flip inputs, drag chips and terminals, Rewire pin, Change IC, Arrange); edits update the circuit and every other view immediately.
  - **X-ray view**: the gates inside every chip, unused gates in white; rewiring here never changes the circuit.
  - Summary lists only the Logisim parts and the chips that replace them. Chips are always built one-to-one with the gates, so outputs always match.
- **TTL chips in `.circ` imports** (7400, 7404 and others) are read as gates.
- **Sharp on every display.** Windows DPI awareness removes the blurry rendering; the window, side bar, rail, Home tiles and file dialog scale with the display. Set `VIBE_UI_SCALE` (0.75 to 3) to force a scale.
- **Reliable text files.** Settings, saved API keys and Trash information are always read and written as UTF-8.

## Fixes

- OpenRouter "Test connection" no longer returns 404.
- Thinking models that spend their whole answer budget are retried once with a larger limit.
- Circuit clock controls moved to their own row so narrow panes do not clip the title.
- Removed the "Reuse spare gates" and 74283 options, which could change the logic of the circuit.

## Downloads

| System  | File                                                                             |
| ------- | -------------------------------------------------------------------------------- |
| Windows | `VibeSimulation-windows.zip` (run `VibeSimulation.exe`)                          |
| macOS   | `VibeSimulation-macos.zip` (right-click the app, then **Open**, on first launch) |
| Linux   | `VibeSimulation-linux.tar.gz`                                                    |

Or run from source with Python 3.9+ and Tk: `pip install .` then `vibesimulation`.

## Notes

Developed and tested on Linux; Windows and macOS builds come from the same code. Please report problems at <https://github.com/imthess/VibeSimulation/issues>.

Full changelog: [CHANGELOG.md](CHANGELOG.md)
