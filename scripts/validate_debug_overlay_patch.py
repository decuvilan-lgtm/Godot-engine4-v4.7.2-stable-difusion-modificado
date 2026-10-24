#!/usr/bin/env python3
"""Source-only regression checks for the Godot run-bar debug-overlay patch.

This deliberately does not build Godot, run Linux tests, or claim runtime validation.
"""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts" / "apply_github_import_patch.py"
README = ROOT / "README.md"

def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        raise SystemExit(1)
    print(f"PASS: {message}")

require(PATCHER.is_file(), "Godot source patcher exists")
source = PATCHER.read_text(encoding="utf-8")
ast.parse(source, filename=str(PATCHER))
require(True, "patcher has valid Python syntax")

for token, label in [
    ("PREVIEW_DEBUG_COLLISIONS", "collision overlay menu item"),
    ("PREVIEW_DEBUG_PATHS", "path overlay menu item"),
    ("PREVIEW_DEBUG_NAVIGATION", "navigation overlay menu item"),
    ("PREVIEW_DEBUG_AVOIDANCE", "avoidance overlay menu item"),
    ("PREVIEW_DEBUG_CANVAS_REDRAW", "CanvasItem redraw menu item"),
    ('set_project_metadata("debug_options", metadata_key, enabled)', "per-project debug preference persistence"),
    ("set_debug_collisions(enabled)", "live collision debugger command"),
    ("set_debug_navigation(enabled)", "live navigation debugger command"),
    ("set_debug_avoidance(enabled)", "live avoidance debugger command"),
    ('_put_msg("scene:set_debug_navigation", msg)', "navigation remote-debugger message"),
    ('_put_msg("scene:set_debug_avoidance", msg)', "avoidance remote-debugger message"),
    ('message_handlers["set_debug_navigation"] = _msg_set_debug_navigation', "navigation runtime message handler registration"),
    ('message_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance', "avoidance runtime message handler registration"),
]:
    require(token in source, label)

# Prevent documentation from claiming that currently incomplete overlays are live.
readme = README.read_text(encoding="utf-8") if README.is_file() else ""
require("Visible Paths" in readme and "CanvasItem Redraws" in readme,
        "README mentions both deferred overlay limitations")

print("Source-only checks passed. This does not prove C++ compilation or in-game runtime behavior.")
