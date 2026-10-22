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
	return "Navigate and operate visible Godot editor controls: buttons, tabs, options, text fields, sliders/ranges, checkboxes, focus, and open PopupMenus. Project deletion controls are always blocked."


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
			"focus": {"type": "boolean", "description": "Focus a control without changing its value."},
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
	if bool(arguments.get("focus", false)):
		control.grab_focus()
		if not arguments.has("text_value") and not arguments.has("numeric_value") and not arguments.has("checked_value") and not arguments.has("tab_index") and not arguments.has("option_index") and not arguments.has("menu_index"):
			return {"ok": true, "path": path, "focused": control.has_focus()}
	if control is TextEdit:
		if not arguments.has("text_value"):
			return tool_error("text_value is required for TextEdit input")
		var text_edit := control as TextEdit
		text_edit.text = String(arguments.get("text_value", ""))
		return {"ok": true, "path": path, "text_length": text_edit.text.length()}
	if control is Range:
		if not arguments.has("numeric_value"):
			return tool_error("numeric_value is required for Range input")
		var range_control := control as Range
		var range_value := float(arguments.get("numeric_value", range_control.value))
		if range_value < range_control.min_value or range_value > range_control.max_value:
			return tool_error("numeric_value is outside the control's range")
		range_control.value = range_value
		return {"ok": true, "path": path, "value": range_control.value}
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
        "scripts/tools/scene/inspect_scene_ui_controls_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "inspect_scene_ui_controls"


func get_description() -> String:
	return "Inspect Control nodes in the currently edited scene, including layout, text, button states, sliders, and option choices. This inspects the scene being edited, not a separate running-game process."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"filter": {"type": "string", "description": "Optional case-insensitive filter by node path, name, class, or text."},
			"max_items": {"type": "integer", "description": "Maximum results, clamped to 1..500."},
		},
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var root := get_edited_scene_root()
	if root == null:
		return tool_error("no scene is currently open for editing")
	var filter_text := String(arguments.get("filter", "")).strip_edges().to_lower()
	var max_items := clampi(int(arguments.get("max_items", 250)), 1, 500)
	var results: Array[Dictionary] = []
	_walk_controls(root, root, filter_text, max_items, results)
	return {
		"ok": true,
		"scene_path": root.scene_file_path,
		"count": results.size(),
		"truncated": results.size() >= max_items,
		"controls": results,
		"scope": "edited_scene_not_separate_runtime_process",
	}


func _walk_controls(node: Node, root: Node, filter_text: String, max_items: int, output: Array[Dictionary]) -> void:
	if output.size() >= max_items:
		return
	if node is Control:
		var control := node as Control
		var node_path := str(root.get_path_to(control))
		var details := _describe_control(control)
		var haystack := (node_path + " " + str(control.name) + " " + control.get_class() + " " + details).to_lower()
		if filter_text == "" or haystack.contains(filter_text):
			output.append({
				"path": node_path,
				"name": str(control.name),
				"class": control.get_class(),
				"visible": control.visible,
				"visible_in_tree": control.is_visible_in_tree(),
				"disabled": control is BaseButton and (control as BaseButton).disabled,
				"rect": {
					"x": control.position.x,
					"y": control.position.y,
					"width": control.size.x,
					"height": control.size.y,
				},
				"details": details,
			})
	for child in node.get_children():
		_walk_controls(child, root, filter_text, max_items, output)


func _describe_control(control: Control) -> String:
	if control is Button:
		return "text=%s; pressed=%s" % [(control as Button).text, str((control as Button).button_pressed)]
	if control is Label:
		return (control as Label).text.left(1000)
	if control is RichTextLabel:
		return (control as RichTextLabel).get_parsed_text().left(1500)
	if control is LineEdit:
		var line_edit := control as LineEdit
		return "placeholder=%s; text=%s" % [line_edit.placeholder_text, "[redacted]" if line_edit.secret else line_edit.text.left(500)]
	if control is TextEdit:
		return (control as TextEdit).text.left(1000)
	if control is Range:
		var range_control := control as Range
		return "value=%s; min=%s; max=%s; step=%s" % [str(range_control.value), str(range_control.min_value), str(range_control.max_value), str(range_control.step)]
	if control is OptionButton:
		var option_button := control as OptionButton
		var options: Array[String] = []
		for index in range(option_button.get_item_count()):
			options.append("%d:%s%s" % [index, option_button.get_item_text(index), " [selected]" if index == option_button.selected else ""])
		return "selected=%d; options=%s" % [option_button.selected, " | ".join(options)]
	if control is CheckBox or control is CheckButton:
		return "text=%s; checked=%s" % [(control as Button).text, str((control as BaseButton).button_pressed)]
	return ""


func get_edited_scene_root() -> Node:
	return editor_interface.get_edited_scene_root()
''',
        "scripts/tools/scene/interact_scene_ui_control_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "interact_scene_ui_control"


func get_description() -> String:
	return "Interact with UI controls in the currently edited scene to exercise a UI before or during preview setup: press buttons, set text/ranges/checks/options, or focus controls. Does not control a separate running-game process."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string", "description": "Exact node path from the edited scene root; obtain it from inspect_scene_ui_controls."},
			"action": {"type": "string", "enum": ["press", "set_text", "set_value", "set_checked", "select_option", "focus"]},
			"text_value": {"type": "string"},
			"numeric_value": {"type": "number"},
			"checked_value": {"type": "boolean"},
			"option_index": {"type": "integer"},
			"submit_text": {"type": "boolean"},
		},
		"required": ["node_path", "action"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var root := editor_interface.get_edited_scene_root()
	if root == null:
		return tool_error("no scene is currently open for editing")
	var path := String(arguments.get("node_path", "")).strip_edges()
	if path == "" or path == ".":
		return tool_error("a specific Control node path is required")
	var node := root.get_node_or_null(NodePath(path))
	if node == null or not node is Control:
		return tool_error("Control node path not found in the edited scene")
	var control := node as Control
	var action := String(arguments.get("action", ""))
	match action:
		"press":
			if not control is BaseButton:
				return tool_error("press requires a Button, CheckBox, CheckButton, or other BaseButton")
			var button := control as BaseButton
			if button.disabled:
				return tool_error("button is disabled")
			if button is CheckBox or button is CheckButton:
				button.button_pressed = not button.button_pressed
			button.emit_signal("pressed")
			return {"ok": true, "path": path, "action": action, "pressed": true}
		"set_text":
			if not arguments.has("text_value"):
				return tool_error("text_value is required")
			if control is LineEdit:
				var line_edit := control as LineEdit
				line_edit.text = String(arguments.get("text_value", ""))
				if bool(arguments.get("submit_text", false)):
					line_edit.emit_signal("text_submitted", line_edit.text)
				return {"ok": true, "path": path, "action": action, "text_length": line_edit.text.length()}
			if control is TextEdit:
				(control as TextEdit).text = String(arguments.get("text_value", ""))
				return {"ok": true, "path": path, "action": action, "text_length": (control as TextEdit).text.length()}
			return tool_error("set_text supports LineEdit and TextEdit")
		"set_value":
			if not control is Range:
				return tool_error("set_value requires a Range control such as Slider, SpinBox, or ProgressBar")
			if not arguments.has("numeric_value"):
				return tool_error("numeric_value is required")
			var range_control := control as Range
			var value := float(arguments.get("numeric_value", range_control.value))
			if value < range_control.min_value or value > range_control.max_value:
				return tool_error("numeric_value is outside the control's range")
			range_control.value = value
			return {"ok": true, "path": path, "action": action, "value": range_control.value}
		"set_checked":
			if not control is CheckBox and not control is CheckButton:
				return tool_error("set_checked requires CheckBox or CheckButton")
			if not arguments.has("checked_value"):
				return tool_error("checked_value is required")
			(control as BaseButton).button_pressed = bool(arguments.get("checked_value", false))
			return {"ok": true, "path": path, "action": action, "checked": (control as BaseButton).button_pressed}
		"select_option":
			if not control is OptionButton:
				return tool_error("select_option requires an OptionButton")
			if not arguments.has("option_index"):
				return tool_error("option_index is required")
			var options := control as OptionButton
			var index := int(arguments.get("option_index", -1))
			if index < 0 or index >= options.get_item_count():
				return tool_error("option_index is outside the available range")
			if options.is_item_disabled(index) or options.is_item_separator(index):
				return tool_error("option is disabled or a separator")
			options.select(index)
			options.emit_signal("item_selected", index)
			return {"ok": true, "path": path, "action": action, "selected_index": index, "selected_text": options.get_item_text(index)}
		"focus":
			control.grab_focus()
			return {"ok": true, "path": path, "action": action, "has_focus": control.has_focus()}
		_:
			return tool_error("unsupported action")
''',
        "scripts/tools/editor/send_editor_viewport_input_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "send_editor_viewport_input"


func get_description() -> String:
	return "Send a targeted mouse or keyboard input event to a SubViewport/SubViewportContainer inside the Godot editor UI tree. This can operate an embedded game preview when its viewport is exposed; it cannot inject input into a separate external game process."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"viewport_path": {"type": "string", "description": "Exact path to a SubViewport or SubViewportContainer under the editor base control."},
			"event_type": {"type": "string", "enum": ["mouse_button", "mouse_motion", "key", "text"]},
			"x": {"type": "number", "description": "Viewport-local horizontal coordinate for mouse events."},
			"y": {"type": "number", "description": "Viewport-local vertical coordinate for mouse events."},
			"button_index": {"type": "integer", "description": "Mouse button: 1 left, 2 right, 3 middle."},
			"pressed": {"type": "boolean", "description": "Pressed state for mouse button or key events."},
			"keycode": {"type": "integer", "description": "Godot Key enum integer for key events."},
			"shift": {"type": "boolean"},
			"ctrl": {"type": "boolean"},
			"alt": {"type": "boolean"},
			"unicode": {"type": "integer", "description": "Unicode codepoint for a key event, if applicable."},
			"text": {"type": "string", "description": "Text for an InputEventText event."},
		},
		"required": ["viewport_path", "event_type"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var base := editor_interface.get_base_control()
	if base == null:
		return tool_error("Godot editor base control is unavailable")
	var path := String(arguments.get("viewport_path", "")).strip_edges()
	if path == "" or path == ".":
		return tool_error("a specific viewport path is required")
	var target := base.get_node_or_null(NodePath(path))
	if target == null:
		return tool_error("viewport path not found under the editor UI")
	var viewport: SubViewport
	if target is SubViewport:
		viewport = target as SubViewport
	elif target is SubViewportContainer:
		for child in target.get_children():
			if child is SubViewport:
				viewport = child as SubViewport
				break
	if viewport == null:
		return tool_error("target is not a SubViewport or a SubViewportContainer containing a SubViewport")
	if not viewport.is_inside_tree():
		return tool_error("target viewport is not inside the editor tree")
	var event_type := String(arguments.get("event_type", ""))
	var event: InputEvent
	match event_type:
		"mouse_button":
			if not arguments.has("x") or not arguments.has("y") or not arguments.has("button_index"):
				return tool_error("mouse_button requires x, y, and button_index")
			var button_index := int(arguments.get("button_index", 1))
			if button_index < 1 or button_index > 3:
				return tool_error("button_index must be 1 (left), 2 (right), or 3 (middle)")
			var mouse := InputEventMouseButton.new()
			mouse.position = Vector2(float(arguments.get("x", 0.0)), float(arguments.get("y", 0.0)))
			mouse.global_position = mouse.position
			mouse.button_index = button_index
			mouse.pressed = bool(arguments.get("pressed", true))
			event = mouse
		"mouse_motion":
			if not arguments.has("x") or not arguments.has("y"):
				return tool_error("mouse_motion requires x and y")
			var motion := InputEventMouseMotion.new()
			motion.position = Vector2(float(arguments.get("x", 0.0)), float(arguments.get("y", 0.0)))
			motion.global_position = motion.position
			event = motion
		"key":
			if not arguments.has("keycode"):
				return tool_error("key requires keycode")
			var key_event := InputEventKey.new()
			key_event.keycode = int(arguments.get("keycode", 0))
			key_event.pressed = bool(arguments.get("pressed", true))
			key_event.shift_pressed = bool(arguments.get("shift", false))
			key_event.ctrl_pressed = bool(arguments.get("ctrl", false))
			key_event.alt_pressed = bool(arguments.get("alt", false))
			key_event.unicode = int(arguments.get("unicode", 0))
			event = key_event
		"text":
			if not arguments.has("text"):
				return tool_error("text event requires text")
			var text_event := InputEventText.new()
			text_event.text = String(arguments.get("text", ""))
			event = text_event
		_:
			return tool_error("unsupported event_type")
	viewport.push_input(event, true)
	return {
		"ok": true,
		"viewport_path": path,
		"event_type": event_type,
		"viewport_size": {"width": viewport.size.x, "height": viewport.size.y},
		"sent": true,
		"scope": "embedded_subviewport_only",
	}
''',
        "scripts/tools/scene/reorder_node_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "reorder_node"


func get_description() -> String:
	return "Reorder a node among its current siblings through Godot's undo/redo history."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string"},
			"new_index": {"type": "integer", "description": "Zero-based child index."},
		},
		"required": ["node_path", "new_index"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")
	if node == get_edited_scene_root():
		return tool_error("cannot reorder the scene root")
	var parent := node.get_parent()
	if parent == null:
		return tool_error("node has no parent")
	var old_index := node.get_index()
	var new_index := int(arguments.get("new_index", -1))
	if new_index < 0 or new_index >= parent.get_child_count():
		return tool_error("new_index is outside the sibling range")
	if new_index == old_index:
		return {"ok": true, "index": old_index, "unchanged": true}
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Reorder Node")
	undo_redo.add_do_method(parent, "move_child", node, new_index)
	undo_redo.add_undo_method(parent, "move_child", node, old_index)
	undo_redo.commit_action()
	return {"ok": true, "node_name": str(node.name), "old_index": old_index, "new_index": new_index, "undo_available": true}
''',
        "scripts/tools/scene/set_node_group_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "set_node_group"


func get_description() -> String:
	return "Add or remove a node from a named group through Godot's undo/redo history."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"node_path": {"type": "string"},
			"group_name": {"type": "string"},
			"enabled": {"type": "boolean", "description": "True adds the group; false removes it."},
		},
		"required": ["node_path", "group_name", "enabled"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var node := resolve_scene_node(String(arguments.get("node_path", ".")))
	if node == null:
		return tool_error("node not found")
	var group_name := String(arguments.get("group_name", "")).strip_edges()
	if group_name == "" or group_name.contains("/") or group_name.contains(":"):
		return tool_error("group_name must be non-empty and cannot contain path separators")
	var enabled := bool(arguments.get("enabled", false))
	var currently_enabled := node.is_in_group(group_name)
	if enabled == currently_enabled:
		return {"ok": true, "group_name": group_name, "enabled": enabled, "unchanged": true}
	var undo_redo := editor_interface.get_editor_undo_redo()
	undo_redo.create_action("MCP: Set Node Group")
	if enabled:
		undo_redo.add_do_method(node, "add_to_group", group_name, true)
		undo_redo.add_undo_method(node, "remove_from_group", group_name)
	else:
		undo_redo.add_do_method(node, "remove_from_group", group_name)
		undo_redo.add_undo_method(node, "add_to_group", group_name, true)
	undo_redo.commit_action()
	return {"ok": true, "node_name": str(node.name), "group_name": group_name, "enabled": enabled, "undo_available": true}
''',
        "scripts/tools/scene/manage_node_signal_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "manage_node_signal"


func get_description() -> String:
	return "Connect or disconnect a signal between nodes in the currently edited scene, with undo/redo support."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"source_path": {"type": "string"},
			"signal_name": {"type": "string"},
			"target_path": {"type": "string"},
			"method_name": {"type": "string"},
			"action": {"type": "string", "enum": ["connect", "disconnect"]},
		},
		"required": ["source_path", "signal_name", "target_path", "method_name", "action"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var source := resolve_scene_node(String(arguments.get("source_path", ".")))
	var target := resolve_scene_node(String(arguments.get("target_path", ".")))
	if source == null or target == null:
		return tool_error("source or target node not found in the edited scene")
	var signal_name := String(arguments.get("signal_name", "")).strip_edges()
	var method_name := String(arguments.get("method_name", "")).strip_edges()
	if signal_name == "" or method_name == "" or method_name.contains("/") or method_name.contains(":"):
		return tool_error("signal_name and method_name must be valid non-empty names")
	if not source.has_signal(signal_name):
		return tool_error("source node does not declare that signal")
	if not target.has_method(method_name):
		return tool_error("target node does not declare that method")
	var callable := Callable(target, method_name)
	var connected := source.is_connected(signal_name, callable)
	var action := String(arguments.get("action", ""))
	if action == "connect":
		if connected:
			return {"ok": true, "connected": true, "unchanged": true}
		var undo_redo := editor_interface.get_editor_undo_redo()
		undo_redo.create_action("MCP: Connect Signal")
		undo_redo.add_do_method(source, "connect", signal_name, callable)
		undo_redo.add_undo_method(source, "disconnect", signal_name, callable)
		undo_redo.commit_action()
		return {"ok": true, "action": action, "source": str(source.name), "signal": signal_name, "target": str(target.name), "method": method_name, "undo_available": true}
	if action == "disconnect":
		if not connected:
			return {"ok": true, "connected": false, "unchanged": true}
		var undo_redo := editor_interface.get_editor_undo_redo()
		undo_redo.create_action("MCP: Disconnect Signal")
		undo_redo.add_do_method(source, "disconnect", signal_name, callable)
		undo_redo.add_undo_method(source, "connect", signal_name, callable)
		undo_redo.commit_action()
		return {"ok": true, "action": action, "source": str(source.name), "signal": signal_name, "target": str(target.name), "method": method_name, "undo_available": true}
	return tool_error("unsupported action")
''',
        "scripts/tools/editor/read_editor_diagnostics_tool.gd": r'''@tool
extends MCPTool


func get_name() -> String:
	return "read_editor_diagnostics"


func get_description() -> String:
	return "Read visible text from Godot editor Output/Debugger/log-style controls, including RichTextLabel and TextEdit content. This reads controls exposed in the editor UI and does not invent diagnostics."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"filter": {"type": "string", "description": "Optional case-insensitive filter against control path, name, class, and text."},
			"max_controls": {"type": "integer", "description": "Maximum controls to return, clamped to 1..100."},
			"max_chars_per_control": {"type": "integer", "description": "Maximum text characters per control, clamped to 100..10000."},
			"visible_only": {"type": "boolean"},
		},
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var base := editor_interface.get_base_control()
	if base == null:
		return tool_error("Godot editor base control is unavailable")
	var filter_text := String(arguments.get("filter", "")).strip_edges().to_lower()
	var max_controls := clampi(int(arguments.get("max_controls", 30)), 1, 100)
	var max_chars := clampi(int(arguments.get("max_chars_per_control", 4000)), 100, 10000)
	var visible_only := bool(arguments.get("visible_only", true))
	var results: Array[Dictionary] = []
	_walk_text_controls(base, base, filter_text, max_controls, max_chars, visible_only, results)
	return {
		"ok": true,
		"count": results.size(),
		"truncated": results.size() >= max_controls,
		"controls": results,
		"note": "Only text controls reachable in the editor UI tree are included; hidden tabs or diagnostics owned by another process may not be exposed.",
	}


func _walk_text_controls(node: Node, base: Node, filter_text: String, max_controls: int, max_chars: int, visible_only: bool, output: Array[Dictionary]) -> void:
	if output.size() >= max_controls:
		return
	if node is Control:
		var control := node as Control
		var visible := control.is_visible_in_tree()
		if (not visible_only or visible) and (control is RichTextLabel or control is TextEdit or control is Label):
			var content := ""
			if control is RichTextLabel:
				content = (control as RichTextLabel).get_parsed_text()
			elif control is TextEdit:
				content = (control as TextEdit).text
			elif control is Label:
				content = (control as Label).text
			var path := str(base.get_path_to(control))
			var haystack := (path + " " + str(control.name) + " " + control.get_class() + " " + content).to_lower()
			if filter_text == "" or haystack.contains(filter_text):
				output.append({
					"path": path,
					"name": str(control.name),
					"class": control.get_class(),
					"visible": visible,
					"text": content.left(max_chars),
					"truncated_text": content.length() > max_chars,
					"total_chars": content.length(),
				})
	for child in node.get_children():
		if output.size() >= max_controls:
			return
		_walk_text_controls(child, base, filter_text, max_controls, max_chars, visible_only, output)
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
        "scripts/tools/editor/install_runtime_game_bridge_tool.gd": r'''@tool
extends MCPTool

const BRIDGE_PATH := "res://addons/godot_mcp_android_runtime/game_runtime_bridge.gd"
const AUTOLOAD_NAME := "GodotMCPRuntimeBridge"
const BRIDGE_SOURCE := """extends Node

const PORT := 37843
const TOKEN := "__GODOT_MCP_RUNTIME_TOKEN__"
const MAX_REQUEST_BYTES := 65536
var _server := TCPServer.new()
var _client: StreamPeerTCP
var _buffer := PackedByteArray()
var _previous_window_mode := DisplayServer.WINDOW_MODE_WINDOWED


func _ready() -> void:
	var error := _server.listen(PORT, "127.0.0.1")
	if error != OK:
		push_error("Godot MCP runtime bridge could not listen on loopback port %d: %s" % [PORT, error_string(error)])


func _process(_delta: float) -> void:
	if _client == null and _server.is_connection_available():
		_client = _server.take_connection()
		_buffer.clear()
	if _client == null:
		return
	_client.poll()
	if _client.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		_client = null
		_buffer.clear()
		return
	var available := _client.get_available_bytes()
	if available > 0:
		if _buffer.size() + available > MAX_REQUEST_BYTES:
			_send_response({"ok": false, "error": "request too large"})
			return
		var packet := _client.get_data(available)
		if packet[0] != OK:
			_client = null
			_buffer.clear()
			return
		_buffer.append_array(packet[1])
		var newline := _buffer.find(10)
		if newline >= 0:
			var request_text := _buffer.slice(0, newline).get_string_from_utf8()
			var parsed = JSON.parse_string(request_text)
			var response: Dictionary
			if parsed is Dictionary:
				response = _handle_request(parsed)
			else:
				response = {"ok": false, "error": "invalid JSON request"}
			_send_response(response)


func _send_response(response: Dictionary) -> void:
	if _client != null and _client.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		_client.put_data((JSON.stringify(response) + "\n").to_utf8_buffer())
	_client = null
	_buffer.clear()


func _handle_request(request: Dictionary) -> Dictionary:
	if String(request.get("token", "")) != TOKEN:
		return {"ok": false, "error": "unauthorized runtime bridge request"}
	var action := String(request.get("action", "status"))
	match action:
		"status":
			return {"ok": true, "running": true, "port": PORT, "scene": get_tree().current_scene.scene_file_path if get_tree().current_scene != null else "", "window_mode": DisplayServer.window_get_mode()}
		"inspect_controls":
			var root := get_tree().current_scene
			if root == null:
				return {"ok": true, "controls": [], "note": "No current scene"}
			var controls: Array[Dictionary] = []
			_walk_controls(root, root, String(request.get("filter", "")).to_lower(), clampi(int(request.get("max_items", 200)), 1, 500), controls)
			return {"ok": true, "count": controls.size(), "controls": controls, "scene": root.scene_file_path}
		"click_control":
			return _click_control(String(request.get("node_path", "")))
		"set_text":
			return _set_control_text(String(request.get("node_path", "")), String(request.get("text", "")))
		"set_value":
			return _set_control_value(String(request.get("node_path", "")), float(request.get("value", 0.0)))
		"set_checked":
			return _set_control_checked(String(request.get("node_path", "")), bool(request.get("checked", false)))
		"select_option":
			return _select_control_option(String(request.get("node_path", "")), int(request.get("index", -1)))
		"mouse_click":
			var position := Vector2(float(request.get("x", 0.0)), float(request.get("y", 0.0)))
			var button := int(request.get("button_index", 1))
			if button < 1 or button > 3:
				return {"ok": false, "error": "button_index must be 1, 2, or 3"}
			_send_mouse_click(position, button)
			return {"ok": true, "action": action, "position": position}
		"key":
			var key_event := InputEventKey.new()
			key_event.keycode = int(request.get("keycode", 0))
			key_event.pressed = bool(request.get("pressed", true))
			key_event.shift_pressed = bool(request.get("shift", false))
			key_event.ctrl_pressed = bool(request.get("ctrl", false))
			key_event.alt_pressed = bool(request.get("alt", false))
			key_event.unicode = int(request.get("unicode", 0))
			Input.parse_input_event(key_event)
			return {"ok": true, "action": action, "keycode": key_event.keycode, "pressed": key_event.pressed}
		"fullscreen":
			_previous_window_mode = DisplayServer.window_get_mode()
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
			return {"ok": true, "window_mode": DisplayServer.window_get_mode()}
		"windowed":
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
			return {"ok": true, "window_mode": DisplayServer.window_get_mode()}
		"toggle_fullscreen":
			if DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN:
				DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
			else:
				_previous_window_mode = DisplayServer.window_get_mode()
				DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
			return {"ok": true, "window_mode": DisplayServer.window_get_mode()}
		_:
			return {"ok": false, "error": "unsupported action"}


func _walk_controls(node: Node, root: Node, filter_text: String, max_items: int, output: Array[Dictionary]) -> void:
	if output.size() >= max_items:
		return
	if node is Control:
		var control := node as Control
		var path := str(root.get_path_to(control))
		var details := ""
		if control is Button:
			details = (control as Button).text
		elif control is Label:
			details = (control as Label).text.left(300)
		elif control is LineEdit:
			var line_edit := control as LineEdit
			details = "placeholder=%s; text=%s" % [line_edit.placeholder_text, "[redacted]" if line_edit.secret else line_edit.text.left(200)]
		elif control is Range:
			var range_control := control as Range
			details = "value=%s; min=%s; max=%s" % [range_control.value, range_control.min_value, range_control.max_value]
		elif control is OptionButton:
			var option_button := control as OptionButton
			var options: Array[String] = []
			for i in range(option_button.get_item_count()):
				options.append("%d:%s" % [i, option_button.get_item_text(i)])
			details = "selected=%d; options=%s" % [option_button.selected, " | ".join(options)]
		var haystack := (path + " " + str(control.name) + " " + control.get_class() + " " + details).to_lower()
		if filter_text == "" or haystack.contains(filter_text):
			output.append({"path": path, "name": str(control.name), "class": control.get_class(), "visible": control.is_visible_in_tree(), "disabled": control is BaseButton and (control as BaseButton).disabled, "rect": {"x": control.get_global_rect().position.x, "y": control.get_global_rect().position.y, "width": control.get_global_rect().size.x, "height": control.get_global_rect().size.y}, "details": details})
	for child in node.get_children():
		_walk_controls(child, root, filter_text, max_items, output)


func _click_control(node_path: String) -> Dictionary:
	var root := get_tree().current_scene
	if root == null or node_path.strip_edges() == "":
		return {"ok": false, "error": "current scene or node_path is missing"}
	var target := root.get_node_or_null(NodePath(node_path))
	if target == null or not target is Control:
		return {"ok": false, "error": "Control path not found in running scene"}
	var control := target as Control
	if not control.is_visible_in_tree():
		return {"ok": false, "error": "Control is not visible"}
	if control is BaseButton:
		var button := control as BaseButton
		if button.disabled:
			return {"ok": false, "error": "Control is disabled"}
		var center := control.get_global_rect().get_center()
		_send_mouse_click(center, MOUSE_BUTTON_LEFT)
		return {"ok": true, "action": "click_control", "path": node_path, "position": center}
	if control is LineEdit or control is TextEdit:
		control.grab_focus()
		return {"ok": true, "action": "focus_control", "path": node_path, "note": "Text input is focused; send key/text input separately"}
	var center := control.get_global_rect().get_center()
	_send_mouse_click(center, MOUSE_BUTTON_LEFT)
	return {"ok": true, "action": "click_control", "path": node_path, "position": center}


func _set_control_text(node_path: String, value: String) -> Dictionary:
	var target := _get_live_control(node_path)
	if target == null:
		return {"ok": false, "error": "Control path not found"}
	if target is LineEdit:
		(target as LineEdit).text = value
	elif target is TextEdit:
		(target as TextEdit).text = value
	else:
		return {"ok": false, "error": "Control is not a LineEdit or TextEdit"}
	return {"ok": true, "action": "set_text", "path": node_path}


func _set_control_value(node_path: String, value: float) -> Dictionary:
	var target := _get_live_control(node_path)
	if target == null:
		return {"ok": false, "error": "Control path not found"}
	if not target is Range:
		return {"ok": false, "error": "Control is not a Range"}
	var range_control := target as Range
	range_control.value = clampf(value, range_control.min_value, range_control.max_value)
	return {"ok": true, "action": "set_value", "path": node_path, "value": range_control.value}


func _set_control_checked(node_path: String, checked: bool) -> Dictionary:
	var target := _get_live_control(node_path)
	if target == null:
		return {"ok": false, "error": "Control path not found"}
	if not target is BaseButton:
		return {"ok": false, "error": "Control is not a button or checkbox"}
	var button := target as BaseButton
	if button.disabled:
		return {"ok": false, "error": "Control is disabled"}
	if not button.toggle_mode and not (button is CheckBox or button is CheckButton):
		return {"ok": false, "error": "Control is not toggleable"}
	button.button_pressed = checked
	return {"ok": true, "action": "set_checked", "path": node_path, "checked": button.button_pressed}


func _select_control_option(node_path: String, index: int) -> Dictionary:
	var target := _get_live_control(node_path)
	if target == null:
		return {"ok": false, "error": "Control path not found"}
	if not target is OptionButton:
		return {"ok": false, "error": "Control is not an OptionButton"}
	var options := target as OptionButton
	if index < 0 or index >= options.get_item_count():
		return {"ok": false, "error": "option index is out of range"}
	if not options.is_item_enabled(index):
		return {"ok": false, "error": "option is disabled"}
	options.select(index)
	options.item_selected.emit(index)
	return {"ok": true, "action": "select_option", "path": node_path, "index": index, "text": options.get_item_text(index)}


func _get_live_control(node_path: String) -> Control:
	var root := get_tree().current_scene
	if root == null or node_path.strip_edges() == "":
		return null
	var target := root.get_node_or_null(NodePath(node_path))
	if target == null or not target is Control:
		return null
	var control := target as Control
	if not control.is_visible_in_tree():
		return null
	return control


func _send_mouse_click(position: Vector2, button_index: int) -> void:
	var down := InputEventMouseButton.new()
	down.position = position
	down.global_position = position
	down.button_index = button_index
	down.pressed = true
	Input.parse_input_event(down)
	var up := down.duplicate() as InputEventMouseButton
	up.pressed = false
	Input.parse_input_event(up)
"""

func get_name() -> String:
	return "install_runtime_game_bridge"


func get_description() -> String:
	return "Install a project-local runtime companion that lets the MCP tools inspect live Control nodes, click them, send keyboard/mouse input, and toggle the running game's fullscreen mode. Makes a verified backup of project.godot before adding an autoload; refuses to overwrite an existing bridge."


func get_input_schema() -> Dictionary:
	return {"type": "object", "properties": {"confirm_install": {"type": "boolean", "description": "Must be true because this adds a project-local script and an autoload entry."}}, "required": ["confirm_install"], "additionalProperties": false}


func execute(arguments: Dictionary) -> Dictionary:
	if not bool(arguments.get("confirm_install", false)):
		return tool_error("confirm_install=true is required to add the runtime bridge autoload")
	if not FileAccess.file_exists("res://project.godot"):
		return tool_error("project.godot not found; open a Godot project first")
	if FileAccess.file_exists(BRIDGE_PATH):
		return tool_error("runtime bridge already exists; refusing to overwrite")
	var bridge_dir := BRIDGE_PATH.get_base_dir()
	var mkdir_error := DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(bridge_dir))
	if mkdir_error != OK:
		return tool_error("cannot create runtime bridge directory: %s" % error_string(mkdir_error))
	var crypto := Crypto.new()
	var runtime_token := crypto.generate_random_bytes(32).hex_encode()
	var bridge_file := FileAccess.open(BRIDGE_PATH, FileAccess.WRITE)
	if bridge_file == null:
		return tool_error("cannot create runtime bridge script: %s" % error_string(FileAccess.get_open_error()))
	bridge_file.store_string(BRIDGE_SOURCE.replace("__GODOT_MCP_RUNTIME_TOKEN__", runtime_token))
	bridge_file.close()
	var project_file := FileAccess.open("res://project.godot", FileAccess.READ)
	if project_file == null:
		return tool_error("cannot read project.godot")
	var original := project_file.get_as_text()
	project_file.close()
	var backup_dir := "res://.godot_mcp_backups"
	var backup_error := DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(backup_dir))
	if backup_error != OK:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(BRIDGE_PATH))
		return tool_error("cannot create project settings backup directory")
	var backup_path := "%s/project.godot.%d.bak" % [backup_dir, Time.get_ticks_usec()]
	var backup := FileAccess.open(backup_path, FileAccess.WRITE)
	if backup == null:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(BRIDGE_PATH))
		return tool_error("cannot create project.godot backup")
	backup.store_string(original)
	backup.close()
	var verify := FileAccess.open(backup_path, FileAccess.READ)
	if verify == null:
		return tool_error("project.godot backup cannot be verified; settings were not changed")
	var backup_text := verify.get_as_text()
	verify.close()
	if backup_text != original:
		return tool_error("project.godot backup verification failed; settings were not changed")
	var entry := AUTOLOAD_NAME + '="*' + BRIDGE_PATH + '"'
	if original.contains(entry) or original.contains(AUTOLOAD_NAME + "="):
		return tool_error("an autoload with this name already exists; no project.godot changes were made")
	var updated := original
	if not updated.contains("[autoload]"):
		updated += "\n\n[autoload]\n" + entry + "\n"
	else:
		var section_start := updated.find("[autoload]")
		var next_section := updated.find("\n[", section_start + 1)
		if next_section == -1:
			updated = updated + "\n" + entry + "\n"
		else:
			updated = updated.insert(next_section + 1, entry + "\n")
	var output := FileAccess.open("res://project.godot", FileAccess.WRITE)
	if output == null:
		return tool_error("cannot write project.godot; backup saved at " + backup_path)
	output.store_string(updated)
	output.close()
	return {"ok": true, "script_path": BRIDGE_PATH, "autoload": AUTOLOAD_NAME, "backup_path": backup_path, "port": 37843, "next_step": "Run the game, then use control_runtime_game with action=status or inspect_controls."}
''',
        "scripts/tools/editor/control_runtime_game_tool.gd": r'''@tool
extends MCPTool

const PORT := 37843


func get_name() -> String:
	return "control_runtime_game"


func get_description() -> String:
	return "Control a running Godot game through the project-local loopback runtime bridge: inspect live UI controls, click controls, send key/mouse input, and enter/exit fullscreen. Requires install_runtime_game_bridge and the game running."


func get_input_schema() -> Dictionary:
	return {
		"type": "object",
		"properties": {
			"action": {"type": "string", "enum": ["status", "inspect_controls", "click_control", "set_text", "set_value", "set_checked", "select_option", "mouse_click", "key", "fullscreen", "windowed", "toggle_fullscreen"]},
			"filter": {"type": "string"},
			"max_items": {"type": "integer"},
			"node_path": {"type": "string"},
			"text": {"type": "string"},
			"value": {"type": "number"},
			"checked": {"type": "boolean"},
			"index": {"type": "integer"},
			"x": {"type": "number"},
			"y": {"type": "number"},
			"button_index": {"type": "integer"},
			"keycode": {"type": "integer"},
			"pressed": {"type": "boolean"},
			"shift": {"type": "boolean"},
			"ctrl": {"type": "boolean"},
			"alt": {"type": "boolean"},
			"unicode": {"type": "integer"}
		},
		"required": ["action"],
		"additionalProperties": false,
	}


func execute(arguments: Dictionary) -> Dictionary:
	var peer := StreamPeerTCP.new()
	var error := peer.connect_to_host("127.0.0.1", PORT)
	if error != OK:
		return tool_error("could not connect to running-game bridge on loopback port %d: %s; install the bridge and start the game first" % [PORT, error_string(error)])
	for attempt in range(20):
		peer.poll()
		if peer.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			break
		OS.delay_msec(10)
	if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return tool_error("runtime bridge is not reachable; ensure the game is running with GodotMCPRuntimeBridge autoload enabled")
	var bridge_file := FileAccess.open("res://addons/godot_mcp_android_runtime/game_runtime_bridge.gd", FileAccess.READ)
	if bridge_file == null:
		peer.disconnect_from_host()
		return tool_error("runtime bridge script is missing; run install_runtime_game_bridge first")
	var bridge_source := bridge_file.get_as_text()
	bridge_file.close()
	var token := ""
	for line in bridge_source.split("\n"):
		if line.begins_with("const TOKEN :="):
			var token_parts := line.split("\"")
			if token_parts.size() >= 2:
				token = token_parts[1]
			break
	if token == "" or token == "__GODOT_MCP_RUNTIME_TOKEN__":
		peer.disconnect_from_host()
		return tool_error("could not read runtime bridge authentication token")
	var request := arguments.duplicate()
	request["token"] = token
	var encoded := (JSON.stringify(request) + "\n").to_utf8_buffer()
	if encoded.size() > 65536:
		peer.disconnect_from_host()
		return tool_error("request exceeds maximum size")
	var write_error := peer.put_data(encoded)
	if write_error != OK:
		peer.disconnect_from_host()
		return tool_error("failed to send runtime command: %s" % error_string(write_error))
	var response_bytes := PackedByteArray()
	for attempt in range(100):
		peer.poll()
		var available := peer.get_available_bytes()
		if available > 0:
			var packet := peer.get_data(available)
			if packet[0] == OK:
				response_bytes.append_array(packet[1])
				if response_bytes.find(10) >= 0:
					break
		OS.delay_msec(10)
	peer.disconnect_from_host()
	if response_bytes.is_empty():
		return tool_error("runtime bridge did not respond before timeout")
	var newline := response_bytes.find(10)
	var response_text := response_bytes.slice(0, newline if newline >= 0 else response_bytes.size()).get_string_from_utf8()
	var parsed = JSON.parse_string(response_text)
	if not parsed is Dictionary:
		return tool_error("runtime bridge returned invalid JSON")
	return parsed
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
        'const InspectSceneUIControlsTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/inspect_scene_ui_controls_tool.gd")\n'
        'const InteractSceneUIControlTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/interact_scene_ui_control_tool.gd")\n'
        'const SendEditorViewportInputTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/send_editor_viewport_input_tool.gd")\n'
        'const ReorderNodeTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/reorder_node_tool.gd")\n'
        'const SetNodeGroupTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/set_node_group_tool.gd")\n'
        'const ManageNodeSignalTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/manage_node_signal_tool.gd")\n'
        'const ReadEditorDiagnosticsTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/read_editor_diagnostics_tool.gd")\n'
        'const GetEditorStateTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/get_editor_state_tool.gd")\n'
        'const InspectEditorUITool := preload("res://addons/godot_mcp_android/scripts/tools/editor/inspect_editor_ui_tool.gd")\n'
        'const ActivateEditorUIControlTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/activate_editor_ui_control_tool.gd")\n'
        'const OpenSceneTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/open_scene_tool.gd")\n'
        'const RunSceneTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/run_scene_tool.gd")\n'
        'const GetNodePropertiesTool := preload("res://addons/godot_mcp_android/scripts/tools/scene/get_node_properties_tool.gd")\n'
        'const CreateResourceTool := preload("res://addons/godot_mcp_android/scripts/tools/resource/create_resource_tool.gd")\n',
        'const InstallRuntimeGameBridgeTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/install_runtime_game_bridge_tool.gd")\n'
        'const ControlRuntimeGameTool := preload("res://addons/godot_mcp_android/scripts/tools/editor/control_runtime_game_tool.gd")\n',
    )
    replace_once(
        registry,
        '\tregister(GetProjectInfoTool.new(editor_interface))\n',
        '\tregister(GetProjectInfoTool.new(editor_interface))\n'
        '\tregister(DuplicateNodeTool.new(editor_interface))\n'
        '\tregister(RenameNodeTool.new(editor_interface))\n'
        '\tregister(ReparentNodeTool.new(editor_interface))\n'
        '\tregister(InspectSceneUIControlsTool.new(editor_interface))\n'
        '\tregister(InteractSceneUIControlTool.new(editor_interface))\n'
        '\tregister(SendEditorViewportInputTool.new(editor_interface))\n'
        '\tregister(ReorderNodeTool.new(editor_interface))\n'
        '\tregister(SetNodeGroupTool.new(editor_interface))\n'
        '\tregister(ManageNodeSignalTool.new(editor_interface))\n'
        '\tregister(ReadEditorDiagnosticsTool.new(editor_interface))\n'
        '\tregister(GetEditorStateTool.new(editor_interface))\n'
        '\tregister(InspectEditorUITool.new(editor_interface))\n'
        '\tregister(ActivateEditorUIControlTool.new(editor_interface))\n'
        '\tregister(OpenSceneTool.new(editor_interface))\n'
        '\tregister(RunSceneTool.new(editor_interface))\n'
        '\tregister(GetNodePropertiesTool.new(editor_interface))\n'
        '\tregister(CreateResourceTool.new(editor_interface))\n',
        '\tregister(InstallRuntimeGameBridgeTool.new(editor_interface))\n'
        '\tregister(ControlRuntimeGameTool.new(editor_interface))\n',
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
        "InspectSceneUIControlsTool",
        "InteractSceneUIControlTool",
        "SendEditorViewportInputTool",
        "ReorderNodeTool",
        "SetNodeGroupTool",
        "ManageNodeSignalTool",
        "ReadEditorDiagnosticsTool",
        "GetEditorStateTool",
        "InspectEditorUITool",
        "ActivateEditorUIControlTool",
        "OpenSceneTool",
        "RunSceneTool",
        "GetNodePropertiesTool",
        "CreateResourceTool",
        "InstallRuntimeGameBridgeTool",
        "ControlRuntimeGameTool",
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
    if "control is Range" not in activate_ui or "control is TextEdit" not in activate_ui or '"focus"' not in activate_ui:
        raise RuntimeError("generic editor UI bridge is missing range, text-editor, or focus operations")
    viewport_input = (ADDON_OUT / "scripts/tools/editor/send_editor_viewport_input_tool.gd").read_text(encoding="utf-8")
    if "SubViewportContainer" not in viewport_input or "viewport.push_input(event, true)" not in viewport_input:
        raise RuntimeError("embedded preview input tool is missing viewport targeting")
    diagnostics = (ADDON_OUT / "scripts/tools/editor/read_editor_diagnostics_tool.gd").read_text(encoding="utf-8")
    if "RichTextLabel" not in diagnostics or "TextEdit" not in diagnostics or "max_chars_per_control" not in diagnostics:
        raise RuntimeError("editor diagnostics reader is missing bounded text extraction")
    if "separate external game process" not in viewport_input:
        raise RuntimeError("embedded preview input tool must document its scope")
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
    for tool_name, required_text in (
        ("reorder_node", "get_editor_undo_redo"),
        ("set_node_group", "add_to_group"),
        ("manage_node_signal", "is_connected"),
    ):
        tool_text = (ADDON_OUT / "scripts/tools/scene" / f"{tool_name}_tool.gd").read_text(encoding="utf-8")
        if required_text not in tool_text:
            raise RuntimeError(f"{tool_name} is missing its required scene operation")
    if "undo_available" not in (ADDON_OUT / "scripts/tools/scene/reorder_node_tool.gd").read_text(encoding="utf-8"):
        raise RuntimeError("reorder_node is missing undo/redo reporting")
    if "_set_owner_recursive" not in (ADDON_OUT / "scripts/tools/scene/duplicate_node_tool.gd").read_text(encoding="utf-8"):
        raise RuntimeError("duplicate_node must preserve scene ownership in descendant nodes")
    inspect_scene_ui = (ADDON_OUT / "scripts/tools/scene/inspect_scene_ui_controls_tool.gd").read_text(encoding="utf-8")
    interact_scene_ui = (ADDON_OUT / "scripts/tools/scene/interact_scene_ui_control_tool.gd").read_text(encoding="utf-8")
    if "get_edited_scene_root()" not in inspect_scene_ui or '"rect"' not in inspect_scene_ui:
        raise RuntimeError("scene UI inspection must report layout geometry")
    for required_action in ['"press"', '"set_text"', '"set_value"', '"set_checked"', '"select_option"', '"focus"']:
        if required_action not in interact_scene_ui:
            raise RuntimeError(f"scene UI interaction is missing action {required_action}")
    if "separate running-game process" not in interact_scene_ui:
        raise RuntimeError("scene UI interaction must state its runtime-preview scope")

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
    runtime_installer = (ADDON_OUT / "scripts/tools/editor/install_runtime_game_bridge_tool.gd").read_text(encoding="utf-8")
    runtime_controller = (ADDON_OUT / "scripts/tools/editor/control_runtime_game_tool.gd").read_text(encoding="utf-8")
    if "BRIDGE_SOURCE" not in runtime_installer or "37843" not in runtime_installer or "project.godot" not in runtime_installer or "generate_random_bytes" not in runtime_installer:
        raise RuntimeError("runtime bridge installer is missing project setup and backup handling")
    for runtime_action in ["inspect_controls", "click_control", "fullscreen", "windowed", "toggle_fullscreen"]:
        if runtime_action not in runtime_installer or runtime_action not in runtime_controller:
            raise RuntimeError(f"runtime game bridge is missing action {runtime_action}")
    if "127.0.0.1" not in runtime_installer or "127.0.0.1" not in runtime_controller or 'request["token"] = token' not in runtime_controller:
        raise RuntimeError("runtime bridge must use loopback-only communication")
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
