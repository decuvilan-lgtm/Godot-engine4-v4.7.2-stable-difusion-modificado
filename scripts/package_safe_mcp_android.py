#!/usr/bin/env python3
"""Package a hardened Android-compatible Godot MCP addon from the public upstream source.

The addon is deliberately loopback-only and does not expose arbitrary GDScript
expression execution. It is packaged separately from the engine APK because
EditorPlugin addons are enabled per Godot project.
"""
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "godot-mcp-android-source" / "addons" / "godot_mcp_android"
DIST = ROOT / "dist"
ADDON_OUT = DIST / "addons" / "godot_mcp_android"
ZIP_OUT = DIST / "godot-mcp-android-safe.zip"

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path.name}: expected exactly one patch anchor, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def main() -> int:
    if not (UPSTREAM / "plugin.cfg").is_file():
        print(f"Upstream addon not found: {UPSTREAM}", file=sys.stderr)
        return 2

    if DIST.exists():
        shutil.rmtree(DIST)
    ADDON_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(UPSTREAM, ADDON_OUT)

    registry = ADDON_OUT / "scripts/protocol/mcp_tool_registry.gd"
    # The generic expression tool can invoke editor APIs outside the narrow
    # typed tool schemas. Remove it rather than pretending it is a sandbox.
    replace_once(
        registry,
        'const ExecuteScriptTool := preload("res://addons/godot_mcp_android/scripts/tools/system/execute_script_tool.gd")\n',
        "",
    )
    replace_once(
        registry,
        "\tregister(ExecuteScriptTool.new(editor_interface))\n",
        "",
    )

    for rel in (
        "scripts/server/mcp_http_server.gd",
        "scripts/server/mcp_websocket_server.gd",
    ):
        server = ADDON_OUT / rel
        text = server.read_text(encoding="utf-8")
        old = "\tbind_host = ProjectSettings.get_setting(SETTING_BIND_HOST, bind_host)"
        if text.count(old) != 1:
            raise RuntimeError(f"{server.name}: expected one configurable bind-host assignment")
        server.write_text(text.replace(old, '\tbind_host = "127.0.0.1"', 1), encoding="utf-8")

    # Do not advertise cross-origin browser access for an editor-control API.
    http = ADDON_OUT / "scripts/server/mcp_http_server.gd"
    replace_once(
        http,
        '\tresponse += "Access-Control-Allow-Origin: *\\r\\n"\n',
        "",
    )

    registry_text = registry.read_text(encoding="utf-8")
    if "ExecuteScriptTool" in registry_text or "delete_project" in registry_text:
        raise RuntimeError("unsafe tool registration detected")
    for rel in ("scripts/server/mcp_http_server.gd", "scripts/server/mcp_websocket_server.gd"):
        server_text = (ADDON_OUT / rel).read_text(encoding="utf-8")
        if 'bind_host = "127.0.0.1"' not in server_text:
            raise RuntimeError(f"{rel}: loopback-only guard missing")

    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((DIST / "addons").rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST))
    print(f"Packaged safe addon: {ZIP_OUT}")
    print("Safety checks passed: loopback-only listeners; no generic execute_script tool; no delete_project tool.")
    print("Install by extracting the zip into a Godot project root and enabling the plugin in Project Settings > Plugins.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
