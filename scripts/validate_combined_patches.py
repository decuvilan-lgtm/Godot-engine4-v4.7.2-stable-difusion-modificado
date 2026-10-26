#!/usr/bin/env python3
"""Cross-feature regression checks after all Godot C++/GDScript patchers have run."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot-source"
FAILURES: list[str] = []


def require(ok: bool, message: str) -> None:
    if not ok:
        FAILURES.append(message)
        print("FAIL: " + message, file=sys.stderr)
    else:
        print("PASS: " + message)


def read(path: Path) -> str:
    if not path.is_file():
        require(False, f"patched source exists: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


editor_node_h = read(GODOT / "editor/editor_node.h")
editor_node_cpp = read(GODOT / "editor/editor_node.cpp")
runbar_h = read(GODOT / "editor/run/editor_run_bar.h")
runbar_cpp = read(GODOT / "editor/run/editor_run_bar.cpp")
debugger_h = read(GODOT / "editor/debugger/editor_debugger_node.h")
debugger_cpp = read(GODOT / "editor/debugger/editor_debugger_node.cpp")
script_debugger_h = read(GODOT / "editor/debugger/script_editor_debugger.h")
script_debugger_cpp = read(GODOT / "editor/debugger/script_editor_debugger.cpp")
scene_debugger_h = read(GODOT / "scene/debugger/scene_debugger.h")
scene_debugger_cpp = read(GODOT / "scene/debugger/scene_debugger.cpp")
native_3d_h = read(GODOT / "editor/scene/3d/node_3d_editor_plugin.h")
native_3d_cpp = read(GODOT / "editor/scene/3d/node_3d_editor_plugin.cpp")
editor_settings_cpp = read(GODOT / "editor/settings/editor_settings.cpp")

# Ensure patchers did not collide and leave duplicate definitions/declarations.
for symbol, source, label in [
    (r"void EditorNode::toggle_mobile_immersive_preview\(\)", editor_node_cpp, "immersive toggle has exactly one definition"),
    (r"void EditorNode::exit_mobile_immersive_preview\(\)", editor_node_cpp, "immersive exit has exactly one definition"),
    (r"void EditorRunBar::_immersive_preview_pressed\(\)", runbar_cpp, "run-bar fullscreen callback has exactly one definition"),
    (r"void EditorDebuggerNode::set_mobile_immersive_preview\(bool p_enabled\)", debugger_cpp, "editor debugger forwarding has exactly one definition"),
    (r"void ScriptEditorDebugger::set_mobile_immersive_preview\(bool p_enable\)", script_debugger_cpp, "remote debugger forwarding has exactly one definition"),
    (r"Error SceneDebugger::_msg_set_mobile_immersive_preview\(const Array &p_args\)", scene_debugger_cpp, "runtime immersive handler has exactly one definition"),
    (r"void SceneDebugger::_runtime_debug_button_pressed\(\)", scene_debugger_cpp, "preview overlay button callback has exactly one definition"),
    (r"void SceneDebugger::_runtime_debug_item_pressed\(int p_id\)", scene_debugger_cpp, "preview overlay menu callback has exactly one definition"),
    (r"void Node3DEditorViewport::_update_native_navigation_control_layout\(\)", native_3d_cpp, "native joystick layout updater has exactly one definition"),
]:
    require(len(re.findall(symbol, source)) == 1, label)

for symbol, source, label in [
    ("toggle_mobile_immersive_preview", editor_node_h, "EditorNode declares the fullscreen toggle"),
    ("exit_mobile_immersive_preview", editor_node_h, "EditorNode declares fullscreen exit"),
    ("_immersive_preview_pressed", runbar_h, "run bar declares fullscreen callback"),
    ("set_mobile_immersive_preview", debugger_h, "editor debugger declares fullscreen forwarding"),
    ("set_mobile_immersive_preview", script_debugger_h, "script debugger declares fullscreen forwarding"),
    ("_msg_set_mobile_immersive_preview", scene_debugger_h, "runtime debugger declares fullscreen handler"),
    ('message_handlers["set_mobile_immersive_preview"]', scene_debugger_cpp, "runtime message is registered"),
    ("_update_native_navigation_control_layout", native_3d_h, "native 3D viewport declares joystick relayout"),
    ("native_joystick_size", editor_settings_cpp, "native joystick size setting is registered"),
    ("native_joystick_inset_x", editor_settings_cpp, "native joystick horizontal position setting is registered"),
    ("native_joystick_inset_y", editor_settings_cpp, "native joystick vertical position setting is registered"),
    ("position_control->set_custom_minimum_size(Size2(native_size, native_size)", native_3d_cpp, "native left joystick uses configured size"),
    ("_update_native_navigation_control_layout();", native_3d_cpp, "native joysticks relayout at creation and on settings changes"),
    ("play_button = memnew(Button);", runbar_cpp, "native Run control remains present"),
    ("is_playing()", runbar_cpp, "fullscreen toggle is blocked until a game is running"),
    ("mobile_immersive_exit_button->show()", editor_node_cpp, "fullscreen mode exposes a return control"),
    ("mobile_immersive_exit_button->hide()", editor_node_cpp, "return control is hidden after exiting fullscreen"),
    ("project_run_bar->hide()", editor_node_cpp, "black preview run bar is hidden in immersive fullscreen"),
    ("project_run_bar->show()", editor_node_cpp, "preview run bar is restored on exit"),
    ("set_distraction_free_mode(mobile_previous_distraction_free)", editor_node_cpp, "editor distraction-free state is restored"),
    ("enable_immersive_mode(mobile_previous_system_immersive)", editor_node_cpp, "Android system-bar state is restored"),
    ("_create_runtime_debug_overlay()", scene_debugger_cpp, "runtime overlay can be initialized after the game window exists"),
    ('popup->add_check_item("Colisiones 2D/3D, formas y raycasts", 0)', scene_debugger_cpp, "collision overlay remains integrated"),
    ('popup->add_check_item("Rutas Path2D/Path3D", 1)', scene_debugger_cpp, "path overlay remains integrated"),
]:
    require(symbol in source, label)

sync = read(ROOT / "scripts/github_sync_addon/plugin.gd")
terrain = read(ROOT / "scripts/terrain_3d_addon/terrain_editor_plugin.gd")
require("Sincronizar GitHub" in sync, "GitHub sync button remains available in the open editor")
require("_build_incremental_download_queue()" in sync and "_git_blob_sha1" in sync, "incremental sync compares actual local content with verified upstream blobs")
require("_build_change_plan()" in sync and '"kind": "delete"' in sync, "tracked upstream deletions remain in the change plan")
require("_copy_file_streaming(staged_path, local_path)" in sync, "sync replaces files in place without making duplicate backups")
require("GitHub → Godot" in sync or "GITHUB → GODOT" in sync, "sync remains one-way and reports direction")
require("EditorInterface.open_scene_from_path(scene_path)" in sync, "scene organization opens scene tabs instead of flattening node trees")
require("state.get_node_instance(node_index)" in sync, "scene organization follows nested PackedScene instances")
require("PackedScene" in sync and "get_state()" in sync, "scene hierarchy traversal uses serialized scene state")
require("_is_native_joystick_zone(event.position)" in terrain, "terrain pencil does not capture native joystick zones")
require("event.index == pencil_touch_index and not pencil_touch_cancelled" in terrain, "multitouch cancellation cannot resume the same pencil gesture")
require("left_zone.has_point(position) or right_zone.has_point(position)" in terrain, "native joystick areas use their exact touch bounds")
require("action_button.set_offset(Control.SIDE_BOTTOM, -178.0 * scale)" in terrain, "ACTION is anchored above the native left joystick")
require("_create_terrain()" in terrain[terrain.index("func _toggle_panel()"):terrain.index("func _create_terrain()")], "terrain editor opens on an editable base")
require("terrain_tabs.current_tab not in [1, 2]" in terrain, "terrain viewport editing is limited to Sculpt/Paint tabs")

if FAILURES:
    raise SystemExit(f"{len(FAILURES)} combined patch/regression check(s) failed.")
print("PASS: combined patch compatibility and cross-feature regression checks passed.")
