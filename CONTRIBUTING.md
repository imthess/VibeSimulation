# Contributing

## Set up

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

GUI tests need a display. On a server use Xvfb: `Xvfb :97 &` then `DISPLAY=:97 python dev/guitest43.py`.

## Tests

Scripts in `dev/` print `ok` / `FAIL` lines and exit non-zero on failure. **`python dev/run_all.py`** runs all of them and prints one table (`--fast` = no window, `--window` = window tests only; on a server use `xvfb-run -a python dev/run_all.py`).

| Kind                                                                                                                                                                                                                                                         | Scripts                                                                                                                                                                  | Needs                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Fast, no window (run on every push)                                                                                                                                                                                                                          | `svtest.py`, `instrtest.py`, `sweeptest.py`, `noisetest.py`, `exampletest.py`, `producttest.py`, `finetunetest.py`, `keytest.py`, `simsettingstest.py`, `analogtest4.py` | `iverilog` for `svtest.py`                                                                |
| Verilog against Icarus                                                                                                                                                                                                                                       | `vtest_*.py`, `vfuzz_expr.py <seed> <n> [wide]`, `vfuzz_proc.py <seed> <n> seq`                                                                                          | `iverilog`                                                                                |
| Analog against ngspice                                                                                                                                                                                                                                       | `ngtest.py`, `ngtest2.py`                                                                                                                                                | `ngspice`                                                                                 |
| Window tests (`guitest44.py` keychain / key detection, `guitest45.py` Multisim "Show results for", `guitest46.py` Verilog / SystemVerilog settings and waveform, `guitest47`-`guitest50` drag-and-drop, properties panel, QA-round fixes and the glass look) | `guitest*.py` (`guitest.py` is the old prototype test and is not run)                                                                                                    | a display                                                                                 |
| Logisim comparison                                                                                                                                                                                                                                           | `geotest.py`, `semtest.py`, `randtest.py`                                                                                                                                | Java and `dev/logisim.jar` (download Logisim 2.7.1 yourself; it is not in the repository) |

## Adding things

- **A part:** a file in `src/vibesimulation/components/<library>/`, subclass `Component`, decorate with `@register`, list it in `workspaces/logisim/circuit/parts_folders.py`.
- **An example:** one `add(...)` call in `product/examples.py` (or `examples_sv.py`); `dev/exampletest.py` checks that it compiles and runs.
- **A SystemVerilog feature:** one new file in `src/vibesimulation/workspaces/systemverilog/engine/features/`: subclass `Feature`, set `name`, `order` and `triggers`, write `apply(ctx)`, decorate with `@feature`, and add its name to `FALLBACK` in `features/__init__.py`. Keep every token on its original line (use `TokenEditor`). Add a case to `dev/svtest.py`: compare against `iverilog -g2012` with `diff(...)` when iverilog supports the construct.
- Design patterns used, and where, are listed in `docs/MANUAL.md`. Keep one feature or one box per file.

## Pull requests

Run the fast tests first. Say what you changed and what you checked it against.

## Making the AI import more accurate

See `dev/finetune/README.md`.
