@tool
extends EditorPlugin

const TERRAIN_SCRIPT := "res://addons/terrain_3d/terrain_data.gd"
const TERRAIN_META := "github_terrain_3d"

var terrain_button: Button
var panel: VBoxContainer
var terrain_width: SpinBox
var terrain_depth: SpinBox
var cell_size: SpinBox
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
var cached_terrain: Node
var cached_scene_root: Node
var cursor_hit := Vector3.ZERO
var cursor_valid := false
var cursor_mesh: MeshInstance3D
var cursor_material: StandardMaterial3D
var stroke_timer := 0.0
var import_dialog: FileDialog
var export_dialog: FileDialog
var status_label: Label

func _enter_tree() -> void:
	terrain_button = Button.new()
	terrain_button.text = "Terreno 3D"
	terrain_button.tooltip_text = "Abrir las herramientas de terreno 3D"
	terrain_button.pressed.connect(_toggle_panel)
	add_control_to_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, terrain_button)
	_build_panel()
	set_process(true)

func handles(object: Object) -> bool:
	return object is Node and object.has_meta(TERRAIN_META)

func _exit_tree() -> void:
	if terrain_button:
		remove_control_from_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, terrain_button)
		terrain_button.queue_free()
	if panel:
		remove_control_from_bottom_panel(panel)
		panel.queue_free()
	if cursor_mesh and is_instance_valid(cursor_mesh):
		cursor_mesh.queue_free()
	if import_dialog:
		import_dialog.queue_free()
	if export_dialog:
		export_dialog.queue_free()

func _build_panel() -> void:
	panel = VBoxContainer.new()
	panel.name = "Terrain3DEditorPanel"
	panel.custom_minimum_size = Vector2(260, 0)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_child(scroll)
	var content := VBoxContainer.new()
	content.custom_minimum_size = Vector2(240, 0)
	content.add_theme_constant_override("separation", 6)
	scroll.add_child(content)

	var title := Label.new()
	title.text = "TERRENO 3D"
	title.add_theme_font_size_override("font_size", 18)
	content.add_child(title)
	var intro := Label.new()
	intro.text = "Crea, esculpe y pinta el terreno directamente en la vista 3D. Usa el joystick para mover el cursor."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(intro)

	_add_section(content, "Crear terreno")
	terrain_width = _add_spin(content, "Resolución X", 65, 9, 257, 8)
	terrain_depth = _add_spin(content, "Resolución Z", 65, 9, 257, 8)
	cell_size = _add_spin(content, "Tamaño de celda", 1.0, 0.1, 16.0, 0.1)
	var create_button := Button.new()
	create_button.text = "Crear terreno editable"
	create_button.pressed.connect(_create_terrain)
	content.add_child(create_button)

	_add_section(content, "Herramientas de edición")
	mode_picker = OptionButton.new()
	for mode in ["Elevar", "Bajar", "Suavizar", "Aplanar", "Pintar color", "Pintar capa de material"]
		mode_picker.add_item(mode)
	content.add_child(mode_picker)
	brush_radius = _add_slider(content, "Radio del pincel", 4.0, 0.5, 24.0, 0.5)
	brush_strength = _add_slider(content, "Intensidad", 0.35, 0.01, 1.0, 0.01)
	flatten_height = _add_spin(content, "Altura objetivo", 0.0, -100.0, 100.0, 0.25)
	paint_color = ColorPickerButton.new()
	paint_color.color = Color(0.24, 0.48, 0.20)
	paint_color.text = "Color del terreno"
	content.add_child(paint_color)
	layer_picker = OptionButton.new()
	for layer_name in ["Hierba", "Roca", "Arena", "Nieve"]:
		layer_picker.add_item(layer_name)
	content.add_child(layer_picker)
	grid_snap = CheckButton.new()
	grid_snap.text = "Ajustar pincel a cuadrícula"
	grid_snap.button_pressed = false
	content.add_child(grid_snap)
	var focus_button := Button.new()
	focus_button.text = "Enfocar terreno en la vista 3D"
	focus_button.pressed.connect(_focus_terrain)
	content.add_child(focus_button)
	var collision_button := Button.new()
	collision_button.text = "Regenerar colisiones"
	collision_button.pressed.connect(_regenerate_collision)
	content.add_child(collision_button)
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
	content.add_child(undo_row)

	_add_section(content, "Cursor móvil")
	var joystick_row := HBoxContainer.new()
	joystick_pad = Panel.new()
	joystick_pad.custom_minimum_size = Vector2(112, 112)
	joystick_pad.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	joystick_pad.gui_input.connect(_on_joystick_input)
	joystick_row.add_child(joystick_pad)
	var joystick_help := Label.new()
	joystick_help.text = "Mantén y arrastra aquí para mover el cursor sobre el terreno."
	joystick_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	joystick_help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	joystick_row.add_child(joystick_help)
	content.add_child(joystick_row)
	var recenter := Button.new()
	recenter.text = "Centrar cursor"
	recenter.pressed.connect(func(): joystick_vector = Vector2.ZERO)
	content.add_child(recenter)
	continuous_stroke = CheckButton.new()
	continuous_stroke.text = "Trazo continuo mientras muevo el joystick"
	content.add_child(continuous_stroke)
	var apply_button := Button.new()
	apply_button.text = "Aplicar pincel en cursor"
	apply_button.pressed.connect(_apply_at_cursor)
	content.add_child(apply_button)

	_add_section(content, "Altura y vegetación")
	height_scale = _add_spin(content, "Escala de altura", 20.0, 0.1, 250.0, 1.0)
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
	content.add_child(heightmap_row)
	foliage_count = _add_spin(content, "Cantidad de árboles", 180, 1, 5000, 10)
	var foliage_button := Button.new()
	foliage_button.text = "Distribuir árboles"
	foliage_button.pressed.connect(_scatter_foliage)
	content.add_child(foliage_button)

	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_label.text = "Selecciona un terreno o crea uno nuevo."
	content.add_child(status_label)

	add_control_to_bottom_panel(panel, "Terreno 3D")
	panel.hide()
	_create_cursor()

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

func _add_section(parent: Control, text: String) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 15)
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
	spin.custom_minimum_size = Vector2(96, 0)
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
	if panel.visible:
		hide_bottom_panel()
	else:
		make_bottom_panel_item_visible(panel)

func _create_terrain() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null:
		_set_status("Primero crea o abre una escena.")
		return
	var terrain_script = load(TERRAIN_SCRIPT)
	if terrain_script == null:
		_set_status("No se encontró terrain_data.gd.")
		return
	var terrain = terrain_script.new()
	terrain.name = "Terrain3D_%d" % (root.get_child_count() + 1)
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
	_set_status("Terreno creado. Usa el pincel en la vista 3D o el joystick de este panel.")

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
	cursor_update_timer += delta
	stroke_timer += delta
	# Cap terrain raycasts to 20 Hz on mobile; the cursor remains responsive without
	# querying physics at the display refresh rate while the editor is otherwise idle.
	if cursor_update_timer < 0.05:
		return
	cursor_update_timer = 0.0
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
	var local := terrain.to_local(world_position)
	if grid_snap.button_pressed:
		local.x = roundf(local.x / terrain.cell_size) * terrain.cell_size
		local.z = roundf(local.z / terrain.cell_size) * terrain.cell_size
	var radius := brush_radius.value
	var strength := brush_strength.value
	var mode := mode_picker.get_selected_id()
	if mode == 4:
		var old_colors: PackedColorArray = terrain.vertex_colors.duplicate()
		var new_colors: PackedColorArray = old_colors.duplicate()
		for z in range(terrain.grid_depth):
			for x in range(terrain.grid_width):
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
		var selected_layer := layer_picker.selected
		for z in range(terrain.grid_depth):
			for x in range(terrain.grid_width):
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
	for z in range(terrain.grid_depth):
		for x in range(terrain.grid_width):
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
	undo_redo.add_do_method(terrain, method, new_value)
	undo_redo.add_undo_method(terrain, method, old_value)
	undo_redo.commit_action()
	_set_status(action_name + " aplicado. Usa Deshacer/Rehacer para revisar el cambio.")

func _focus_terrain() -> void:
	var terrain = _get_terrain()
	var viewport := EditorInterface.get_editor_viewport_3d(0)
	if terrain == null or viewport == null or viewport.get_camera_3d() == null:
		_set_status("Selecciona o crea un terreno para enfocarlo.")
		return
	var camera := viewport.get_camera_3d()
	var center := terrain.global_position
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
	var image := Image.create(terrain.grid_width, terrain.grid_depth, false, Image.FORMAT_L8)
	var minimum := 0.0
	var maximum := 0.0
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

func _set_status(message: String) -> void:
	if status_label:
		status_label.text = message
