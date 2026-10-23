#!/usr/bin/env python3
"""Structural guard for the nested/standalone Godot scene import fixture.

This is a fast source-level test, not a substitute for loading the fixture in Godot.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "tests/scene_import_fixtures/nested"
EXPECTED = {
    "Main.tscn": "res://scenes/Level.tscn",
    "scenes/Level.tscn": "res://scenes/Enemy.tscn",
    "scenes/Enemy.tscn": "res://scenes/Weapon.tscn",
}
for source, target in EXPECTED.items():
    path = ROOT / source
    if not path.is_file():
        raise SystemExit(f"Missing fixture scene: {source}")
    text = path.read_text(encoding="utf-8")
    if f'path="{target}"' not in text:
        raise SystemExit(f"{source} does not preserve expected nested scene reference to {target}")
    if not re.search(r'^\[node name="[^"]+" parent="\." instance=ExtResource\("[^"]+"\)\]$', text, re.M):
        raise SystemExit(f"{source} does not instance its child scene under its root")

weapon = (ROOT / "scenes/Weapon.tscn")
if not weapon.is_file():
    raise SystemExit("Missing deepest nested scene: scenes/Weapon.tscn")
if (ROOT / "scenes/StandaloneScene.tscn").is_file() is False:
    raise SystemExit("Missing standalone scene fixture")
standalone = (ROOT / "scenes/StandaloneScene.tscn").read_text(encoding="utf-8")
if "ExtResource(" in standalone or 'instance=ExtResource' in standalone:
    raise SystemExit("Standalone scene fixture unexpectedly references another scene")
project = (ROOT / "project.godot").read_text(encoding="utf-8")
if 'run/main_scene="res://Main.tscn"' not in project:
    raise SystemExit("Fixture main scene configuration is incorrect")
inherited = (ROOT / "scenes/InheritedEnemy.tscn").read_text(encoding="utf-8")
if 'path="res://scenes/Enemy.tscn"' not in inherited or 'instance=ExtResource("1_enemy")' not in inherited:
    raise SystemExit("Inherited scene fixture no longer references its base scene")

shared_material = ROOT / "scenes/shared_material.tres"
if not shared_material.is_file():
    raise SystemExit("Missing shared resource fixture")
for name in ("SharedA.tscn", "SharedB.tscn"):
    scene = (ROOT / "scenes" / name).read_text(encoding="utf-8")
    if 'path="res://scenes/shared_material.tres"' not in scene:
        raise SystemExit(f"{name} does not reference the shared material at its original path")

missing = (ROOT / "scenes/MissingDependency.tscn").read_text(encoding="utf-8")
if 'path="res://scenes/IntentionallyMissing.tscn"' not in missing:
    raise SystemExit("Missing-dependency fixture must remain intentionally missing")
if (ROOT / "scenes/IntentionallyMissing.tscn").exists():
    raise SystemExit("The intentionally missing dependency unexpectedly exists")

print("Scene fixture structural checks passed: nested chain, standalone scene, inherited scene, shared resource, and missing-reference case.")
