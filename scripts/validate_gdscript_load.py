#!/usr/bin/env python3
"""Load both editor addons in the real Godot 4.7.2 editor (headless, Windows runner)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_scene_fixtures(project: Path) -> None:
    scenes = project / "scenes"
    scenes.mkdir(parents=True, exist_ok=True)
    (scenes / "base.tscn").write_text(
        '[gd_scene format=3]\n\n[node name="Base" type="Node3D"]\n'
        '\n[node name="Child" type="MeshInstance3D" parent="."]\n',
        encoding="utf-8",
    )
    (scenes / "nested.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="PackedScene" path="res://scenes/base.tscn" id="1_base"]\n\n'
        '[node name="Nested" type="Node3D"]\n\n'
        '[node name="BaseInstance" parent="." instance=ExtResource("1_base")]\n',
        encoding="utf-8",
    )
    (scenes / "main.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="PackedScene" path="res://scenes/nested.tscn" id="1_nested"]\n\n'
        '[node name="Main" type="Node3D"]\n\n'
        '[node name="NestedInstance" parent="." instance=ExtResource("1_nested")]\n',
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, help="Path to Godot 4.7.2 Windows console executable")
    args = parser.parse_args()
    godot = Path(args.godot)
    if not godot.is_file():
        print(f"FAIL: Godot executable not found: {godot}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="godot-addon-load-") as temp:
        project = Path(temp)
        addons = project / "addons"
        addons.mkdir()
        shutil.copytree(ROOT / "scripts/github_sync_addon", addons / "github_sync")
        shutil.copytree(ROOT / "scripts/terrain_3d_addon", addons / "terrain_3d")
        (project / "project.godot").write_text(
            'config_version=5\n\n[application]\nconfig/name="Godot Addon Integration Test"\n'
            'run/main_scene="res://scenes/main.tscn"\n\n'
            '[editor_plugins]\n'
            'enabled=PackedStringArray("res://addons/github_sync/plugin.cfg", '
            '"res://addons/terrain_3d/plugin.cfg")\n',
            encoding="utf-8",
        )
        write_scene_fixtures(project)
        log_file = project / "godot-test.log"
        command = [str(godot), "--headless", "--editor", "--path", str(project), "--quit", "--log-file", str(log_file)]
        print("Running actual Godot editor parser/plugin-load test:")
        print(" ".join(command))
        try:
            result = subprocess.run(
                command, cwd=project, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=180, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            print(output[-12000:])
            print("FAIL: Godot editor did not finish loading the addon fixture within 180 seconds.", file=sys.stderr)
            return 1

        output = result.stdout or ""
        if log_file.is_file():
            output += "\n" + log_file.read_text(encoding="utf-8", errors="replace")
        print(output[-18000:])
        error_markers = (
            "SCRIPT ERROR:",
            "Parse Error:",
            "Failed to load script",
            "Error loading resource:",
            "Invalid call. Nonexistent function",
            "Invalid assignment of property",
        )
        found = [line for line in output.splitlines() if any(marker in line for marker in error_markers)]
        if result.returncode != 0 or found:
            print(f"FAIL: Godot editor returned {result.returncode}; script/resource errors={len(found)}.", file=sys.stderr)
            for line in found:
                print(line, file=sys.stderr)
            return 1
        print("PASS: both addons loaded in Godot 4.7.2 and nested PackedScene fixtures parsed without script/resource errors.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
