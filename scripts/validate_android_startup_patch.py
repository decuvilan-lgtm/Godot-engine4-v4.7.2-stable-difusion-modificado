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
    ("windowSplashScreenAnimatedIcon", "native splash uses the supplied Goku image"),
    ("@drawable/goku_ultra_instinto", "native splash and startup overlay use the supplied Goku image"),
    ("GOKU_DRAWABLE.write_bytes", "supplied Goku image is decoded into an Android drawable"),
    ("scripts/assets/goku_ultra_instinto.jpg.b64", "the provided image is stored as a build-time asset"),
    ("@+id/editor_loading_indicator", "loading overlay keeps the existing readiness hook ID"),
    ("Preparing your workspace", "startup overlay includes a status message"),
    ('android:text="AZIZA"', "startup overlay displays the documented AZIZA text"),
    ("Goku Ultra Instinto", "startup image accessibility label is configured for Goku Ultra Instinto"),
    ("onGodotMainLoopStarted", "patch documents the existing overlay hide lifecycle"),
]:
    require(token in source, label)
layout = ROOT / "godot-source/platform/android/java/editor/src/main/res/layout/godot_editor_layout.xml"
themes = ROOT / "godot-source/platform/android/java/editor/src/main/res/values/themes.xml"
require(layout.is_file() and themes.is_file(), "patched Android startup resources exist")
asset = ROOT / "godot-source/platform/android/java/editor/src/main/res/drawable-nodpi/goku_ultra_instinto.jpg"
require(asset.is_file() and asset.stat().st_size > 1000 and asset.read_bytes().startswith(bytes((0xFF, 0xD8))),
        "Goku splash drawable was decoded as a real JPEG asset")
layout_root = ET.parse(layout).getroot()
themes_root = ET.parse(themes).getroot()
require(any(node.attrib.get("{http://schemas.android.com/apk/res/android}id") == "@+id/editor_loading_indicator" for node in layout_root.iter()),
        "patched loading overlay preserves the startup lifecycle ID")
theme_items = [node.attrib.get("name", "") for node in themes_root.iter("item")]
require("windowSplashScreenBackground" in theme_items and "windowSplashScreenAnimatedIcon" in theme_items,
        "patched native splash resources are well-formed and include explicit branding")
require("@drawable/goku_ultra_instinto" in source, "both native and in-engine startup use the Goku drawable")
print("Static checks only; no Android resource compilation or device runtime is implied.")
