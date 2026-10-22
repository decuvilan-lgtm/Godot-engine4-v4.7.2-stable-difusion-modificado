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

    # Expand the editor-facing MCP surface beyond basic scene mutation.
    # These tools use typed, explicit operations; arbitrary execute_script remains disabled.
    extra_tools = {
        "scripts/tools/editor/inspect_editor_ui_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "inspect_editor_ui"


func get_description() -> String:
	return "Inspect the live Godot editor UI tree, including visible menus, docks, tabs, buttons, labels, and their paths."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"filter": {"type": "string", "description": "Optional case-insensitive text filter for names, labels, or paths."},
			"max_items": {"type": "integer", "description": "Maximum results, clamped to 1..500."},
			"visible_only": {"type": "boolean", "description": "Only return controls currently visible in the editor."},
		},
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var base := editor_interface.get_base_control()
	if base == null:
		return tool_error("Godot editor base control is unavailable")
	var filter_text := String(arguments.get("filter", "")).strip_edges().to_lower()
	var max_items := clampi(int(arguments.get("max_items", 200)), 1, 500)
	var visible_only := bool(arguments.get("visible_only", true))
	var items: Array[Dictionary] = []
	_walk_ui(base, base, filter_text, visible_only, max_items, items)
	return {
		"ok": true,
		"count": items.size(),
		"truncated": items.size() >= max_items,
		"controls": items,
	}


func _walk_ui(node: Node, base: Node, filter_text: String, visible_only: bool, max_items: int, output: Array[Dictionary]) -> void:
	if output.size() >= max_items:
		return
	if node is Control:
		var control := node as Control
		if (not visible_only or control.is_visible_in_tree()):
			var label := _control_label(control)
			var path := str(base.get_path_to(control))
			var haystack := (str(control.name) + " " + label + " " + path + " " + control.get_class()).to_lower()
			if filter_text == "" or haystack.contains(filter_text):
				output.append({
					"path": path,
					"name": str(control.name),
					"class": control.get_class(),
					"label": label,
					"visible": control.is_visible_in_tree(),
					"disabled": _is_disabled_control(control),
					"child_count": control.get_child_count(),
				})
	for child in node.get_children():
		if output.size() >= max_items:
			return
		_walk_ui(child, base, filter_text, visible_only, max_items, output)


func _control_label(control: Control) -> String:
	if control is Button:
		return (control as Button).text
	if control is Label:
		return (control as Label).text
	if control is LineEdit:
		var line_edit := control as LineEdit
		var current_text := "[redacted secret input]" if line_edit.secret else line_edit.text.left(500)
		return "placeholder=%s; text=%s" % [line_edit.placeholder_text, current_text]
	if control is TextEdit:
		return (control as TextEdit).text.left(1500)
	if control is RichTextLabel:
		return (control as RichTextLabel).get_parsed_text().left(1500)
	if control is CheckBox or control is CheckButton:
		var check := control as BaseButton
		return "text=%s; checked=%s" % [(control as Button).text, str(check.button_pressed)]
	if control is OptionButton:
		var option_button := control as OptionButton
		var options: Array[String] = []
		for index in range(option_button.get_item_count()):
			options.append("%d:%s%s" % [index, option_button.get_item_text(index), " [selected]" if index == option_button.selected else ""])
		return " | ".join(options)
	if control is SpinBox:
		return "value=%s; min=%s; max=%s; step=%s" % [str((control as SpinBox).value), str((control as SpinBox).min_value), str((control as SpinBox).max_value), str((control as SpinBox).step)]
	if control is TabBar:
		var tab_bar := control as TabBar
		var tabs: Array[String] = []
		for index in range(tab_bar.get_tab_count()):
			tabs.append(tab_bar.get_tab_title(index))
		return " | ".join(tabs)
	if control is PopupMenu:
		var menu := control as PopupMenu
		var entries: Array[String] = []
		for index in range(menu.get_item_count()):
			entries.append("%d:%s" % [index, menu.get_item_text(index)])
		return " | ".join(entries)
	return ""


func _is_disabled_control(control: Control) -> bool:
	if control is BaseButton:
		return (control as BaseButton).disabled
	if control is PopupMenu:
		return not (control as PopupMenu).is_visible_in_tree()
	return false
''',
        "scripts/tools/editor/activate_editor_ui_control_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "activate_editor_ui_control"


func get_description() -> String:
	return "Navigate the live Godot editor by activating visible buttons, switching tabs/options, or choosing an item from an open PopupMenu. Project deletion controls are always blocked."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"path": {"type": "string", "description": "Exact path returned by inspect_editor_ui."},
			"menu_index": {"type": "integer", "description": "For an open PopupMenu only, the zero-based item index."},
			"tab_index": {"type": "integer", "description": "For a TabBar only, the zero-based tab index."},
			"option_index": {"type": "integer", "description": "For an OptionButton only, the zero-based option index."},
			"text_value": {"type": "string", "description": "New text for a LineEdit control."},
			"numeric_value": {"type": "number", "description": "New value for a SpinBox control."},
			"checked_value": {"type": "boolean", "description": "Desired state for a CheckBox or CheckButton."},
			"submit_text": {"type": "boolean", "description": "If true after setting text, emit the LineEdit text_submitted signal."},
			"confirm_destructive": {"type": "boolean", "description": "Must be true for controls whose label suggests a destructive action."},
		},
		"required": ["path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var base := editor_interface.get_base_control()
	if base == null:
		return tool_error("Godot editor base control is unavailable")
	var path := String(arguments.get("path", "")).strip_edges()
	if path == "" or path == ".":
		return tool_error("a specific control path is required")
	var target := base.get_node_or_null(NodePath(path))
	if target == null or not target is Control:
		return tool_error("UI control path not found")
	var control := target as Control
	if not control.is_visible_in_tree():
		return tool_error("control is not currently visible; inspect the UI again after opening its menu or panel")
	var label := _control_label(control).to_lower()
	var control_name := str(control.name).to_lower()
	var danger_text := label + " " + control_name
	var destructive := false
	# Inspect the chosen PopupMenu item below, not every item in the menu.
	if not control is PopupMenu:
		if danger_text.contains("delete project") or danger_text.contains("remove project") or danger_text.contains("erase project"):
			return tool_error("project deletion/removal through generic UI activation is permanently blocked")
		for word in ["delete", "remove", "erase", "clear", "discard", "revert", "overwrite", "uninstall"]:
			if danger_text.contains(word):
				destructive = true
				break
		if destructive and not bool(arguments.get("confirm_destructive", false)):
			return tool_error("potentially destructive UI action requires confirm_destructive=true")
	if control is LineEdit:
		if not arguments.has("text_value"):
			return tool_error("text_value is required for LineEdit input")
		var line_edit := control as LineEdit
		line_edit.text = String(arguments.get("text_value", ""))
		if bool(arguments.get("submit_text", false)):
			line_edit.emit_signal("text_submitted", line_edit.text)
		return {"ok": true, "path": path, "text_length": line_edit.text.length(), "submitted": bool(arguments.get("submit_text", false))}
	if control is SpinBox:
		if not arguments.has("numeric_value"):
			return tool_error("numeric_value is required for SpinBox input")
		var spin_box := control as SpinBox
		var numeric_value := float(arguments.get("numeric_value", spin_box.value))
		if numeric_value < spin_box.min_value or numeric_value > spin_box.max_value:
			return tool_error("numeric_value is outside the SpinBox range")
		spin_box.value = numeric_value
		return {"ok": true, "path": path, "value": spin_box.value}
	if control is CheckBox or control is CheckButton:
		if not arguments.has("checked_value"):
			return tool_error("checked_value is required for CheckBox or CheckButton")
		var check_button := control as BaseButton
		check_button.button_pressed = bool(arguments.get("checked_value", false))
		return {"ok": true, "path": path, "checked": check_button.button_pressed}
	if control is TabBar:
		var tabs := control as TabBar
		if not arguments.has("tab_index"):
			return tool_error("tab_index is required for TabBar navigation")
		var tab_index := int(arguments.get("tab_index", -1))
		if tab_index < 0 or tab_index >= tabs.get_tab_count():
			return tool_error("tab_index is outside the tab range")
		if tabs.is_tab_disabled(tab_index):
			return tool_error("target tab is disabled")
		tabs.current_tab = tab_index
		return {"ok": true, "path": path, "tab_index": tab_index, "tab_title": tabs.get_tab_title(tab_index)}
	if control is OptionButton:
		var options := control as OptionButton
		if not arguments.has("option_index"):
			return tool_error("option_index is required for OptionButton selection")
		var option_index := int(arguments.get("option_index", -1))
		if option_index < 0 or option_index >= options.get_item_count():
			return tool_error("option_index is outside the option range")
		if options.is_item_disabled(option_index) or options.is_item_separator(option_index):
			return tool_error("option is disabled or a separator")
		options.select(option_index)
		options.emit_signal("item_selected", option_index)
		return {"ok": true, "path": path, "option_index": option_index, "option_text": options.get_item_text(option_index)}
	if control is PopupMenu:
		var menu := control as PopupMenu
		if not menu.is_visible():
			return tool_error("PopupMenu is not open")
		if not arguments.has("menu_index"):
			return tool_error("menu_index is required for PopupMenu activation")
		var index := int(arguments.get("menu_index", -1))
		if index < 0 or index >= menu.get_item_count():
			return tool_error("menu_index is outside the menu item range")
		if menu.is_item_disabled(index) or menu.is_item_separator(index):
			return tool_error("menu item is disabled or a separator")
		var item_text := menu.get_item_text(index).to_lower()
		if item_text.contains("delete project") or item_text.contains("remove project") or item_text.contains("erase project"):
			return tool_error("project deletion/removal is permanently blocked")
		for word in ["delete", "remove", "erase", "clear", "discard", "revert", "overwrite", "uninstall"]:
			if item_text.contains(word):
				destructive = true
				break
		if destructive and not bool(arguments.get("confirm_destructive", false)):
			return tool_error("potentially destructive menu action requires confirm_destructive=true")
		menu.activate_item(index)
		return {"ok": true, "path": path, "menu_index": index, "menu_item": menu.get_item_text(index)}
	if control is BaseButton:
		var button := control as BaseButton
		if button.disabled:
			return tool_error("button is disabled")
		if control is CheckBox or control is CheckButton:
			button.button_pressed = not button.button_pressed
		button.emit_signal("pressed")
		return {"ok": true, "path": path, "label": _control_label(control), "activated": true, "pressed": button.button_pressed}
	return tool_error("unsupported control type; only buttons and open PopupMenu items can be activated")


func _control_label(control: Control) -> String:
	if control is Button:
		return (control as Button).text
	if control is Label:
		return (control as Label).text
	if control is PopupMenu:
		var menu := control as PopupMenu
		var entries: Array[String] = []
		for index in range(menu.get_item_count()):
			entries.append("%d:%s" % [index, menu.get_item_text(index)])
		return " | ".join(entries)
	return ""
''',
        "scripts/tools/scene/duplicate_node_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "duplicate_node"


func get_description() -> String:
	return "Duplicate a non-root scene node as a sibling using Godot's undo/redo history."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string", "description": "Path from the edited scene root; use . for the root (root duplication is refused)."},
		},
		"required": ["node_path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")
	var root := get_edited_scene_root()
	if node == root:
		return tool_error("cannot duplicate the scene root as a sibling")
	var parent := node.get_parent()
	if parent == null:
		return tool_error("node has no parent")
	var copy := node.duplicate()
	if copy == null:
		return tool_error("Godot could not duplicate this node")
	var original_index := node.get_index()
	var original_owner = node.owner
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Duplicate Node")
	undo_redo.add_do_method(parent, "add_child", copy)
	undo_redo.add_do_method(parent, "move_child", copy, original_index + 1)
	undo_redo.add_do_method(self, "_set_owner_recursive", copy, original_owner)
	undo_redo.add_undo_method(parent, "remove_child", copy)
	undo_redo.commit_action()
	return {
		"ok": true,
		"source_path": relative_scene_path(node),
		"duplicate_name": str(copy.name),
		"undo_available": true,
	}


func _set_owner_recursive(node: Node, scene_owner: Node) -> void:
	node.owner = scene_owner
	for child in node.get_children():
		_set_owner_recursive(child, scene_owner)
''',
        "scripts/tools/scene/rename_node_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "rename_node"


func get_description() -> String:
	return "Rename a scene node through Godot's undo/redo history."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string", "description": "Path from the edited scene root."},
			"new_name": {"type": "string", "description": "New node name without path separators."},
		},
		"required": ["node_path", "new_name"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")
	var new_name := String(arguments.get("new_name", "")).strip_edges()
	if new_name == "" or new_name.contains("/") or new_name.contains(":") or new_name == "." or new_name == "..":
		return tool_error("new_name is empty or contains a reserved path character")
	var parent := node.get_parent()
	if parent != null:
		var collision := parent.get_node_or_null(NodePath(new_name))
		if collision != null and collision != node:
			return tool_error("a sibling already uses that name")
	var old_name := node.name
	if String(old_name) == new_name:
		return {"ok": true, "path": relative_scene_path(node), "name": new_name, "unchanged": true}
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Rename Node")
	undo_redo.add_do_property(node, "name", StringName(new_name))
	undo_redo.add_undo_property(node, "name", old_name)
	undo_redo.commit_action()
	return {
		"ok": true,
		"old_name": String(old_name),
		"new_name": new_name,
		"undo_available": true,
	}
''',
        "scripts/tools/scene/reparent_node_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "reparent_node"


func get_description() -> String:
	return "Move a node under another node in the edited scene while preserving its order and owner for undo."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string", "description": "Path of the node to move from the edited scene root."},
			"new_parent_path": {"type": "string", "description": "Path of the destination parent; use . for the scene root."},
			"index": {"type": "integer", "description": "Optional child index at the destination; defaults to the end."},
		},
		"required": ["node_path", "new_parent_path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	var new_parent := resolve_scene_node(String(arguments.get("new_parent_path", ".")))
	if node == null or new_parent == null:
		return tool_error("node or destination parent not found")
	var root := get_edited_scene_root()
	if node == root:
		return tool_error("cannot reparent the scene root")
	if node == new_parent or node.is_ancestor_of(new_parent):
		return tool_error("cannot move a node beneath itself or one of its descendants")
	var old_parent := node.get_parent()
	if old_parent == null:
		return tool_error("node has no current parent")
	if new_parent == old_parent:
		return tool_error("node is already under that parent; use the scene tree reorder action instead")
	if new_parent != root and new_parent.owner != root:
		return tool_error("destination must belong to the currently edited scene, not an instanced subscene")
	var old_index := node.get_index()
	var old_owner = node.owner
	var new_index := clampi(int(arguments.get("index", new_parent.get_child_count())), 0, new_parent.get_child_count())
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Reparent Node")
	undo_redo.add_do_method(old_parent, "remove_child", node)
	undo_redo.add_do_method(new_parent, "add_child", node)
	undo_redo.add_do_method(new_parent, "move_child", node, new_index)
	undo_redo.add_do_method(node, "set_owner", old_owner)
	undo_redo.add_undo_method(node, "set_owner", old_owner)
	undo_redo.add_undo_method(old_parent, "move_child", node, old_index)
	undo_redo.add_undo_method(old_parent, "add_child", node)
	undo_redo.add_undo_method(new_parent, "remove_child", node)
	undo_redo.commit_action()
	return {
		"ok": true,
		"node_name": str(node.name),
		"old_parent": str(old_parent.name),
		"new_parent": str(new_parent.name),
		"new_index": new_index,
		"undo_available": true,
	}
''',
        "scripts/tools/editor/get_editor_state_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "get_editor_state"


func get_description() -> String:
	return "Return the current editor scene, open scenes, and play state."


func execute(_arguments: Dictionary) -> Dictionary:
	var root := editor_interface.get_edited_scene_root()
	var scene_path := ""
	var root_name := ""
	var root_type := ""
	if root != null:
		scene_path = root.scene_file_path
		root_name = str(root.name)
		root_type = root.get_class()
	return {
		"ok": true,
		"edited_scene_path": scene_path,
		"root_name": root_name,
		"root_type": root_type,
		"open_scenes": Array(editor_interface.get_open_scenes()),
		"is_playing_scene": editor_interface.is_playing_scene(),
	}
''',
        "scripts/tools/editor/open_scene_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "open_scene"


func get_description() -> String:
	return "Open an existing Godot scene file in the editor."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"path": {"type": "string", "description": "Project-relative scene path, such as res://scenes/level.tscn."},
		},
		"required": ["path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var scene_path := String(arguments.get("path", "")).strip_edges()
	if scene_path == "":
		return tool_error("path is required")
	if not scene_path.begins_with("res://"):
		return tool_error("scene path must begin with res://")
	if not is_safe_project_path(scene_path):
		return tool_error("unsafe scene path")
	if scene_path.get_extension().to_lower() not in ["tscn", "scn"]:
		return tool_error("only .tscn and .scn scene files can be opened")
	if not FileAccess.file_exists(scene_path):
		return tool_error("scene file does not exist")
	editor_interface.open_scene_from_path(scene_path)
	return {
		"ok": true,
		"path": scene_path,
	}
''',
        "scripts/tools/editor/run_scene_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "control_running_scene"


func get_description() -> String:
	return "Start the current scene or main project scene, stop playback, or inspect play state."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"action": {
				"type": "string",
				"enum": ["start_current", "start_main", "stop", "status"],
				"description": "Playback action to perform.",
			},
		},
		"required": ["action"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var action := String(arguments.get("action", "status"))
	match action:
		"start_current":
			if editor_interface.get_edited_scene_root() == null:
				return tool_error("no scene is currently open")
			editor_interface.play_current_scene()
		"start_main":
			var main_scene := String(ProjectSettings.get_setting("application/run/main_scene", ""))
			if main_scene == "":
				return tool_error("the project has no main scene configured")
			if not FileAccess.file_exists(main_scene):
				return tool_error("configured main scene does not exist: %s" % main_scene)
			editor_interface.play_main_scene()
		"stop":
			editor_interface.stop_playing_scene()
		"status":
			pass
		_:
			return tool_error("unsupported action: %s" % action)
	return {
		"ok": true,
		"action": action,
		"is_playing_scene": editor_interface.is_playing_scene(),
	}
''',
        "scripts/tools/scene/get_node_properties_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "get_node_properties"


func get_description() -> String:
	return "List a node's available Godot properties and their Variant types."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string", "description": "NodePath from the edited scene root. Use . for the root."},
			"include_values": {"type": "boolean", "description": "Include simple values as strings; complex values are omitted."},
		},
		"required": ["node_path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")
	var include_values := bool(arguments.get("include_values", false))
	var properties: Array[Dictionary] = []
	for item in node.get_property_list():
		var property_name := String(item.get("name", ""))
		if property_name.begins_with("_"):
			continue
		var entry := {
			"name": property_name,
			"type": int(item.get("type", TYPE_NIL)),
			"usage": int(item.get("usage", 0)),
		}
		if include_values:
			var value = node.get(property_name)
			if value == null or typeof(value) in [TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING, TYPE_STRING_NAME, TYPE_NODE_PATH]:
				entry["value"] = str(value)
			elif typeof(value) in [TYPE_VECTOR2, TYPE_VECTOR2I, TYPE_RECT2, TYPE_RECT2I, TYPE_VECTOR3, TYPE_VECTOR3I, TYPE_VECTOR4, TYPE_VECTOR4I, TYPE_COLOR]:
				entry["value"] = str(value)
		properties.append(entry)
	return {
		"ok": true,
		"path": relative_scene_path(node),
		"class": node.get_class(),
		"properties": properties,
	}
''',
        "scripts/tools/resource/create_resource_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "create_resource"


func get_description() -> String:
	return "Create and save a new Resource of a registered Godot class to a project path."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"class_name": {"type": "string", "description": "Resource class, for example Gradient, Curve, or StandardMaterial3D."},
			"path": {"type": "string", "description": "New project resource path, for example res://resources/material.tres."},
		},
		"required": ["class_name", "path"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var resource_class := String(arguments.get("class_name", "")).strip_edges()
	var resource_path := String(arguments.get("path", "")).strip_edges()
	if resource_class == "" or resource_path == "":
		return tool_error("class_name and path are required")
	if not resource_path.begins_with("res://") or not is_safe_project_path(resource_path):
		return tool_error("resource path must be a safe res:// path")
	if resource_path.get_extension().to_lower() not in ["tres", "res"]:
		return tool_error("resource path must end in .tres or .res")
	if FileAccess.file_exists(resource_path):
		return tool_error("resource path already exists; refusing to overwrite")
	if not ClassDB.class_exists(resource_class) or not ClassDB.can_instantiate(resource_class):
		return tool_error("class cannot be instantiated: %s" % resource_class)
	var instance = ClassDB.instantiate(resource_class)
	if not instance is Resource:
		if instance != null:
			instance.free()
		return tool_error("class is not a Resource: %s" % resource_class)
	var resource: Resource = instance
	var parent_path := resource_path.get_base_dir()
	if parent_path.begins_with("res://") and parent_path != "res://":
		var absolute_parent := ProjectSettings.globalize_path(parent_path)
		var dir_error := DirAccess.make_dir_recursive_absolute(absolute_parent)
		if dir_error != OK:
			resource.free()
			return tool_error("could not create resource directory: %s" % error_string(dir_error))
	var save_error := ResourceSaver.save(resource, resource_path)
	resource.free()
	if save_error != OK:
		return tool_error("could not save resource: %s" % error_string(save_error))
	return {
		"ok": true,
		"class_name": resource_class,
		"path": resource_path,
	}
''',
    }
    for relative_path, source in extra_tools.items():
        target = ADDON_OUT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")

    replace_once(
        registry,
        'const GetProjectInfoTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/get_project_info_tool.gd")\n',
        'const GetProjectInfoTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/get_project_info_tool.gd")\n'
        'const DuplicateNodeTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/duplicate_node_tool.gd")\n'
        'const RenameNodeTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/rename_node_tool.gd")\n'
        'const ReparentNodeTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/reparent_node_tool.gd")\n'
        'const GetEditorStateTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/get_editor_state_tool.gd")\n'
        'const InspectEditorUITool := preload("res://addons/godot_mcp_android/scripts/tools/editor/inspect_editor_ui_tool.gd")\n'
        'const ActivateEditorUIControlTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/activate_editor_ui_control_tool.gd")\n'
        'const OpenSceneTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/open_scene_tool.gd")\n'
        'const RunSceneTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/run_scene_tool.gd")\n'
        'const GetNodePropertiesTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/get_node_properties_tool.gd")\n'
        'const CreateResourceTool := preload("res://addons/godot_mcp_android/scripts/tools/resource/create_resource_tool.gd")\n',
    )
    replace_once(
        registry,
        '\tregister(GetProjectInfoTool.new(editor_interface))\n',
        '\tregister(GetProjectInfoTool.new(editor_interface))\n'
        '\tregister(DuplicateNodeTool.new(editor_interface))\n'
        '\tregister(RenameNodeTool.new(editor_interface))\n'
        '\tregister(ReparentNodeTool.new(editor_interface))\n'
        '\tregister(GetEditorStateTool.new(editor_interface))\n'
        '\tregister(InspectEditorUITool.new(editor_interface))\n'
        '\tregister(ActivateEditorUIControlTool.new(editor_interface))\n'
        '\tregister(OpenSceneTool.new(editor_interface))\n'
        '\tregister(RunSceneTool.new(editor_interface))\n'
        '\tregister(GetNodePropertiesTool.new(editor_interface))\n'
        '\tregister(CreateResourceTool.new(editor_interface))\n',
    )

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

    required_tool_registrations = (
        "DuplicateNodeTool",
        "RenameNodeTool",
        "ReparentNodeTool",
        "GetEditorStateTool",
        "InspectEditorUITool",
        "ActivateEditorUIControlTool",
        "OpenSceneTool",
        "RunSceneTool",
        "GetNodePropertiesTool",
        "CreateResourceTool",
    )
    for registration in required_tool_registrations:
        if registration not in registry_text:
            raise RuntimeError(f"new typed MCP tool is not registered: {registration}")

    inspect_ui = (ADDON_OUT / "scripts/tools/editor/inspect_editor_ui_tool.gd").read_text(encoding="utf-8")
    activate_ui = (ADDON_OUT / "scripts/tools/editor/activate_editor_ui_control_tool.gd").read_text(encoding="utf-8")
    if "get_base_control()" not in inspect_ui or "get_path_to(control)" not in inspect_ui:
        raise RuntimeError("inspect_editor_ui is missing live editor UI traversal")
    if "get_base_control()" not in activate_ui or "activate_item(index)" not in activate_ui:
        raise RuntimeError("activate_editor_ui_control is missing UI activation")
    if "project deletion/removal is permanently blocked" not in activate_ui:
        raise RuntimeError("generic UI activation must permanently block project deletion")
    if "confirm_destructive" not in activate_ui:
        raise RuntimeError("generic UI activation must require confirmation for destructive actions")
    if "text_value" not in activate_ui or "numeric_value" not in activate_ui or "checked_value" not in activate_ui:
        raise RuntimeError("generic UI activation is missing form-control operations")
    for tool_name, required_text in (
        ("duplicate_node", "get_editor_undo_redo"),
        ("rename_node", "get_editor_undo_redo"),
        ("reparent_node", "get_editor_undo_redo"),
    ):
        tool_path = ADDON_OUT / "scripts/tools/scene" / f"{tool_name}_tool.gd"
        tool_text = tool_path.read_text(encoding="utf-8")
        if required_text not in tool_text or "undo_available" not in tool_text:
            raise RuntimeError(f"{tool_name} is missing undo/redo safeguards")
    if "is_ancestor_of(new_parent)" not in (ADDON_OUT / "scripts/tools/scene/reparent_node_tool.gd").read_text(encoding="utf-8"):
        raise RuntimeError("reparent_node is missing cycle prevention")

    open_scene = (ADDON_OUT / "scripts/tools/editor/open_scene_tool.gd").read_text(encoding="utf-8")
    run_scene = (ADDON_OUT / "scripts/tools/editor/run_scene_tool.gd").read_text(encoding="utf-8")
    create_resource = (ADDON_OUT / "scripts/tools/resource/create_resource_tool.gd").read_text(encoding="utf-8")
    if "open_scene_from_path" not in open_scene or "is_safe_project_path" not in open_scene:
        raise RuntimeError("open_scene is missing scene-path validation")
    if "play_current_scene" not in run_scene or "stop_playing_scene" not in run_scene:
        raise RuntimeError("scene playback tool is missing required editor actions")
    if "FileAccess.file_exists(resource_path)" not in create_resource or "ResourceSaver.save" not in create_resource:
        raise RuntimeError("create_resource must refuse overwrite and save via ResourceSaver")
    if "var class_name :=" in create_resource:
        raise RuntimeError("create_resource uses a reserved GDScript identifier")
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
