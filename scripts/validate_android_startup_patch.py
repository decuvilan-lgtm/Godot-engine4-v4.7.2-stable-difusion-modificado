#!/usr/bin/env python3
"""Static checks for the Android editor startup/loading overlay patch."""
from pathlib import Path
import ast
import sys

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
print("Static checks only; no Android resource compilation or device runtime is implied.")
