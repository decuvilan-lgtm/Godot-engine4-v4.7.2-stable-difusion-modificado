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

    # Remove the unused implementation too, so it cannot be re-registered accidentally.
    (ADDON_OUT / "scripts/tools/system/execute_script_tool.gd").unlink(missing_ok=True)

    # Before replacing an existing project file, preserve its prior UTF-8 contents.
    # Backups are project-local, hash-named, and unique per write so repeated edits do not
    # overwrite earlier recovery points. If the backup cannot be written, abort the mutation.
    replace_once(
        ADDON_OUT / "scripts/tools/filesystem/write_file_tool.gd",
        """\tvar file := FileAccess.open(resource_path, FileAccess.WRITE)
\tif file == null:""",
        """\tvar recovery_path := ""
\tif FileAccess.file_exists(resource_path):
\t\tvar previous_file := FileAccess.open(resource_path, FileAccess.READ)
\t\tif previous_file == null:
\t\t\treturn tool_error("cannot read existing file for recovery: %s" % error_string(FileAccess.get_open_error()))
\t\tvar previous_text := previous_file.get_as_text()
\t\tprevious_file.close()
\t\tvar recovery_dir := ".godot_mcp_backups"
\t\tvar recovery_error := DirAccess.make_dir_recursive_absolute(globalize_project_path(recovery_dir))
\t\tif recovery_error != OK:
\t\t\treturn tool_error("cannot create recovery directory: %s" % error_string(recovery_error))
\t\trecovery_path = "res://%s/%s.%d.bak" % [recovery_dir, resource_path.sha256_text(), Time.get_ticks_usec()]
\t\tvar recovery_file := FileAccess.open(recovery_path, FileAccess.WRITE)
\t\tif recovery_file == null:
\t\t\treturn tool_error("cannot create recovery copy: %s" % error_string(FileAccess.get_open_error()))
\t\trecovery_file.store_string(previous_text)
\t\trecovery_file.close()
\t\tif not FileAccess.file_exists(recovery_path):
\t\t\treturn tool_error("recovery copy was not created; original file was not changed")
\t\tvar recovery_check := FileAccess.open(recovery_path, FileAccess.READ)
\t\tif recovery_check == null:
\t\t\treturn tool_error("recovery copy could not be opened for verification; original file was not changed")
\t\tvar recovered_text := recovery_check.get_as_text()
\t\trecovery_check.close()
\t\tif recovered_text != previous_text:
\t\t\treturn tool_error("recovery copy could not be verified; original file was not changed")
\n\tvar file := FileAccess.open(resource_path, FileAccess.WRITE)
\tif file == null:"""),
    )
    
    # Route scene mutations through Godot's editor undo/redo manager. This keeps
    # the operations reversible and avoids manually invoking lifecycle methods.
    replace_once(
        ADDON_OUT / "scripts/tools/scene/set_node_property_tool.gd",
        """func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")

	var property_name := String(arguments.get("property", ""))
	node.set(property_name, arguments.get("value"))

	if property_name == "script" and node.is_inside_tree() and node.has_method("_ready"):
		node._ready()

	return {
		"ok": true,
		"path": relative_scene_path(node),
		"property": property_name,
	}""",
        """func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")

	var property_name := String(arguments.get("property", ""))
	var property_exists := false
	for property_info in node.get_property_list():
		if String(property_info.get("name", "")) == property_name:
			property_exists = true
			break
	if not property_exists:
		return tool_error("property not found: %s" % property_name)

	var previous_value = node.get(property_name)
	var new_value = arguments.get("value")
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Set Node Property")
	undo_redo.add_do_property(node, property_name, new_value)
	undo_redo.add_undo_property(node, property_name, previous_value)
	undo_redo.commit_action()

	return {
		"ok": true,
		"path": relative_scene_path(node),
		"property": property_name,
		"undo_available": true,
	}""",
    )

    replace_once(
        ADDON_OUT / "scripts/tools/scene/remove_node_tool.gd",
        """func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")

	var root := get_edited_scene_root()
	if node == root:
		return tool_error("cannot remove the scene root node")

	var path := relative_scene_path(node)
	node.queue_free()
	return {
		"ok": true,
		"path": path,
	}""",
        """func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")

	var root := get_edited_scene_root()
	if node == root:
		return tool_error("cannot remove the scene root node")

	var parent := node.get_parent()
	if parent == null:
		return tool_error("cannot remove a node without a parent")

	var path := relative_scene_path(node)
	var original_index := node.get_index()
	var original_owner = node.owner
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Remove Node")
	undo_redo.add_do_method(parent, "remove_child", node)
	# Undo methods are registered in reverse execution order.
	undo_redo.add_undo_method(node, "set_owner", original_owner)
	undo_redo.add_undo_method(parent, "move_child", node, original_index)
	undo_redo.add_undo_method(parent, "add_child", node)
	undo_redo.commit_action()

	return {
		"ok": true,
		"path": path,
		"undo_available": true,
	}""",
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

    # Keep the exact pre-edit contents available for the recovery copy.
    replace_once(
        ADDON_OUT / "scripts/tools/filesystem/edit_file_tool.gd",
        "\tvar content := file.get_as_text()",
        "\tvar content := file.get_as_text()\n\tvar original_content := content",
    )

    replace_once(
        ADDON_OUT / "scripts/tools/filesystem/write_file_tool.gd",
        '\t"bytes_written": text.to_utf8_buffer().size(),',
        '\t"bytes_written": text.to_utf8_buffer().size(),\n\t"recovery_copy": recovery_path,',
    )
    replace_once(
        ADDON_OUT / "scripts/tools/filesystem/edit_file_tool.gd",
        '\t"replacements": count,',
        '\t"replacements": count,\n\t"recovery_copy": recovery_path,',
    )

    # Editing a file also requires a recovery copy before the write begins.
    replace_once(
        ADDON_OUT / "scripts/tools/filesystem/edit_file_tool.gd",
        """\tvar write_file := FileAccess.open(resource_path, FileAccess.WRITE)
\tif write_file == null:""",
        """\tvar recovery_dir := ".godot_mcp_backups"
\tvar recovery_error := DirAccess.make_dir_recursive_absolute(globalize_project_path(recovery_dir))
\tif recovery_error != OK:
\t\treturn tool_error("cannot create recovery directory: %s" % error_string(recovery_error))
\tvar recovery_path := "res://%s/%s.%d.bak" % [recovery_dir, resource_path.sha256_text(), Time.get_ticks_usec()]
\tvar recovery_file := FileAccess.open(recovery_path, FileAccess.WRITE)
\tif recovery_file == null:
\t\treturn tool_error("cannot create recovery copy: %s" % error_string(FileAccess.get_open_error()))
\trecovery_file.store_string(original_content)
\trecovery_file.close()
\tif not FileAccess.file_exists(recovery_path):
\t\treturn tool_error("recovery copy was not created; original file was not changed")
\tvar recovery_check := FileAccess.open(recovery_path, FileAccess.READ)
\tif recovery_check == null:
\t\treturn tool_error("recovery copy could not be opened for verification; original file was not changed")
\tvar recovered_text := recovery_check.get_as_text()
\trecovery_check.close()
\tif recovered_text != original_content:
\t\treturn tool_error("recovery copy could not be verified; original file was not changed")
\n\tvar write_file := FileAccess.open(resource_path, FileAccess.WRITE)
\tif write_file == null:"""),
    )

    write_tool = (ADDON_OUT / "scripts/tools/filesystem/write_file_tool.gd").read_text(encoding="utf-8")
    edit_tool = (ADDON_OUT / "scripts/tools/filesystem/edit_file_tool.gd").read_text(encoding="utf-8")
    for label, tool_text in (("write_file", write_tool), ("edit_file", edit_tool)):
        if ".godot_mcp_backups" not in tool_text or "recovery copy" not in tool_text or "var recovery_check := FileAccess.open(recovery_path, FileAccess.READ)" not in tool_text:
            raise RuntimeError(f"{label} is missing recovery-copy protection")

    registry_text = registry.read_text(encoding="utf-8")
    if "ExecuteScriptTool" in registry_text or "delete_project" in registry_text:
        raise RuntimeError("unsafe tool registration detected")
    set_node_tool = (ADDON_OUT / "scripts/tools/scene/set_node_property_tool.gd").read_text(encoding="utf-8")
    remove_node_tool = (ADDON_OUT / "scripts/tools/scene/remove_node_tool.gd").read_text(encoding="utf-8")
    if "get_editor_undo_redo()" not in set_node_tool or "add_undo_property" not in set_node_tool:
        raise RuntimeError("set_node_property is missing editor undo/redo integration")
    if "get_editor_undo_redo()" not in remove_node_tool or "queue_free()" in remove_node_tool:
        raise RuntimeError("remove_node is missing reversible removal safeguards")
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
