#!/usr/bin/env python3
"""Add native, read-only scene dependency inspection to the safe MCP addon."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "dist/addons/godot_mcp_android"
TOOL = ADDON / "scripts/tools/editor/inspect_scene_dependencies_tool.gd"
REGISTRY = ADDON / "scripts/protocol/mcp_tool_registry.gd"

TOOL_SOURCE = r'''@tool
extends MCPTool


func get_name() -> String:
	return "inspect_scene_dependencies"


func get_description() -> String:
	return "Inspect the transitive resource dependency graph for a scene using Godot's native ResourceLoader, including inherited scenes and imported/binary resources when their loaders expose dependencies. Read-only; does not copy or modify files."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"scene_path": {"type": "string", "description": "Project resource path, for example res://scenes/main.tscn."},
			"max_resources": {"type": "integer", "description": "Maximum unique resources to inspect, clamped to 1..2000."},
		},
		"required": ["scene_path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var scene_path := String(arguments.get("scene_path", "")).strip_edges()
	if not scene_path.begins_with("res://") or not is_safe_project_path(scene_path):
		return tool_error("scene_path must be a safe res:// project path")
	if not FileAccess.file_exists(scene_path):
		return tool_error("scene file does not exist")
	var max_resources := clampi(int(arguments.get("max_resources", 500)), 1, 2000)
	var pending: Array[String] = [scene_path]
	var visited := {}
	var edges: Array[Dictionary] = []
	var missing: Array[String] = []
	while not pending.is_empty() and visited.size() < max_resources:
		var current := pending.pop_back()
		if visited.has(current):
			continue
		visited[current] = true
		var dependencies := ResourceLoader.get_dependencies(current)
		dependencies.sort()
		for raw_dependency in dependencies:
			var dependency := String(raw_dependency).split("::", false, 1)[0]
			if not dependency.begins_with("res://") or not is_safe_project_path(dependency):
				return tool_error("Godot reported an unsafe or external dependency from %s: %s" % [current, raw_dependency])
			edges.append({"from": current, "to": dependency})
			if not FileAccess.file_exists(dependency) and not ResourceLoader.exists(dependency):
				missing.append(dependency)
			elif not visited.has(dependency):
				pending.append(dependency)
	var resources: Array[String] = []
	for path in visited.keys():
		resources.append(String(path))
	resources.sort()
	edges.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if String(a["from"]) == String(b["from"]):
			return String(a["to"]) < String(b["to"])
		return String(a["from"]) < String(b["from"])
	)
	missing = _unique_sorted(missing)
	return {
		"ok": true,
		"scene_path": scene_path,
		"resource_count": resources.size(),
		"edge_count": edges.size(),
		"truncated": not pending.is_empty(),
		"resources": resources,
		"dependencies": edges,
		"missing_resources": missing,
		"note": "Read-only native ResourceLoader graph. This reports dependencies; it does not import or rewrite them.",
	}


func _unique_sorted(values: Array[String]) -> Array[String]:
	var seen := {}
	for value in values:
		seen[value] = true
	var result: Array[String] = []
	for value in seen.keys():
		result.append(String(value))
	result.sort()
	return result
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}: {old!r}")
    return source.replace(old, new, 1)


def main() -> None:
    if not ADDON.is_dir():
        raise SystemExit("Safe MCP addon must be packaged before extending it.")
    registry = REGISTRY.read_text(encoding="utf-8")
    if "InspectSceneDependenciesTool" in registry or TOOL.exists():
        raise SystemExit("Dependency inspection patch is already applied or partially applied; refusing duplicate registration.")
    TOOL.parent.mkdir(parents=True, exist_ok=True)
    TOOL.write_text(TOOL_SOURCE, encoding="utf-8")
    registry = replace_once(
        registry,
        'const InstallRuntimeGameBridgeTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/install_runtime_game_bridge_tool.gd")',
        'const InspectSceneDependenciesTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/inspect_scene_dependencies_tool.gd")\nconst InstallRuntimeGameBridgeTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/install_runtime_game_bridge_tool.gd")',
        "registry preload",
    )
    registry = replace_once(
        registry,
        "\tregister(InstallRuntimeGameBridgeTool.new(editor_interface))",
        "\tregister(InspectSceneDependenciesTool.new(editor_interface))\n\tregister(InstallRuntimeGameBridgeTool.new(editor_interface))",
        "registry registration",
    )
    REGISTRY.write_text(registry, encoding="utf-8")
    # Rebuild the standalone artifact too; the base packager created an older ZIP.
    archive_path = ROOT / "dist/godot-mcp-android-safe.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "dist/addons").rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT / "dist"))
    if "ExecuteScriptTool" in registry or "delete_project" in registry:
        raise SystemExit("Unsafe MCP tool registration detected.")
    if "ResourceLoader.get_dependencies(current)" not in TOOL_SOURCE or "is_safe_project_path(dependency)" not in TOOL_SOURCE:
        raise SystemExit("Native dependency traversal or path validation is missing.")
    with ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        expected_tool = "addons/godot_mcp_android/scripts/tools/editor/inspect_scene_dependencies_tool.gd"
        expected_registry = "addons/godot_mcp_android/scripts/protocol/mcp_tool_registry.gd"
        if expected_tool not in names or expected_registry not in names:
            raise SystemExit("Rebuilt standalone ZIP is missing the dependency tool or registry.")
        if any(name.startswith("/") or ".." in name.split("/") for name in names):
            raise SystemExit("Unsafe path detected in rebuilt standalone ZIP.")
        if "ExecuteScriptTool" in archive.read(expected_registry).decode("utf-8"):
            raise SystemExit("Unsafe generic execution tool appeared in rebuilt ZIP.")
    print("Added inspect_scene_dependencies: native ResourceLoader traversal, bounded output, safe paths, read-only operation.")


if __name__ == "__main__":
    main()
