#!/usr/bin/env python3
"""Source-only regression checks for the running-game preview debug overlay."""
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
    ("__GodotPreviewDebugOverlay", "debug overlay is created inside the running game window"),
    ('button->set_text("COL.")', "compact COL button is created in the runtime preview"),
    ("set_custom_minimum_size(Size2(60, 44))", "runtime COL button has a mobile touch target"),
    ("_create_runtime_debug_overlay();", "runtime overlay is installed by SceneDebugger"),
    ("_runtime_debug_button_pressed", "runtime button opens its menu"),
    ("_runtime_debug_item_pressed", "runtime menu toggles overlays live"),
    ("callable_mp_static(SceneDebugger, &SceneDebugger::_runtime_debug_item_pressed)", "runtime menu signal is wired"),
    ('popup->add_check_item("Colisiones 2D/3D, formas y raycasts", 0)', "menu contains collision shapes and raycasts"),
    ("rectángulos, círculos, cápsulas, polígonos, cajas 3D, Area2D/Area3D y RayCast2D/3D", "collision tooltip names the supported 2D/3D shape variants and detection areas"),
    ('popup->add_check_item("Rutas Path2D/Path3D", 1)', "menu contains 2D/3D path overlays"),
    ('popup->add_check_item("Mallas de navegación", 2)', "menu contains navigation overlays"),
    ('popup->add_check_item("Áreas y velocidades de evasión", 3)', "menu contains avoidance overlays"),
    ('popup->add_check_item("Redibujado 2D", 4)', "menu contains CanvasItem redraw debugging"),
    ('Mostrar FPS (esquina superior derecha)', "optional FPS counter appears in the existing runtime menu"),
    ('fps_label->set_anchors_and_offsets_preset(Control::PRESET_TOP_RIGHT)', "FPS counter is anchored to the top-right corner"),
    ('fps_label->set_offset(SIDE_TOP, 56)', "FPS counter sits below the COL button"),
    ('fps_label->set_mouse_filter(Control::MOUSE_FILTER_IGNORE)', "FPS counter does not intercept game input"),
    ('Engine::get_singleton()->get_frames_per_second()', "FPS counter reads live engine FPS"),
    ('fps_timer->set_wait_time(0.25)', "FPS counter refreshes at four updates per second"),
    ("set_debug_collisions_hint(bool(p_args[0]))", "collision toggle updates physics debug state"),
    ("path_2d->debug_update_runtime()", "live Path2D renderer refresh"),
    ("path_3d->debug_update_runtime(enabled)", "live Path3D renderer refresh"),
    ("canvas_item_set_debug_redraw(bool(p_args[0]))", "RenderingServer live redraw toggle"),
    ('message_handlers["set_debug_paths"] = _msg_set_debug_paths', "path handler is registered"),
    ('message_handlers["set_debug_canvas_item_redraw"] = _msg_set_debug_canvas_item_redraw', "redraw handler is registered"),
    ("Android immersive preview mode", "Android immersive preview patch is present"),
    ("mobile_immersive_exit_button->show()", "immersive mode keeps a floating return button"),
    ("title_bar->hide()", "immersive mode hides the editor top bar"),
    ("window_set_mode(DisplayServerEnums::WINDOW_MODE_FULLSCREEN)", "immersive mode requests fullscreen"),
    ("set_mobile_immersive_preview(true)", "immersive mode sends a stretch request to the running game"),
    ("set_content_scale_aspect(Window::CONTENT_SCALE_ASPECT_IGNORE)", "running game fills the available screen"),
    ("set_content_scale_mode(mobile_immersive_previous_scale_mode)", "game scaling mode is restored on exit"),
    ("Size2i(680 * EDSCALE, 560 * EDSCALE)", "GitHub import dialog is sized for mobile readability"),
    ("popup_centered_clamped", "GitHub dialog clamps to available screen size"),
    ("void Path3D::debug_update_runtime(bool p_enabled)", "Path3D creates/updates its runtime debug instance"),
]:
    require(token in source, label)

require("preview_debug_button" not in source and "main_hbox->add_child(preview_debug_button)" not in source,
        "COL controls are not placed in the Play/Stop editor run bar")
require("Visible Paths" in README.read_text(encoding="utf-8") and "CanvasItem Redraws" in README.read_text(encoding="utf-8"),
        "README documents the preview debugging controls")
print("Source-only checks passed. This does not prove C++ compilation or in-game runtime behavior.")
