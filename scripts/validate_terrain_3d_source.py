#!/usr/bin/env python3
"""Static source checks for the separate 3D terrain editor addon."""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "scripts/terrain_3d_addon"
PLUGIN = ADDON / "terrain_editor_plugin.gd"
DATA = ADDON / "terrain_data.gd"
CFG = ADDON / "plugin.cfg"
PATCHER = ROOT / "scripts/apply_github_sync_patch.py"

def require(condition: bool, message: str) -> None:
    if not condition:
        print("FAIL: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: " + message)

require(all(path.is_file() for path in (PLUGIN, DATA, CFG, PATCHER)), "terrain addon and embedding patch exist")
plugin = PLUGIN.read_text(encoding="utf-8")
data = DATA.read_text(encoding="utf-8")
patcher = PATCHER.read_text(encoding="utf-8")
ast.parse(patcher, filename=str(PATCHER))
require(True, "terrain embedding patcher has valid Python syntax")
for token, label in [
    ("CONTAINER_SPATIAL_EDITOR_MENU", "separate 3D editor toolbar entry"),
    ("_create_terrain_preview", "pre-creation terrain footprint preview"),
    ("PlaneMesh", "square/rectangular preview follows the chosen dimensions"),
    ("CylinderMesh.new()", "circular terrain preview follows the selected footprint"),
    ("shape_picker.add_item(\"Circular / elíptica\", 1)", "terrain creation offers a circular/elliptical footprint"),
    ("base_thickness = _add_spin(home, \"Grosor de base Y\"", "terrain creation exposes a configurable solid base thickness"),
    ("max_height = _add_spin(home, \"Rango de altura Y\"", "terrain creation exposes a vertical sculpting range"),
    ("terrain.set(\"footprint_shape\"", "creation applies the selected footprint shape"),
    ("terrain.set(\"base_thickness\"", "creation applies the selected volume thickness"),
    ("terrain.set(\"max_height\"", "creation applies the selected vertical range"),
    ("_add_wall(st", "terrain mesh creates perimeter walls for a solid volume"),
    ("_add_bottom_vertex", "terrain mesh includes an underside"),
    ("add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, panel)", "terrain tools share the native right dock"),
    ("remove_control_from_docks(panel)\n\tadd_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, panel)", "toolbar reopening re-registers a closed terrain dock"),
    ("var local: Vector3 = terrain.to_local(world_position)", "brush local coordinates have an explicit Vector3 type"),
    ("var center: Vector3 = terrain.global_position", "terrain focus center has an explicit Vector3 type"),
    ("panel.custom_minimum_size = Vector2(0, 0)", "terrain dock does not force a wider custom column"),
    ("func _refresh_ui_scale() -> void:", "terrain controls refresh their touch sizing when editor scale changes"),
    ("editor_settings.settings_changed.connect(_refresh_ui_scale)", "terrain listens for editor scale setting changes"),
    ("joystick_pad.gui_input.connect", "touch joystick input is wired"),
    ("_forward_3d_gui_input", "3D viewport mouse/touch input is handled"),
    ("if panel == null or not panel.visible or terrain_tabs == null or terrain_tabs.current_tab not in [1, 2]:", "viewport input is limited to Sculpt/Paint and leaves other tabs to Godot"),
    ("set_input_event_forwarding_always_enabled()", "terrain viewport input remains available without selection-dependent forwarding"),
    ("if (panel == null or not panel.visible) and not stroke_active and not collision_dirty and not joystick_pressed:", "terrain editor avoids idle polling when its dock is closed"),
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
    ('_make_tab_page(terrain_tabs, "Inicio")', "dedicated interface has an overview tab"),
    ('_make_tab_page(terrain_tabs, "Esculpir")', "dedicated interface has a sculpting tab"),
    ('_make_tab_page(terrain_tabs, "Pintar")', "dedicated interface has a painting tab"),
    ('_make_tab_page(terrain_tabs, "Vegetación")', "dedicated interface has a foliage tab"),
    ('_make_tab_page(terrain_tabs, "Heightmaps")', "dedicated interface has a heightmap tab"),
    ("create_button.text = \"Crear terreno\"", "terrain is created only by explicit user action"),
    ("while root.has_node(NodePath(\"Terrain3D_%d\" % suffix)):", "terrain creation avoids node-name collisions"),
    ("terrain.heights.size() != terrain.grid_width * terrain.grid_depth", "heightmap export rejects incomplete terrain data"),
    ("layer_picker.selected < 0 or layer_picker.selected > 3", "texture assignment validates selected layer"),
    ("Terreno creado con la forma, dimensiones X/Z, rango Y, base y colisiones configuradas", "terrain creation reports its configured shape, dimensions, height and collision"),
    ("var min_x := clampi(", "brush work is limited to the affected vertex region"),
    ("_set_heights_deferred", "height edits defer collision rebuilds until the stroke ends"),
    ("collision_dirty and not stroke_active and not joystick_pressed", "collision rebuild is coalesced after touch/mouse strokes"),
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
require("_create_terrain()" not in toggle_body, "opening Terreno 3D leaves the ordinary 3D scene empty")
require('create_button.text = "Crear terreno"' in plugin, "terrain insertion requires the explicit Create terrain button")

for token, label in [
    ("@export_enum(\"Cuadrada / rectangular\", \"Circular / elíptica\") var footprint_shape", "terrain data persists its footprint shape"),
    ("@export_range(0.1, 100.0, 0.1) var base_thickness", "terrain data persists its solid base thickness"),
    ("@export_range(1.0, 1000.0, 1.0) var max_height", "terrain data persists its vertical sculpt range"),
    ("SurfaceTool", "procedural terrain mesh"),
    ("st.index()", "indexed terrain mesh avoids tripled vertex storage on mobile"),
    ("is_finite(height)", "reject non-finite/corrupt height values before mesh generation"),
    ("mesh == null", "mesh generation failure is handled safely"),
    ("collision.shape == null", "collision generation failure is handled safely"),
    ("create_trimesh_shape", "terrain collision generation"),
    ("set_heights", "editable height data"),
    ("set_vertex_colors", "editable vertex color data"),
    ("set_layer_weights", "editable four-channel material weights"),
    ("NoiseTexture2D", "procedural texture generation for material layers"),
    ("@export_storage var heights", "terrain heights persist in saved scenes"),
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
require("Ajustar al ancho y fondo completos" in plugin, "full-width/full-depth image fitting is enabled by default")
require("set_full_surface_texture" in data, "full-surface image assignment can be undone and restored")
require("uniform sampler2D full_surface_texture" in data, "terrain shader supports a dedicated full-surface image")
require("use_full_surface_texture" in data, "terrain shader can switch between image and material layers")
require("stretch_full_surface_texture" in data, "terrain shader supports stretched or repeated image mapping")

require('var terrain_tabs: TabContainer' in plugin, 'terrain editor uses a native tab container')
require('paint_mode_picker = OptionButton.new()' in plugin, 'paint modes live in the Paint tab')
require('terrain_tabs.current_tab not in [1, 2]' in plugin, 'brush editing is restricted to Sculpt/Paint tabs')
require('mode_picker.add_item("Pintar color")' not in plugin, 'sculpt selector does not contain paint modes')
require('var terrain_tabs: TabContainer' in plugin, 'terrain tools use a native tab container')
require('paint_mode_picker = OptionButton.new()' in plugin, 'paint modes live in the Paint tab')
require('terrain_tabs.current_tab not in [1, 2]' in plugin, 'brush editing is restricted to Sculpt/Paint tabs')
