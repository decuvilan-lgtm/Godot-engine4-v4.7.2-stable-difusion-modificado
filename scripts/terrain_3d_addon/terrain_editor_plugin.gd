@tool
extends EditorPlugin

const TERRAIN_SCRIPT := "res://addons/terrain_3d/terrain_data.gd"
const TERRAIN_META := "github_terrain_3d"

var terrain_button: Button
var panel: VBoxContainer
var terrain_width: SpinBox
var terrain_depth: SpinBox
var cell_size: SpinBox
var resolution_preview_label: Label
var terrain_preview: MeshInstance3D
var terrain_preview_material: StandardMaterial3D
var mode_picker: OptionButton
var brush_radius: HSlider
var brush_strength: HSlider
var flatten_height: SpinBox
var height_scale: SpinBox
var paint_color: ColorPickerButton
var layer_picker: OptionButton
var grid_snap: CheckButton
var foliage_count: SpinBox
var continuous_stroke: CheckButton
var joystick_pad: Control
var joystick_vector := Vector2.ZERO
var joystick_pressed := false
var stroke_active := false
var cursor_update_timer := 0.0
var last_viewport_brush_msec := 0
var collision_dirty := false
var collision_dirty_terrain: Node
var cached_terrain: Node
var cached_scene_root: Node
var cursor_hit := Vector3.ZERO
var cursor_valid := false
var cursor_mesh: MeshInstance3D
var cursor_material: StandardMaterial3D
var stroke_timer := 0.0
var import_dialog: FileDialog
var export_dialog: FileDialog
var texture_dialog: FileDialog
var status_label: Label

func _enter_tree() -> void:
	terrain_button = Button.new()
	terrain_button.text = "Terreno 3D"
	terrain_button.custom_minimum_size = Vector2(0, 0)
	terrain_button.tooltip_text = "Abrir las herramientas de terreno 3D"
	terrain_button.pressed.connect(_toggle_panel)
	add_control_to_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, terrain_button)
	_build_panel()
	var editor_settings := EditorInterface.get_editor_settings()
	if editor_settings and not editor_settings.settings_changed.is_connected(_refresh_ui_scale):
		editor_settings.settings_changed.connect(_refresh_ui_scale)
	_refresh_ui_scale()
	# Terrain brush input must remain available even when the terrain node is not selected.
	set_input_event_forwarding_always_enabled()
	set_process(true)

func handles(object: Object) -> bool:
	return object is Node and object.has_meta(TERRAIN_META)

func _exit_tree() -> void:
	if terrain_button:
		remove_control_from_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, terrain_button)
		terrain_button.queue_free()
	if panel:
		remove_control_from_docks(panel)
		panel.queue_free()
	if cursor_mesh and is_instance_valid(cursor_mesh):
		cursor_mesh.queue_free()
	if import_dialog:
		import_dialog.queue_free()
	if export_dialog:
		export_dialog.queue_free()
	if texture_dialog:
		texture_dialog.queue_free()
	if terrain_preview and is_instance_valid(terrain_preview):
		terrain_preview.queue_free()

func _build_panel() -> void:
	panel = VBoxContainer.new()
	panel.name = "Terrain3DEditorPanel"
	panel.custom_minimum_size = Vector2(0, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_constant_override("separation", roundi(8.0 * EditorInterface.get_editor_scale()))
	panel.hide()
	# Behave like a native Godot inspector dock: share the right dock area and
	# never reserve a custom-width column or resize the whole editor UI.
	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, panel)
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_child(tabs)
	var home := _make_tab_page(tabs, "Inicio")
	var sculpt := _make_tab_page(tabs, "Esculpir")
	var paint := _make_tab_page(tabs, "Pintar")
	var foliage := _make_tab_page(tabs, "Vegetación")
	var maps := _make_tab_page(tabs, "Heightmaps")

	var title := Label.new()
	title.text = "EDITOR DE TERRENO 3D"
	home.add_child(title)
	var intro := Label.new()
	intro.text = "Al abrir esta pestaña se crea una base cuadrada editable en la escena. Las herramientas están separadas para mantener una interfaz cómoda en móvil."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	home.add_child(intro)
	_add_section(home, "Dimensiones")
	terrain_width = _add_spin(home, "Resolución X", 65, 9, 257, 8)
	terrain_depth = _add_spin(home, "Resolución Z", 65, 9, 257, 8)
	cell_size = _add_spin(home, "Tamaño de celda", 1.0, 0.1, 16.0, 0.1)
	resolution_preview_label = Label.new()
	resolution_preview_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	home.add_child(resolution_preview_label)
	terrain_width.value_changed.connect(_update_terrain_preview)
	terrain_depth.value_changed.connect(_update_terrain_preview)
	cell_size.value_changed.connect(_update_terrain_preview)
	var create_button := Button.new()
	create_button.text = "Crear otro terreno"
	create_button.pressed.connect(_create_terrain)
	home.add_child(create_button)
	var focus_button := Button.new()
	focus_button.text = "Enfocar terreno en la vista 3D"
	focus_button.pressed.connect(_focus_terrain)
	home.add_child(focus_button)
	var collision_button := Button.new()
	collision_button.text = "Regenerar colisiones"
	collision_button.pressed.connect(_regenerate_collision)
	home.add_child(collision_button)
	var undo_row := HBoxContainer.new()
	var undo_button := Button.new()
	undo_button.text = "Deshacer"
	undo_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	undo_button.pressed.connect(func(): EditorInterface.get_editor_undo_redo().undo())
	undo_row.add_child(undo_button)
	var redo_button := Button.new()
	redo_button.text = "Rehacer"
	redo_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	redo_button.pressed.connect(func(): EditorInterface.get_editor_undo_redo().redo())
	undo_row.add_child(redo_button)
	home.add_child(undo_row)

	_add_section(sculpt, "Pincel de escultura")
	mode_picker = OptionButton.new()
	for mode in ["Elevar", "Bajar", "Suavizar", "Aplanar"]:
		mode_picker.add_item(mode)
	sculpt.add_child(mode_picker)
	brush_radius = _add_slider(sculpt, "Radio del pincel", 4.0, 0.5, 24.0, 0.5)
	brush_strength = _add_slider(sculpt, "Intensidad", 0.35, 0.01, 1.0, 0.01)
	flatten_height = _add_spin(sculpt, "Altura objetivo", 0.0, -100.0, 100.0, 0.25)
	grid_snap = CheckButton.new()
	grid_snap.text = "Ajustar pincel a cuadrícula"
	sculpt.add_child(grid_snap)
	_add_section(sculpt, "Control táctil")
	var joystick_row := HBoxContainer.new()
	joystick_pad = Panel.new()
	joystick_pad.custom_minimum_size = Vector2(112, 112) * EditorInterface.get_editor_scale()
	joystick_pad.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	joystick_pad.gui_input.connect(_on_joystick_input)
	joystick_row.add_child(joystick_pad)
	var joystick_help := Label.new()
	joystick_help.text = "Mantén y arrastra para mover el cursor por el terreno."
	joystick_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	joystick_help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	joystick_row.add_child(joystick_help)
	sculpt.add_child(joystick_row)
	var recenter := Button.new()
	recenter.text = "Centrar cursor"
	recenter.pressed.connect(func(): joystick_vector = Vector2.ZERO)
	sculpt.add_child(recenter)
	continuous_stroke = CheckButton.new()
	continuous_stroke.text = "Trazo continuo con el joystick"
	sculpt.add_child(continuous_stroke)
	var apply_button := Button.new()
	apply_button.text = "Aplicar pincel en cursor"
	apply_button.pressed.connect(_apply_at_cursor)
	sculpt.add_child(apply_button)

	_add_section(paint, "Pintura de terreno")
	mode_picker.add_item("Pintar color")
	mode_picker.add_item("Pintar capa de material")
	paint_color = ColorPickerButton.new()
	paint_color.color = Color(0.24, 0.48, 0.20)
	paint_color.text = "Color del terreno"
	paint.add_child(paint_color)
	layer_picker = OptionButton.new()
	for layer_name in ["Hierba", "Roca", "Arena", "Nieve"]:
		layer_picker.add_item(layer_name)
	paint.add_child(layer_picker)
	var texture_button := Button.new()
	texture_button.text = "Cargar textura para la capa elegida"
	texture_button.pressed.connect(_open_layer_texture)
	paint.add_child(texture_button)
	var paint_help := Label.new()
	paint_help.text = "Selecciona un modo de pintura en la lista del pincel de Esculpir; el color y la capa se configuran aquí."
	paint_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	paint.add_child(paint_help)

	_add_section(foliage, "Distribución de vegetación")
	foliage_count = _add_spin(foliage, "Cantidad de árboles", 180, 1, 5000, 10)
	var foliage_button := Button.new()
	foliage_button.text = "Distribuir árboles"
	foliage_button.pressed.connect(_scatter_foliage)
	foliage.add_child(foliage_button)
	var foliage_help := Label.new()
	foliage_help.text = "La vegetación se genera usando instancias múltiples para reducir el coste de renderizado en móvil."
	foliage_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	foliage.add_child(foliage_help)

	_add_section(maps, "Mapas de altura")
	height_scale = _add_spin(maps, "Escala de altura", 20.0, 0.1, 250.0, 1.0)
	var heightmap_row := HBoxContainer.new()
	var import_button := Button.new()
	import_button.text = "Importar heightmap"
	import_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	import_button.pressed.connect(_open_import_heightmap)
	heightmap_row.add_child(import_button)
	var export_button := Button.new()
	export_button.text = "Exportar heightmap"
	export_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	export_button.pressed.connect(_open_export_heightmap)
	heightmap_row.add_child(export_button)
	maps.add_child(heightmap_row)
	var map_help := Label.new()
	map_help.text = "Importa una imagen en escala de grises para definir alturas o exporta el relieve actual a PNG."
	map_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	maps.add_child(map_help)

	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_label.text = "Abre una escena 3D para comenzar."
	panel.add_child(status_label)
	# Keep the dock closed at startup; the toolbar button always reopens it.
	panel.hide()
	_create_cursor()
	_create_terrain_preview()

	import_dialog = FileDialog.new()
	import_dialog.title = "Importar mapa de altura"
	import_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	import_dialog.access = FileDialog.ACCESS_FILESYSTEM
	import_dialog.add_filter("*.png,*.jpg,*.jpeg,*.webp", "Imagen de altura")
	import_dialog.file_selected.connect(_import_heightmap)
	add_child(import_dialog)

	export_dialog = FileDialog.new()
	export_dialog.title = "Exportar mapa de altura"
	export_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	export_dialog.access = FileDialog.ACCESS_FILESYSTEM
	export_dialog.add_filter("*.png", "PNG heightmap")
	export_dialog.file_selected.connect(_export_heightmap)
	add_child(export_dialog)

	texture_dialog = FileDialog.new()
	texture_dialog.title = "Asignar textura a la capa elegida"
	texture_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	texture_dialog.access = FileDialog.ACCESS_FILESYSTEM
	texture_dialog.add_filter("*.png,*.jpg,*.jpeg,*.webp", "Textura de terreno")
	texture_dialog.file_selected.connect(_import_layer_texture)
	add_child(texture_dialog)

func _refresh_ui_scale() -> void:
	# Custom touch targets follow Godot's current editor scale when the theme changes.
	var scale := EditorInterface.get_editor_scale()
	if panel:
		panel.add_theme_constant_override("separation", roundi(8.0 * scale))
	if joystick_pad:
		joystick_pad.custom_minimum_size = Vector2(112, 112) * scale
	if panel:
		for control in panel.find_children("*", "SpinBox", true, false):
			var spin := control as SpinBox
			if spin:
				spin.custom_minimum_size = Vector2(112, 44) * scale

func _make_tab_page(tabs: TabContainer, title: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = title
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tabs.add_child(scroll)
	var content := VBoxContainer.new()
	content.custom_minimum_size = Vector2(250, 0)
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 12)
	scroll.add_child(content)
	return content

func _add_section(parent: Control, text: String) -> void:
	var label := Label.new()
	label.text = text
	parent.add_child(label)
	var separator := HSeparator.new()
	parent.add_child(separator)

func _add_spin(parent: Control, label_text: String, value: float, minimum: float, maximum: float, step: float) -> SpinBox:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = label_text
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.step = step
	spin.value = value
	spin.custom_minimum_size = Vector2(112, 44) * EditorInterface.get_editor_scale()
	row.add_child(spin)
	parent.add_child(row)
	return spin

func _add_slider(parent: Control, label_text: String, value: float, minimum: float, maximum: float, step: float) -> HSlider:
	var column := VBoxContainer.new()
	var label := Label.new()
	label.text = "%s: %.2f" % [label_text, value]
	column.add_child(label)
	var slider := HSlider.new()
	slider.min_value = minimum
	slider.max_value = maximum
	slider.step = step
	slider.value = value
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.value_changed.connect(func(v: float): label.text = "%s: %.2f" % [label_text, v])
	column.add_child(slider)
	parent.add_child(column)
	return slider

func _toggle_panel() -> void:
	if panel == null or not is_instance_valid(panel):
		_build_panel()
	if panel.visible:
		panel.hide()
		return

	# Re-register the dock on every reopen. Godot can detach/close an EditorPlugin
	# dock independently of the child Control's lifetime; show() alone may leave
	# the toolbar button pointing at a hidden, detached panel.
	remove_control_from_docks(panel)
	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, panel)
	panel.show()
	_update_terrain_preview()
	# Open the tools in their dock first. Create a starter base only when there
	# is an editable scene; never interrupt other editor actions if none is open.
	if _get_terrain() == null:
		_create_terrain()
	else:
		_focus_terrain()

func _create_terrain() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null:
		_set_status("Primero crea o abre una escena.")
		return
	if terrain_width == null or terrain_depth == null or cell_size == null:
		_set_status("El panel de terreno todavía no está inicializado.")
		return
	var terrain_script = load(TERRAIN_SCRIPT)
	if terrain_script == null:
		_set_status("No se encontró terrain_data.gd.")
		return
	var terrain = terrain_script.new()
	# Never rely on child count for names: deleted nodes leave gaps and imported
	# scenes may already contain Terrain3D_1, Terrain3D_2, etc.
	var suffix := 1
	while root.has_node(NodePath("Terrain3D_%d" % suffix)):
		suffix += 1
	terrain.name = "Terrain3D_%d" % suffix
	terrain.set_meta(TERRAIN_META, true)
	cached_terrain = terrain
	cached_scene_root = root
	var undo_redo := EditorInterface.get_editor_undo_redo()
	undo_redo.create_action("Crear terreno 3D")
	undo_redo.add_do_method(root, "add_child", terrain)
	undo_redo.add_do_method(terrain, "set_owner", root)
	undo_redo.add_do_method(terrain, "initialize_grid", int(terrain_width.value), int(terrain_depth.value), cell_size.value)
	undo_redo.add_undo_method(root, "remove_child", terrain)
	undo_redo.add_do_reference(terrain)
	undo_redo.commit_action()
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(terrain)
	_set_status("Base cuadrada creada con malla, material y colisiones. Edita desde las pestañas del editor de terreno.")
	_focus_terrain()

func _get_terrain():
	var root := EditorInterface.get_edited_scene_root()
	if root != cached_scene_root:
		cached_scene_root = root
		cached_terrain = null
	if cached_terrain and is_instance_valid(cached_terrain) and cached_terrain.is_inside_tree() and cached_terrain.has_meta(TERRAIN_META):
		return cached_terrain
	var selection := EditorInterface.get_selection().get_selected_nodes()
	for node in selection:
		if is_instance_valid(node) and node.has_meta(TERRAIN_META):
			cached_terrain = node
			return cached_terrain
	cached_terrain = _find_terrain(root)
	return cached_terrain

func _find_terrain(node: Node):
	if node == null:
		return null
	if node.has_meta(TERRAIN_META):
		return node
	for child in node.get_children():
		var found = _find_terrain(child)
		if found:
			return found
	return null

func _create_terrain_preview() -> void:
	terrain_preview = MeshInstance3D.new()
	terrain_preview.name = "TerrainCreationPreview"
	terrain_preview.top_level = true
	terrain_preview.visible = false
	terrain_preview_material = StandardMaterial3D.new()
	terrain_preview_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	terrain_preview_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	terrain_preview_material.albedo_color = Color(0.15, 0.8, 1.0, 0.22)
	terrain_preview_material.no_depth_test = true
	terrain_preview.material_override = terrain_preview_material
	_update_terrain_preview()

func _update_terrain_preview(_value: float = 0.0) -> void:
	if resolution_preview_label:
		var width := int(terrain_width.value) if terrain_width else 65
		var depth := int(terrain_depth.value) if terrain_depth else 65
		var cell := cell_size.value if cell_size else 1.0
		resolution_preview_label.text = "%d × %d vértices · %.1f × %.1f unidades" % [width, depth, (width - 1) * cell, (depth - 1) * cell]
	if terrain_preview == null or not is_instance_valid(terrain_preview) or terrain_width == null:
		return
	var plane := PlaneMesh.new()
	plane.size = Vector2((terrain_width.value - 1.0) * cell_size.value, (terrain_depth.value - 1.0) * cell_size.value)
	plane.subdivide_width = int(terrain_width.value) - 2
	plane.subdivide_depth = int(terrain_depth.value) - 2
	terrain_preview.mesh = plane

func _create_cursor() -> void:
	cursor_mesh = MeshInstance3D.new()
	cursor_mesh.name = "TerrainBrushPreview"
	cursor_mesh.top_level = true
	cursor_mesh.visible = false
	var scene := EditorInterface.get_edited_scene_root()
	if scene:
		scene.add_child(cursor_mesh)
	cursor_material = StandardMaterial3D.new()
	cursor_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	cursor_material.albedo_color = Color(0.18, 0.9, 1.0, 1.0)
	cursor_material.no_depth_test = true

func _update_cursor_mesh(position: Vector3) -> void:
	var scene := EditorInterface.get_edited_scene_root()
	if cursor_mesh == null or not is_instance_valid(cursor_mesh):
		_create_cursor()
	if scene and cursor_mesh.get_parent() != scene:
		if cursor_mesh.get_parent():
			cursor_mesh.get_parent().remove_child(cursor_mesh)
		scene.add_child(cursor_mesh)
	var immediate := ImmediateMesh.new()
	immediate.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, cursor_material)
	var radius := brush_radius.value
	for i in range(49):
		var angle := TAU * float(i) / 48.0
		immediate.surface_add_vertex(Vector3(cos(angle) * radius, 0.04, sin(angle) * radius))
	immediate.surface_end()
	cursor_mesh.mesh = immediate
	cursor_mesh.global_position = position
	cursor_mesh.visible = true

func _raycast_terrain(camera: Camera3D, screen_position: Vector2) -> Dictionary:
	var terrain = _get_terrain()
	if terrain == null or camera == null:
		return {}
	var viewport := EditorInterface.get_editor_viewport_3d(0)
	if viewport == null or viewport.world_3d == null:
		return {}
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	var query := PhysicsRayQueryParameters3D.create(origin, origin + direction * 2000.0)
	query.collide_with_areas = false
	var result := viewport.world_3d.direct_space_state.intersect_ray(query)
	if result.is_empty():
		return {}
	var collider = result.get("collider")
	var terrain_collision = terrain.get("collision_body")
	if collider != terrain_collision:
		return {}
	return result

func _on_joystick_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		joystick_pressed = event.pressed
		if event.pressed:
			_update_joystick_vector(event.position)
		else:
			joystick_vector = Vector2.ZERO
		joystick_pad.accept_event()
	elif event is InputEventScreenDrag and joystick_pressed:
		_update_joystick_vector(event.position)
		joystick_pad.accept_event()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		joystick_pressed = event.pressed
		if event.pressed:
			_update_joystick_vector(event.position)
		else:
			joystick_vector = Vector2.ZERO
		joystick_pad.accept_event()
	elif event is InputEventMouseMotion and joystick_pressed:
		_update_joystick_vector(event.position)
		joystick_pad.accept_event()

func _update_joystick_vector(position: Vector2) -> void:
	var center := joystick_pad.size * 0.5
	var extent := maxf(1.0, minf(center.x, center.y) - 8.0)
	joystick_vector = ((position - center) / extent).limit_length(1.0)

func _process(delta: float) -> void:
	# Do no polling/redraw work while the terrain tools are closed and no edit
	# stroke/collision rebuild is pending. This avoids stealing input or CPU from
	# the rest of the mobile editor.
	if (panel == null or not panel.visible) and not stroke_active and not collision_dirty and not joystick_pressed:
		return
	cursor_update_timer += delta
	stroke_timer += delta
	# Cap terrain raycasts to 20 Hz on mobile; the cursor remains responsive without
	# querying physics at the display refresh rate while the editor is otherwise idle.
	if cursor_update_timer < 0.05:
		return
	cursor_update_timer = 0.0
	if cursor_mesh == null or not is_instance_valid(cursor_mesh):
		_create_cursor()
	if terrain_preview == null or not is_instance_valid(terrain_preview):
		_create_terrain_preview()
	# Rebuild the expensive trimesh collider once after an edit stroke, not on every dab.
	if collision_dirty and not stroke_active and not joystick_pressed:
		if collision_dirty_terrain and is_instance_valid(collision_dirty_terrain):
			collision_dirty_terrain.rebuild_collision()
		collision_dirty = false
		collision_dirty_terrain = null
	var root := EditorInterface.get_edited_scene_root()
	if terrain_preview and is_instance_valid(terrain_preview):
		if root and terrain_preview.get_parent() != root:
			if terrain_preview.get_parent():
				terrain_preview.get_parent().remove_child(terrain_preview)
			root.add_child(terrain_preview)
		terrain_preview.visible = panel.visible and root != null and _get_terrain() == null
		if terrain_preview.visible:
			terrain_preview.global_position = Vector3(0.0, 0.05, 0.0)
	var terrain = _get_terrain()
	if terrain == null:
		if cursor_mesh:
			cursor_mesh.visible = false
		return
	var viewport := EditorInterface.get_editor_viewport_3d(0)
	if viewport == null:
		return
	var camera := viewport.get_camera_3d()
	if camera == null:
		return
	var screen_position := viewport.size * 0.5
	screen_position += joystick_vector * minf(viewport.size.x, viewport.size.y) * 0.42
	var hit := _raycast_terrain(camera, screen_position)
	cursor_valid = not hit.is_empty()
	if cursor_valid:
		cursor_hit = hit.position
		_update_cursor_mesh(cursor_hit)
	else:
		cursor_mesh.visible = false
	if continuous_stroke.button_pressed and joystick_pressed and cursor_valid and stroke_timer >= 0.12:
		stroke_timer = 0.0
		_apply_brush(terrain, cursor_hit)

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	# Never intercept normal Godot viewport input while this dock is hidden.
	if panel == null or not panel.visible:
		return AFTER_GUI_INPUT_PASS
	var terrain = _get_terrain()
	if terrain == null:
		return AFTER_GUI_INPUT_PASS
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		stroke_active = event.pressed
		if event.pressed:
			var hit := _raycast_terrain(camera, event.position)
			if not hit.is_empty():
				cursor_hit = hit.position
				cursor_valid = true
				_update_cursor_mesh(cursor_hit)
				_apply_brush(terrain, cursor_hit)
				return AFTER_GUI_INPUT_STOP
	elif event is InputEventMouseMotion and stroke_active and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		var now := Time.get_ticks_msec()
		if now - last_viewport_brush_msec < 120:
			return AFTER_GUI_INPUT_STOP
		last_viewport_brush_msec = now
		var hit := _raycast_terrain(camera, event.position)
		if not hit.is_empty():
			cursor_hit = hit.position
			cursor_valid = true
			_update_cursor_mesh(cursor_hit)
			_apply_brush(terrain, cursor_hit)
			return AFTER_GUI_INPUT_STOP
	elif event is InputEventScreenTouch:
		stroke_active = event.pressed
		if event.pressed:
			var hit := _raycast_terrain(camera, event.position)
			if not hit.is_empty():
				cursor_hit = hit.position
				cursor_valid = true
				_update_cursor_mesh(cursor_hit)
				_apply_brush(terrain, cursor_hit)
				return AFTER_GUI_INPUT_STOP
	elif event is InputEventScreenDrag and stroke_active:
		var now := Time.get_ticks_msec()
		if now - last_viewport_brush_msec < 120:
			return AFTER_GUI_INPUT_STOP
		last_viewport_brush_msec = now
		var hit := _raycast_terrain(camera, event.position)
		if not hit.is_empty():
			cursor_hit = hit.position
			cursor_valid = true
			_update_cursor_mesh(cursor_hit)
			_apply_brush(terrain, cursor_hit)
			return AFTER_GUI_INPUT_STOP
	return AFTER_GUI_INPUT_PASS

func _apply_at_cursor() -> void:
	var terrain = _get_terrain()
	if terrain and cursor_valid:
		_apply_brush(terrain, cursor_hit)
	else:
		_set_status("No hay un punto válido del terreno bajo el cursor.")

func _apply_brush(terrain, world_position: Vector3) -> void:
	var local: Vector3 = terrain.to_local(world_position)
	if grid_snap.button_pressed:
		local.x = roundf(local.x / terrain.cell_size) * terrain.cell_size
		local.z = roundf(local.z / terrain.cell_size) * terrain.cell_size
	var radius: float = brush_radius.value
	var strength: float = brush_strength.value
	var mode: int = mode_picker.get_selected_id()
	var half_x := float(terrain.grid_width - 1) * 0.5
	var half_z := float(terrain.grid_depth - 1) * 0.5
	var min_x := clampi(floori((local.x - radius) / terrain.cell_size + half_x), 0, terrain.grid_width - 1)
	var max_x := clampi(ceili((local.x + radius) / terrain.cell_size + half_x), 0, terrain.grid_width - 1)
	var min_z := clampi(floori((local.z - radius) / terrain.cell_size + half_z), 0, terrain.grid_depth - 1)
	var max_z := clampi(ceili((local.z + radius) / terrain.cell_size + half_z), 0, terrain.grid_depth - 1)
	if min_x > max_x or min_z > max_z:
		return

	if mode == 4:
		var old_colors: PackedColorArray = terrain.vertex_colors.duplicate()
		var new_colors: PackedColorArray = old_colors.duplicate()
		for z in range(min_z, max_z + 1):
			for x in range(min_x, max_x + 1):
				var index: int = terrain.get_height_index(x, z)
				var vertex: Vector3 = terrain.get_vertex_local_position(x, z)
				var distance := Vector2(vertex.x - local.x, vertex.z - local.z).length()
				if distance <= radius:
					var weight := 1.0 - smoothstep(0.0, radius, distance)
					new_colors[index] = new_colors[index].lerp(paint_color.color, strength * weight)
		_commit_terrain_change(terrain, "Pintar color del terreno", "set_vertex_colors", old_colors, new_colors)
		return

	if mode == 5:
		var old_weights: PackedColorArray = terrain.layer_weights.duplicate()
		var new_weights: PackedColorArray = old_weights.duplicate()
		var selected_layer: int = layer_picker.selected
		for z in range(min_z, max_z + 1):
			for x in range(min_x, max_x + 1):
				var index: int = terrain.get_height_index(x, z)
				var vertex: Vector3 = terrain.get_vertex_local_position(x, z)
				var distance := Vector2(vertex.x - local.x, vertex.z - local.z).length()
				if distance > radius:
					continue
				var amount := strength * (1.0 - smoothstep(0.0, radius, distance))
				var weights := [old_weights[index].r, old_weights[index].g, old_weights[index].b, old_weights[index].a]
				for channel in range(4):
					weights[channel] = lerpf(weights[channel], 1.0 if channel == selected_layer else 0.0, amount)
				var total: float = maxf(0.001, weights[0] + weights[1] + weights[2] + weights[3])
				new_weights[index] = Color(weights[0] / total, weights[1] / total, weights[2] / total, weights[3] / total)
		_commit_terrain_change(terrain, "Pintar capa de material", "set_layer_weights", old_weights, new_weights)
		return

	var old_heights: PackedFloat32Array = terrain.heights.duplicate()
	var new_heights: PackedFloat32Array = old_heights.duplicate()
	for z in range(min_z, max_z + 1):
		for x in range(min_x, max_x + 1):
			var index: int = terrain.get_height_index(x, z)
			var vertex: Vector3 = terrain.get_vertex_local_position(x, z)
			var distance := Vector2(vertex.x - local.x, vertex.z - local.z).length()
			if distance > radius:
				continue
			var weight := 1.0 - smoothstep(0.0, radius, distance)
			match mode:
				0:
					new_heights[index] += strength * weight
				1:
					new_heights[index] -= strength * weight
				2:
					var total := 0.0
					var count := 0
					for nz in range(maxi(0, z - 1), mini(terrain.grid_depth, z + 2)):
						for nx in range(maxi(0, x - 1), mini(terrain.grid_width, x + 2)):
							total += old_heights[terrain.get_height_index(nx, nz)]
							count += 1
					new_heights[index] = lerpf(old_heights[index], total / maxf(1.0, count), strength * weight)
				3:
					new_heights[index] = lerpf(old_heights[index], flatten_height.value, strength * weight)
	_commit_terrain_change(terrain, "Esculpir terreno", "set_heights", old_heights, new_heights)

func _commit_terrain_change(terrain, action_name: String, method: StringName, old_value: Variant, new_value: Variant) -> void:
	var undo_redo := EditorInterface.get_editor_undo_redo()
	undo_redo.create_action(action_name)
	if method == "set_heights":
		undo_redo.add_do_method(self, "_set_heights_deferred", terrain, new_value)
		undo_redo.add_undo_method(self, "_set_heights_deferred", terrain, old_value)
	else:
		undo_redo.add_do_method(terrain, method, new_value)
		undo_redo.add_undo_method(terrain, method, old_value)
	undo_redo.commit_action()
	_set_status(action_name + " aplicado. Usa Deshacer/Rehacer para revisar el cambio.")

func _set_heights_deferred(terrain, values: PackedFloat32Array) -> void:
	if terrain == null or not is_instance_valid(terrain):
		return
	terrain.set_heights(values, false)
	collision_dirty = true
	collision_dirty_terrain = terrain

func _focus_terrain() -> void:
	var terrain = _get_terrain()
	var viewport := EditorInterface.get_editor_viewport_3d(0)
	if terrain == null or viewport == null or viewport.get_camera_3d() == null:
		_set_status("Selecciona o crea un terreno para enfocarlo.")
		return
	var camera := viewport.get_camera_3d()
	var center: Vector3 = terrain.global_position
	camera.global_position = center + Vector3(18.0, 18.0, 18.0)
	camera.look_at(center, Vector3.UP)
	_set_status("Vista centrada en el terreno.")

func _regenerate_collision() -> void:
	var terrain = _get_terrain()
	if terrain:
		terrain.rebuild_collision()
		_set_status("Colisiones regeneradas.")

func _scatter_foliage() -> void:
	var terrain = _get_terrain()
	if terrain == null:
		_set_status("Crea o selecciona un terreno antes de distribuir árboles.")
		return
	var old_foliage := terrain.get_node_or_null("TerrainFoliage")
	var seed_value := int(Time.get_unix_time_from_system())
	var new_foliage: Node3D = terrain.create_foliage(int(foliage_count.value), seed_value)
	var undo_redo := EditorInterface.get_editor_undo_redo()
	undo_redo.create_action("Distribuir vegetación")
	if old_foliage:
		undo_redo.add_do_method(terrain, "remove_child", old_foliage)
		undo_redo.add_undo_method(terrain, "add_child", old_foliage)
		undo_redo.add_do_reference(old_foliage)
	undo_redo.add_do_method(terrain, "add_child", new_foliage)
	undo_redo.add_do_method(terrain, "set_foliage_owner", new_foliage)
	undo_redo.add_undo_method(terrain, "remove_child", new_foliage)
	undo_redo.add_do_reference(new_foliage)
	undo_redo.commit_action()
	_set_status("Vegetación distribuida. Deshacer/Rehacer también restaura la distribución.");

func _open_import_heightmap() -> void:
	import_dialog.popup_centered(Vector2i(640, 480))

func _import_heightmap(path: String) -> void:
	var terrain = _get_terrain()
	if terrain == null:
		_set_status("Crea o selecciona un terreno antes de importar un heightmap.")
		return
	var image := Image.new()
	var err := image.load(path)
	if err != OK:
		_set_status("No se pudo abrir la imagen de altura (error %d)." % err)
		return
	var old_heights: PackedFloat32Array = terrain.heights.duplicate()
	var image_copy := image.duplicate()
	image_copy.resize(terrain.grid_width, terrain.grid_depth, Image.INTERPOLATE_BILINEAR)
	var new_heights := PackedFloat32Array()
	new_heights.resize(terrain.grid_width * terrain.grid_depth)
	for z in range(terrain.grid_depth):
		for x in range(terrain.grid_width):
			new_heights[terrain.get_height_index(x, z)] = image_copy.get_pixel(x, z).get_luminance() * height_scale.value
	_commit_terrain_change(terrain, "Importar heightmap", "set_heights", old_heights, new_heights)

func _open_export_heightmap() -> void:
	export_dialog.current_file = "terrain_heightmap.png"
	export_dialog.popup_centered(Vector2i(640, 480))

func _export_heightmap(path: String) -> void:
	var terrain = _get_terrain()
	if terrain == null:
		_set_status("No hay terreno para exportar.")
		return
	if terrain.heights.size() != terrain.grid_width * terrain.grid_depth:
		_set_status("El terreno tiene datos de altura incompletos; no se exportó.")
		return
	var image := Image.create(terrain.grid_width, terrain.grid_depth, false, Image.FORMAT_L8)
	var minimum := INF
	var maximum := -INF
	for height in terrain.heights:
		minimum = minf(minimum, height)
		maximum = maxf(maximum, height)
	var span := maxf(0.001, maximum - minimum)
	for z in range(terrain.grid_depth):
		for x in range(terrain.grid_width):
			var value: float = clampf((terrain.heights[terrain.get_height_index(x, z)] - minimum) / span, 0.0, 1.0)
			image.set_pixel(x, z, Color(value, value, value, 1.0))
	var output_path := path if path.to_lower().ends_with(".png") else path + ".png"
	var err := image.save_png(output_path)
	if err == OK:
		_set_status("Heightmap exportado: " + output_path)
	else:
		_set_status("No se pudo guardar el heightmap (error %d)." % err)

func _open_layer_texture() -> void:
	texture_dialog.popup_centered(Vector2i(640, 480))

func _import_layer_texture(path: String) -> void:
	var terrain = _get_terrain()
	if terrain == null:
		_set_status("Crea o selecciona un terreno antes de asignar texturas.")
		return
	if layer_picker == null or layer_picker.selected < 0 or layer_picker.selected > 3:
		_set_status("Selecciona una capa válida: hierba, roca, arena o nieve.")
		return
	var image := Image.new()
	var err := image.load(path)
	if err != OK:
		_set_status("No se pudo abrir la textura (error %d)." % err)
		return
	# Cap imported texture dimensions to keep memory use manageable on the LG K51.
	if image.get_width() > 512 or image.get_height() > 512:
		image.resize(512, 512, Image.INTERPOLATE_BILINEAR)
	if image.is_empty():
		_set_status("La imagen no contiene píxeles utilizables.")
		return
	var texture := ImageTexture.create_from_image(image)
	if texture == null:
		_set_status("No se pudo convertir la imagen en textura.")
		return
	var selected_layer := layer_picker.selected
	var previous: Texture2D = terrain.get_layer_texture(selected_layer)
	var undo_redo := EditorInterface.get_editor_undo_redo()
	undo_redo.create_action("Asignar textura de terreno")
	undo_redo.add_do_method(terrain, "set_layer_texture", selected_layer, texture)
	undo_redo.add_undo_method(terrain, "set_layer_texture", selected_layer, previous)
	undo_redo.add_do_reference(texture)
	undo_redo.commit_action()
	_set_status("Textura asignada a la capa seleccionada. Guarda la escena para conservarla.")

func _set_status(message: String) -> void:
	if status_label:
		status_label.text = message
