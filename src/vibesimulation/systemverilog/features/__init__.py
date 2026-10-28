"""Every module in this package is one SystemVerilog feature; importing the package registers them all.

Modules are found by listing the package folder. A packaged (frozen) program may not be able to list it, so ``FALLBACK`` names the
files for that case; ``dev/svtest.py`` checks that the two agree."""
import importlib
import pkgutil

FALLBACK = ("preprocess", "unsupported", "end_labels", "qualifiers", "unique_priority", "typed_params", "packages", "enums", "structs", "typedefs",
            "always_blocks", "logic_types", "for_decl", "compound_ops", "inside_op", "casts", "fill_literals", "functions", "severity_tasks",
            "assertions", "port_shorthand", "leftover")
FOUND = sorted(m.name for m in pkgutil.iter_modules(__path__))

for _name in (FOUND or FALLBACK): importlib.import_module(f"{__name__}.{_name}")
