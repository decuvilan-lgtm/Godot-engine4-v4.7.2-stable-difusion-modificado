#!/usr/bin/env python3
"""Static source checks for the separate 3D terrain editor addon."""
from pathlib import Path
import ast
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "scripts/terrain_3d_addon"
PLUGIN = ADDON / "terrain_editor_plugin.gd"
DATA = ADDON / "terrain_data.gd"
CFG = ADDON / "plugin.cfg"
PATCHER = ROOT / "scripts/apply_github_sync_patch.py"

FAILURES: list[str] = []

def require(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print("FAIL: " + message, file=sys.stderr)
    else:
        print("PASS: " + message)

require(all(path.is_file() for path in (PLUGIN, DATA, CFG, PATCHER)), "terrain addon and embedding patch exist")
plugin = PLUGIN.read_text(encoding="utf-8")
data = DATA.read_text(encoding="utf-8")
patcher = PATCHER.read_text(encoding="utf-8")
ast.parse(patcher, filename=str(PATCHER))
require(True, "terrain embedding patcher has valid Python syntax")
require("return slider\n\n\t_update_action_overlay_visibility()" not in plugin,
        "terrain overlay refresh is not stranded after an unconditional return")
wall_order = ("_add_custom_vertex(st, top_a, color_a, weight_a, uv_a)\n\t_add_custom_vertex(st, top_b, color_b, weight_b, uv_b)\n\t_add_custom_vertex(st, bottom_a, color_a, weight_a, uv_a)")
require(wall_order in data, "terrain perimeter wall triangles face outward")

for token, label in [
    ("CONTAINER_SPATIAL_EDITOR_MENU", "separate 3D editor toolbar entry"),
    ("_create_terrain_preview", "terrain preview support remains available"),
    ('intro.text = "Terreno integrado en la escena de Godot. La base inicial es de 8 × 8 bloques y se crea al abrir esta herramienta. Selecciona el nodo Terrain3D en el árbol de escena para cambiar geometría, resolución y materiales desde el Inspector nativo."', "terrain dock directs geometry configuration to native Inspector"),
    ('terrain.initialize_grid(9, 9, 1.0)', "new terrain mesh is generated before insertion at eight by eight cells"),
    ('fallback_floor.size = Vector2(8.0, 8.0)', "a visible 8x8 plane is used if mesh generation fails"),
    ('terrain.set("footprint_shape", 0)', "new terrain starts with a square footprint"),
    ('terrain.set("base_thickness", 2.0)', "new terrain starts with a default base thickness"),
    ('terrain.set("max_height", 100.0)', "new terrain starts with a default height range"),
    ("PlaneMesh", "square/rectangular preview follows the chosen dimensions"),
    ("CylinderMesh.new()", "circular terrain preview follows the selected footprint"),
    ("terrain.set(\"footprint_shape\"", "creation applies the selected footprint shape"),
    ("terrain.set(\"base_thickness\"", "creation applies the selected volume thickness"),
    ("terrain.set(\"max_height\"", "creation applies the selected vertical range"),
    ("class TerrainInspectorTools extends EditorInspectorPlugin:", "terrain sculpt/paint tools are hosted by the native Inspector"),
    ("add_inspector_plugin(inspector_tools)", "terrain tool controls register through Godot's Inspector plugin API"),
    ("add_custom_control(tools)", "terrain tool tabs are injected into the selected terrain's Inspector"),
    ("tools.show()", "terrain Inspector controls become visible again whenever the terrain is reselected"),
    ('undo_redo.add_do_method(terrain, "rebuild_collision")', "terrain collision is rebuilt after scene ownership is assigned so it persists on save/reopen"),
    ("panel.get_parent().remove_child(panel)", "Inspector controls detach cleanly when the plugin exits"),
    ("_update_terrain_preview()", "terrain button opens/selects the terrain without toggling a separate dock"),
    ("EditorInterface.get_selection().add_node(terrain)\n\t\t_focus_terrain()", "opening the terrain workspace selects the terrain node for the native Inspector"),
    ("var local: Vector3 = terrain.to_local(world_position)", "brush local coordinates have an explicit Vector3 type"),
    ("var center: Vector3 = terrain.global_position", "terrain focus center has an explicit Vector3 type"),
    ("panel.custom_minimum_size = Vector2(0, 0)", "terrain dock does not force a wider custom column"),
    ("func _refresh_ui_scale() -> void:", "terrain controls refresh their touch sizing when editor scale changes"),
    ("panel.visibility_changed.connect(_update_action_overlay_visibility)", "ACTION overlay hides when the native dock is closed"),
    ("editor_settings.settings_changed.connect(_refresh_ui_scale)", "terrain listens for editor scale setting changes"),
    ('pencil_sensitivity = _add_slider(panel, "Sensibilidad del lápiz (0–100)"', "pencil sensitivity slider ranges from 0 to 100"),
    ('action_button.text = "ACCIÓN"', "single reusable action button is available"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_left_size")', "action positioning reads the native left joystick size setting"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_left_inset_x")', "action positioning reads the native left joystick horizontal inset"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_left_inset_y")', "action positioning reads the native left joystick vertical inset"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_right_size")', "pencil zones read the native right joystick size setting"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_right_inset_x")', "pencil zones read the native right joystick horizontal inset"),
    ('settings.get_setting("editors/3d/navigation/native_joystick_right_inset_y")', "pencil zones read the native right joystick vertical inset"),
    ("pencil_touch_index", "pencil tracks a single touch identifier"),
    ("pencil_touch_cancelled", "multitouch cancels pencil ownership without consuming another finger"),
    ("_is_native_joystick_zone(event.position)", "native joystick touch zones are excluded from pencil ownership"),
    ("Rect2(Vector2(left_x, size.y - left_size - left_y), Vector2(left_size, left_size))", "pencil exclusion matches the actual independently configurable left joystick footprint"),
    ("Rect2(Vector2(size.x - right_size - right_x, size.y - right_size - right_y), Vector2(right_size, right_size))", "pencil exclusion matches the actual independently configurable right joystick footprint"),
    ('event is InputEventScreenDrag and event.index == pencil_touch_index and not pencil_touch_cancelled', "cancelled pencil gestures cannot reactivate from later drags"),
    ('if not pencil_active or not cursor_valid:', "action button refuses to edit until pencil is active on terrain"),
    ('_bind_editor_float_setting(pencil_sensitivity, "terrain_3d/pencil_sensitivity"', "pencil sensitivity persists through Godot editor settings"),
    ('add_inspector_plugin(inspector_tools)', "terrain editing controls live in the native Inspector"),
    ('action_overlay.add_child(action_button)', "single ACTION button overlays the 3D workspace instead of living in the dock"),
    ('var bottom := (joystick_size + inset_y + 20.0) * scale', "ACTION button stays above the native left joystick as its size/position changes"),
    ('terrain_tabs.tab_changed.connect', "ACTION visibility follows the selected terrain tool tab"),
    ('pencil_screen_position.move_toward(pencil_target_position', "pencil sensitivity controls cursor speed"),
    ("sensitivity * 12.0 * delta", "sensitivity value maps to a predictable pixels-per-second cursor speed"),
    ('cursor_material.albedo_color = Color(1.0, 0.82, 0.2, 0.9) if pencil_active else Color(0.05, 0.05, 0.05, 0.65)', "pencil visibly changes color when active/inactive"),
    ("return AFTER_GUI_INPUT_PASS", "terrain input is passed through to native Godot controls"),
    ("_forward_3d_gui_input", "3D viewport mouse/touch input is handled"),
    ("panel.is_inside_tree() and panel.visible", "terrain touch tools are active only while Inspector controls are present"),
    ("selection_changed.connect(_update_action_overlay_visibility)", "ACTION overlay tracks selection changes instead of lingering after deselection"),
    ("set_input_event_forwarding_always_enabled()", "terrain viewport input remains available without selection-dependent forwarding"),
    ("if (panel == null or not panel.is_inside_tree() or not panel.visible) and not stroke_active and not collision_dirty and not action_held:", "terrain editor avoids idle polling when Inspector tools are not attached"),
    ("_raycast_terrain", "cursor uses a 3D raycast"),
    ("Elevar", "raise brush"),
    ("Bajar", "lower brush"),
    ("Suavizar", "smooth brush"),
    ("Aplanar", "flatten brush"),
    ("Pintar color", "vertex-color painting"),
    ("Pintar capa de material", "four paintable terrain material layers"),
    ('for mode in ["Elevar", "Bajar", "Suavizar", "Aplanar"]:', "sculpt tool selector has valid loop syntax"),
    ('paint_mode_picker.add_item("Pintar color")', "color painting is available in the Paint tab"),
    ('paint_mode_picker.add_item("Pintar capa de material")', "material-layer painting is available in the Paint tab"),
    ("func _make_tab_page", "terrain editor options are separated into scrollable tabs"),
    ("scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_ALWAYS", "native vertical scrollbar stays visible for direct dragging"),
    ("scroll.scroll_deadzone = 4", "inner tab touch drags claim scrolling quickly to reduce accidental option activation"),
    ("inspector_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_ALWAYS", "the complete native Inspector injection has a permanently visible vertical scrollbar"),
    ("inspector_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED", "the mobile Inspector avoids horizontal overflow"),
    ("inspector_scroll.scroll_deadzone = 4", "outer Inspector touch drags start scrolling before accidental child activation"),
    ("inspector_scroll.add_child(inspector_content)", "all top-level terrain controls live inside the scrollable Inspector content"),
    ("panel.add_child(inspector_scroll)", "the complete terrain Inspector section is scrollable"),
    ("content.custom_minimum_size = Vector2(0, 0)", "tab content does not force a minimum width that overflows narrow phones"),
    ("func _add_spin(parent: Control, label_text: String", "numeric controls use a responsive vertical layout"),
    ("func _make_labeled_control(label_text: String, control: Control) -> VBoxContainer:", "labeled options stack vertically to fit the native Inspector column"),
    ('_make_tab_page(terrain_tabs, "Inicio")', "dedicated interface has an overview tab"),
    ('_make_tab_page(terrain_tabs, "Esculpir")', "dedicated interface has a sculpting tab"),
    ('_make_tab_page(terrain_tabs, "Pintar")', "dedicated interface has a painting tab"),
    ('_make_tab_page(terrain_tabs, "Vegetación")', "dedicated interface has a foliage tab"),
    ('_make_tab_page(terrain_tabs, "Heightmaps")', "dedicated interface has a heightmap tab"),
    ("while root.has_node(NodePath(\"Terrain3D_%d\" % suffix)):", "terrain creation avoids node-name collisions"),
    ("terrain.heights.size() != terrain.grid_width * terrain.grid_depth", "heightmap export rejects incomplete terrain data"),
    ("var min_x := clampi(", "brush work is limited to the affected vertex region"),
    ("_set_heights_deferred", "height edits defer collision rebuilds until the stroke ends"),
    ("collision_dirty and not stroke_active and not action_held", "collision rebuild is coalesced after touch/mouse strokes"),
    ("_commit_terrain_change", "terrain edits use editor undo/redo"),
    ("Importar heightmap", "heightmap import UI"),
    ("Exportar heightmap", "heightmap export UI"),
    ("var minimum := INF", "heightmap export normalizes to the actual height range"),
    ("Distribuir árboles", "foliage scatter UI"),
    ("Regenerar colisiones", "collision rebuild UI"),
    ("Ajustar pincel a cuadrícula", "optional brush snapping"),
    ("Enfocar terreno en la vista 3D", "viewport recenter/focus control"),
]:
    require(token in plugin, label)
toggle_body = plugin[plugin.index("func _toggle_panel()"):plugin.index("func _create_terrain()")]
require("_create_terrain()" in toggle_body, "opening Terreno 3D creates its initial editable terrain when absent")
require("terrain_width = _add_spin(home" not in plugin and "terrain_depth = _add_spin(home" not in plugin, "geometry configuration is not duplicated in the custom dock")
require("create_button.text = \"Crear terreno\"" not in plugin, "terrain creation is automatic when opening the workspace")

for token, label in [
    ("@export_enum(\"Cuadrada / rectangular\", \"Circular / elíptica\") var footprint_shape: int = 0:", "terrain footprint is exposed as a native Inspector property and rebuilds geometry"),
    ("@export_range(0.1, 100.0, 0.1) var base_thickness: float = 2.0:", "terrain base thickness is exposed as a native Inspector property and rebuilds geometry"),
    ("@export_range(1.0, 1000.0, 1.0) var max_height: float = 100.0:", "terrain height range is exposed as a native Inspector property without destroying sculpted values"),
    ("SurfaceTool", "procedural terrain mesh"),
    ("@export_range(9, 257, 1) var grid_width: int = 9:", "new terrain defaults to nine vertices across, making an eight-unit footprint"),
    ("@export_range(9, 257, 1) var grid_depth: int = 9:", "new terrain defaults to nine vertices deep, making an eight-unit footprint"),
    ("@export_range(0.1, 100.0, 0.1) var base_thickness: float = 2.0:", "terrain base defaults to two units thick"),
    ("_add_bottom_vertex", "terrain mesh includes an underside"),
    ("_add_wall(st", "terrain mesh creates perimeter walls for a solid volume"),
    ("st.index()", "indexed terrain mesh avoids tripled vertex storage on mobile"),
    ("is_finite(height)", "reject non-finite/corrupt height values before mesh generation"),
    ("mesh == null", "mesh generation failure is handled safely"),
    ("collision.shape == null", "collision generation failure is handled safely"),
    ("create_trimesh_shape", "terrain collision generation"),
    ("if mesh != null and (collision_body == null or not is_instance_valid(collision_body))", "saved terrains missing a collision child recover it when opened"),
    ("set_heights", "editable height data"),
    ("set_vertex_colors", "editable vertex color data"),
    ("set_layer_weights", "editable four-channel material weights"),
    ("NoiseTexture2D", "procedural texture generation for material layers"),
    ("@export_storage var heights", "terrain heights persist in saved scenes"),
    ("@export_group(\"Geometría\")", "terrain geometry properties are grouped in the native Inspector"),
    ("@export_range(9, 257, 1) var grid_width: int = 9:", "grid width defaults to the intended 8-unit footprint and remains editable in the native Inspector"),
    ("@export_range(9, 257, 1) var grid_depth: int = 9:", "grid depth defaults to the intended 8-unit footprint and remains editable in the native Inspector"),
    ("func _resize_grid_preserving_data", "programmatic grid-size changes preserve sculpted height/color/material data"),
    ("func _sample_float_grid", "terrain resizing resamples height data instead of discarding it"),
    ("@export_group(\"Material\")", "terrain texture options are grouped in the native Inspector"),
    ('@export var grass_texture: Texture2D:', "grass texture is exposed in native Inspector"),
    ('@export var rock_texture: Texture2D:', "rock texture is exposed in native Inspector"),
    ('@export var sand_texture: Texture2D:', "sand texture is exposed in native Inspector"),
    ('@export var snow_texture: Texture2D:', "snow texture is exposed in native Inspector"),
    ("if terrain_material:\n\t\t\tterrain_material.set_shader_parameter(\"use_full_surface_texture\"", "Inspector texture changes update the terrain material live"),
    ("create_foliage", "procedural foliage placement"),
    ("var canopy_mesh := CylinderMesh.new()", "foliage canopy uses a Godot 4.7 built-in mesh primitive"),
]:
    require(token in data, label)
require("_cell_inside_footprint" in data, "terrain mesh supports a non-rectangular footprint")
require("TERRAIN_DATA_GD" in patcher and "res://addons/terrain_3d/plugin.cfg" in patcher,
        "ZIP-installed projects receive and enable the terrain addon")
print("Static source checks only; GDScript parsing, Android resource compilation and viewport runtime are still required.")


# Full-surface image import should be distinct from heightmaps and layer painting.
require("Reemplazar superficie con imagen" in plugin, "full-surface image picker is exposed in the terrain UI")
require('surface_texture_dialog.add_filter("*.png,*.jpg,*.jpeg,*.webp"' in plugin, "image picker accepts common gallery image formats")
require("stretch_surface_image" not in plugin and "terrain.stretch_full_surface_texture" in plugin, "surface mapping uses the native Inspector property without duplicate dock control")
require("set_full_surface_texture" in data, "full-surface image assignment can be undone and restored")
require("uniform sampler2D full_surface_texture" in data, "terrain shader supports a dedicated full-surface image")
require("use_full_surface_texture" in data, "terrain shader can switch between image and material layers")
require("stretch_full_surface_texture" in data, "terrain shader supports stretched or repeated image mapping")

require('var terrain_tabs: TabContainer' in plugin, 'terrain editor uses a native tab container')
require('paint_mode_picker = OptionButton.new()' in plugin, 'paint modes live in the Paint tab')
require('terrain_tabs.current_tab not in [1, 2]' in plugin, 'brush editing is restricted to Sculpt/Paint tabs')
require(re.search(r'(?m)^\s*mode_picker\.add_item\("Pintar color"\)', plugin) is None, 'sculpt selector does not contain paint modes')


# Regression guards for the two runtime errors found on the Android device.
require("settings.save()" not in plugin, "terrain editor does not call the nonexistent EditorSettings.save() method")
require("not panel.is_queued_for_deletion()" in plugin, "terrain Inspector never reuses a panel already queued for deletion")
require("panel = null\n\t_build_panel()" in plugin, "terrain Inspector rebuilds stale panel references before reattaching controls")
require("not editor_selection.selection_changed.is_connected(_update_action_overlay_visibility)" in plugin, "terrain selection signal is guarded against duplicate connections")
require("editor_selection.selection_changed.disconnect(_update_action_overlay_visibility)" in plugin, "terrain selection signal is disconnected when the addon exits the tree")
require("editor_settings.settings_changed.disconnect(_refresh_ui_scale)" in plugin, "editor settings signal is disconnected when the addon exits the tree")
surface_begin = data.find("st.begin(Mesh.PRIMITIVE_TRIANGLES)")
surface_custom = data.find("st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA8_UNORM)")
require(surface_begin >= 0 and surface_custom > surface_begin, "SurfaceTool begins the surface before configuring its custom vertex channel")

if FAILURES:
    raise SystemExit(f"{len(FAILURES)} terrain source check(s) failed; see all FAIL lines above.")
