#!/usr/bin/env python3
"""Static checks for the Android editor startup/loading overlay patch."""
from pathlib import Path
import ast
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def require(condition: bool, message: str) -> None:
    if not condition:
        print("FAIL: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: " + message)

patcher = ROOT / "scripts/apply_android_startup_patch.py"
ast.parse(patcher.read_text(encoding="utf-8"), filename=str(patcher))
require(True, "startup patcher has valid Python syntax")
source = patcher.read_text(encoding="utf-8")
for token, label in [
    ("windowSplashScreenBackground", "native splash background is explicit"),
    ("windowSplashScreenAnimatedIcon", "native splash uses the app icon"),
    ("@+id/editor_loading_indicator", "loading overlay keeps the existing readiness hook ID"),
    ("Preparing your workspace", "startup overlay includes a status message"),
    ("onGodotMainLoopStarted", "patch documents the existing overlay hide lifecycle"),
]:
    require(token in source, label)
layout = ROOT / "godot-source/platform/android/java/editor/src/main/res/layout/godot_editor_layout.xml"
themes = ROOT / "godot-source/platform/android/java/editor/src/main/res/values/themes.xml"
require(layout.is_file() and themes.is_file(), "patched Android startup resources exist")
layout_root = ET.parse(layout).getroot()
themes_root = ET.parse(themes).getroot()
require(any(node.attrib.get("{http://schemas.android.com/apk/res/android}id") == "@+id/editor_loading_indicator" for node in layout_root.iter()),
        "patched loading overlay preserves the startup lifecycle ID")
theme_items = [node.attrib.get("name", "") for node in themes_root.iter("item")]
require("windowSplashScreenBackground" in theme_items and "windowSplashScreenAnimatedIcon" in theme_items,
        "patched native splash resources are well-formed and include explicit branding")
print("Static checks only; no Android resource compilation or device runtime is implied.")
