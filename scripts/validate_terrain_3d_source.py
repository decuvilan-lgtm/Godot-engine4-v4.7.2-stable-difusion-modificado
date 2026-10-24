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
    ("PlaneMesh", "preview mesh follows the chosen terrain dimensions"),
    ('add_control_to_bottom_panel(panel, "Terreno 3D")', "dedicated terrain editor panel"),
    ("joystick_pad.gui_input.connect", "touch joystick input is wired"),
    ("_forward_3d_gui_input", "3D viewport mouse/touch input is handled"),
    ("_raycast_terrain", "cursor uses a 3D raycast"),
    ("Elevar", "raise brush"),
    ("Bajar", "lower brush"),
    ("Suavizar", "smooth brush"),
    ("Aplanar", "flatten brush"),
    ("Pintar color", "vertex-color painting"),
    ("Pintar capa de material", "four paintable terrain material layers"),
    ('for mode in ["Elevar", "Bajar", "Suavizar", "Aplanar"]:', "sculpt tool selector has valid loop syntax"),
    ('mode_picker.add_item("Pintar color")', "color painting is available in the tool selector"),
    ('mode_picker.add_item("Pintar capa de material")', "material-layer painting is available in the tool selector"),
    ("func _make_tab_page", "terrain editor options are separated into scrollable tabs"),
    ('_make_tab_page(tabs, "Inicio")', "dedicated interface has an overview tab"),
    ('_make_tab_page(tabs, "Esculpir")', "dedicated interface has a sculpting tab"),
    ('_make_tab_page(tabs, "Pintar")', "dedicated interface has a painting tab"),
    ('_make_tab_page(tabs, "Vegetación")', "dedicated interface has a foliage tab"),
    ('_make_tab_page(tabs, "Heightmaps")', "dedicated interface has a heightmap tab"),
    ("_create_terrain()", "opening the terrain editor can create a starter terrain"),
    ("Base cuadrada creada con malla, material y colisiones", "starter terrain has generated mesh, material and collision"),
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
for token, label in [
    ("SurfaceTool", "procedural terrain mesh"),
    ("create_trimesh_shape", "terrain collision generation"),
    ("set_heights", "editable height data"),
    ("set_vertex_colors", "editable vertex color data"),
    ("set_layer_weights", "editable four-channel material weights"),
    ("NoiseTexture2D", "procedural texture generation for material layers"),
    ("@export_storage var heights", "terrain heights persist in saved scenes"),
    ("create_foliage", "procedural foliage placement"),
]:
    require(token in data, label)
require("TERRAIN_DATA_GD" in patcher and "res://addons/terrain_3d/plugin.cfg" in patcher,
        "ZIP-installed projects receive and enable the terrain addon")
print("Static source checks only; GDScript parsing, Android resource compilation and viewport runtime are still required.")
