#!/usr/bin/env python3
"""Source-only regression checks for the Godot run-bar debug-overlay patch.

This deliberately does not build Godot, run Linux tests, or claim runtime validation.
"""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts" / "apply_github_import_patch.py"
README = ROOT / "README.md"

def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        raise SystemExit(1)
    print(f"PASS: {message}")

require(PATCHER.is_file(), "Godot source patcher exists")
source = PATCHER.read_text(encoding="utf-8")
ast.parse(source, filename=str(PATCHER))
require(True, "patcher has valid Python syntax")

for token, label in [
    ("PREVIEW_DEBUG_COLLISIONS", "collision overlay menu item"),
    ('preview_debug_button->set_text(TTR("COL."))', "compact collision button has a visible toolbar label"),
    ("set_custom_minimum_size(Size2(48, 44))", "collision button has a reliable touch target on mobile"),
    ("Colisiones 2D/3D, formas y raycasts", "collision menu explicitly names 2D/3D shapes and raycasts"),
    ("Area2D/Area3D", "collision menu documents Area2D and Area3D visibility"),
    ("Opciones avanzadas de vista previa", "collision menu button has an accessible name and tooltip"),
    ("PREVIEW_DEBUG_PATHS", "path overlay menu item"),
    ("PREVIEW_DEBUG_NAVIGATION", "navigation overlay menu item"),
    ("PREVIEW_DEBUG_AVOIDANCE", "avoidance overlay menu item"),
    ("PREVIEW_DEBUG_CANVAS_REDRAW", "CanvasItem redraw menu item"),
    ('set_project_metadata("debug_options", metadata_key, enabled)', "per-project debug preference persistence"),
    ("set_debug_collisions(enabled)", "live collision debugger command"),
    ('_put_msg("scene:set_debug_collisions", msg)', "collision remote-debugger message"),
    ('message_handlers["set_debug_collisions"] = _msg_set_debug_collisions', "collision runtime handler registration"),
    ("set_debug_collisions_hint(bool(p_args[0]))", "collision handler changes physics debug state"),
    ("set_debug_navigation(enabled)", "live navigation debugger command"),
    ("set_debug_avoidance(enabled)", "live avoidance debugger command"),
    ("set_debug_paths(enabled)", "live path debugger command"),
    ("set_debug_canvas_item_redraw(enabled)", "live CanvasItem redraw debugger command"),
    ('_put_msg("scene:set_debug_paths", msg)', "path remote-debugger message"),
    ('_put_msg("scene:set_debug_canvas_item_redraw", msg)', "CanvasItem redraw remote-debugger message"),
    ('message_handlers["set_debug_paths"] = _msg_set_debug_paths', "path runtime message handler registration"),
    ('message_handlers["set_debug_canvas_item_redraw"] = _msg_set_debug_canvas_item_redraw', "CanvasItem redraw runtime message handler registration"),
    ("canvas_item_set_debug_redraw(bool(p_args[0]))", "RenderingServer live redraw toggle"),
    ("Android immersive preview mode", "Android immersive preview patch is present"),
    ("mobile_immersive_exit_button->show()", "immersive mode keeps a floating return button"),
    ("title_bar->hide()", "immersive mode hides the editor top bar"),
    ("window_set_mode(DisplayServerEnums::WINDOW_MODE_FULLSCREEN)", "immersive mode requests device fullscreen"),
    ("Size2i(680 * EDSCALE, 560 * EDSCALE)", "GitHub import dialog is sized for mobile readability"),
    ("popup_centered_clamped", "GitHub dialog clamps to available screen size"),
    ("path_2d->debug_update_runtime()", "live Path2D renderer refresh"),
    ("path_3d->debug_update_runtime(enabled)", "live Path3D renderer enable/disable"),
    ("void Path3D::debug_update_runtime(bool p_enabled)", "Path3D creates and updates its runtime debug instance"),
    ('_put_msg("scene:set_debug_navigation", msg)', "navigation remote-debugger message"),
    ('_put_msg("scene:set_debug_avoidance", msg)', "avoidance remote-debugger message"),
    ('message_handlers["set_debug_navigation"] = _msg_set_debug_navigation', "navigation runtime message handler registration"),
    ('message_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance', "avoidance runtime message handler registration"),
]:
    require(token in source, label)

# Keep documentation aligned with the live remote-debugger wiring.
readme = README.read_text(encoding="utf-8") if README.is_file() else ""
require("Visible Paths" in readme and "CanvasItem Redraws" in readme,
        "README documents the run-bar overlay controls")
require("Path2D" in source and "Path3D" in source,
        "runtime path toggle explicitly covers both 2D and 3D path nodes")
require('get_project_metadata("debug_options", debug_keys[i], false)' in source,
        "all five overlay preferences default to disabled for projects without saved settings")
require('EditorDebuggerNode::get_singleton()->set_debug_collisions(enabled)' in source
        and 'EditorDebuggerNode::get_singleton()->set_debug_paths(enabled)' in source
        and 'EditorDebuggerNode::get_singleton()->set_debug_navigation(enabled)' in source
        and 'EditorDebuggerNode::get_singleton()->set_debug_avoidance(enabled)' in source
        and 'EditorDebuggerNode::get_singleton()->set_debug_canvas_item_redraw(enabled)' in source,
        "every menu option is wired to a live remote-debugger command")
require('preview_debug_popup->set_item_checked(preview_debug_popup->get_item_index(i)' in source,
        "menu checkbox state is restored from per-project preferences")
require("queue_redraw()" not in source[source.find("Error SceneDebugger::_msg_set_debug_paths"):source.find("Error SceneDebugger::_msg_set_debug_canvas_item_redraw")],
        "path toggle does not rely on generic CanvasItem redraw as a substitute for Path3D rendering")

print("Source-only checks passed. This does not prove C++ compilation or in-game runtime behavior.")
