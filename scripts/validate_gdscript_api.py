#!/usr/bin/env python3
"""Cross-check custom GDScript calls against the checked-out Godot API docs.

This is a fast preflight, not a substitute for parsing/running GDScript on Android.
It checks private helper references and explicit Class.method(...) calls whose
Godot class documentation is present in the official source checkout.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot-source"
DOCS = GODOT / "doc" / "classes"
ADDON_ROOTS = (ROOT / "scripts" / "github_sync_addon", ROOT / "scripts" / "terrain_3d_addon")
FAILURES: list[str] = []
CHECKED_CALLS = 0
CHECKED_CLASSES: set[str] = set()
SKIPPED_CLASSES: set[str] = set()


def fail(message: str) -> None:
    FAILURES.append(message)
    print("FAIL: " + message, file=sys.stderr)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


if not DOCS.is_dir():
    raise SystemExit(f"Official Godot class docs not found at {DOCS}")

gd_files = sorted(path for root in ADDON_ROOTS if root.is_dir() for path in root.rglob("*.gd"))
require(bool(gd_files), "custom addon GDScript files were found")
if not gd_files:
    raise SystemExit(1)

for path in gd_files:
    source = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)
    definitions = set(re.findall(r"(?m)^\s*func\s+([A-Za-z0-9_]+)\s*\(", source))
    private_calls = set(re.findall(r"(?<![.\w])(_[A-Za-z][A-Za-z0-9_]*)\s*\(", source))
    for name in sorted(private_calls - definitions):
        fail(f"{relative}: private helper call {name}() has no local function definition")

    for match in re.finditer(r"\b([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", source):
        class_name, method_name = match.groups()
        if method_name == "new":
            continue
        doc_path = DOCS / f"{class_name}.xml"
        if not doc_path.is_file():
            SKIPPED_CLASSES.add(class_name)
            continue
        try:
            root = ET.parse(doc_path).getroot()
        except ET.ParseError as exc:
            fail(f"Could not parse official API docs {doc_path.name}: {exc}")
            continue
        methods = {node.attrib.get("name", "") for node in root.findall("./methods/method")}
        CHECKED_CLASSES.add(class_name)
        CHECKED_CALLS += 1
        if method_name not in methods:
            line = source.count("\n", 0, match.start()) + 1
            fail(f"{relative}:{line}: {class_name}.{method_name}() is absent from Godot {class_name} API docs")

print(f"Audited {len(gd_files)} GDScript files; checked {CHECKED_CALLS} explicit class-method calls across {len(CHECKED_CLASSES)} documented classes.")
if SKIPPED_CLASSES:
    print("INFO: skipped calls on classes without individual XML docs: " + ", ".join(sorted(SKIPPED_CLASSES)))
if FAILURES:
    raise SystemExit(f"GDScript API preflight found {len(FAILURES)} issue(s).")
print("PASS: no unresolved private helper calls or documented static-class API calls found.")
print("LIMIT: instance-typed calls and runtime behavior still need engine/device validation.")
