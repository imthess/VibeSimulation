# dev/

Tests and comparison scripts (see ../CONTRIBUTING.md for what each needs).

`logisim.jar` is **not** in the repository. The few scripts that compare against real Logisim (`geotest.py`, `semtest.py`, `randtest.py`, `gen_defaults.py`, and the Java helpers in `jsrc/`) need Logisim 2.7.1 saved here as `dev/logisim.jar`, plus a Java runtime.

`docshots.py` regenerates the screenshots in `docs/images` (needs a display, e.g. `xvfb-run -a -s "-screen 0 1500x950x24" python3 dev/docshots.py`).
