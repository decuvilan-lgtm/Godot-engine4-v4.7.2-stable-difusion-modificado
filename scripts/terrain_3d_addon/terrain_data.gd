@tool
extends MeshInstance3D
## Editable grid terrain for the custom Godot Android editor.

@export_group("Geometría")
@export_storage var grid_width: int = 65:
	set(value):
		var previous_width := grid_width
		grid_width = clampi(value, 9, 257)
		if is_inside_tree() and not _suppress_grid_setters and previous_width != grid_width:
			_resize_grid_preserving_data(previous_width, grid_depth)
@export_storage var grid_depth: int = 65:
	set(value):
		var previous_depth := grid_depth
		grid_depth = clampi(value, 9, 257)
		if is_inside_tree() and not _suppress_grid_setters and previous_depth != grid_depth:
			_resize_grid_preserving_data(grid_width, previous_depth)
@export_range(0.1, 16.0, 0.1) var cell_size: float = 1.0:
	set(value):
		cell_size = clampf(value, 0.1, 16.0) if is_finite(value) else 1.0
		if is_inside_tree() and not _suppress_grid_setters and heights.size() == grid_width * grid_depth:
			_rebuild_mesh()
			_rebuild_collision()
@export_enum("Cuadrada / rectangular", "Circular / elíptica") var footprint_shape: int = 0:
	set(value):
		footprint_shape = clampi(value, 0, 1)
		if is_inside_tree() and not _suppress_grid_setters and heights.size() == grid_width * grid_depth:
			_rebuild_mesh()
			_rebuild_collision()
@export_range(0.1, 100.0, 0.1) var base_thickness: float = 2.0:
	set(value):
		base_thickness = clampf(value, 0.1, 100.0) if is_finite(value) else 2.0
		if is_inside_tree() and not _suppress_grid_setters and heights.size() == grid_width * grid_depth:
			_rebuild_mesh()
			_rebuild_collision()
@export_range(1.0, 1000.0, 1.0) var max_height: float = 100.0:
	set(value):
		max_height = clampf(value, 1.0, 1000.0) if is_finite(value) else 100.0
		if is_inside_tree() and not _suppress_grid_setters and heights.size() == grid_width * grid_depth:
			# Keep existing sculpted values intact so Inspector undo/redo only
			# changes the height limit; new brush edits obey this limit.
			_rebuild_mesh()
			_rebuild_collision()

@export_group("Material")
@export var full_surface_texture: Texture2D:
	set(value):
		full_surface_texture = value
		if terrain_material:
			terrain_material.set_shader_parameter("use_full_surface_texture", full_surface_texture != null)
			if full_surface_texture:
				terrain_material.set_shader_parameter("full_surface_texture", full_surface_texture)
@export var stretch_full_surface_texture: bool = true:
	set(value):
		stretch_full_surface_texture = value
		if terrain_material:
			terrain_material.set_shader_parameter("stretch_full_surface_texture", stretch_full_surface_texture)

@export_storage var heights: PackedFloat32Array = PackedFloat32Array()
@export_storage var vertex_colors: PackedColorArray = PackedColorArray()
@export_storage var layer_weights: PackedColorArray = PackedColorArray()
var collision_body: StaticBody3D
var terrain_material: ShaderMaterial
var _suppress_grid_setters := false

func _ready() -> void:
	var existing_collision := get_node_or_null("TerrainCollision")
	if existing_collision is StaticBody3D:
		collision_body = existing_collision
	var existing_material := get_surface_override_material(0)
	if existing_material is ShaderMaterial:
		terrain_material = existing_material
	if terrain_material:
		terrain_material.set_shader_parameter("use_full_surface_texture", full_surface_texture != null)
		if full_surface_texture:
			terrain_material.set_shader_parameter("full_surface_texture", full_surface_texture)
		terrain_material.set_shader_parameter("stretch_full_surface_texture", stretch_full_surface_texture)

func _resize_grid_preserving_data(old_width: int, old_depth: int) -> void:
	var new_width := grid_width
	var new_depth := grid_depth
	var old_heights := heights.duplicate()
	var old_colors := vertex_colors.duplicate()
	var old_weights := layer_weights.duplicate()
	var valid_old := old_width >= 2 and old_depth >= 2 and old_heights.size() == old_width * old_depth
	heights.resize(new_width * new_depth)
	vertex_colors.resize(new_width * new_depth)
	layer_weights.resize(new_width * new_depth)
	for z in range(new_depth):
		for x in range(new_width):
			var index := z * new_width + x
			if valid_old:
				var source_x := float(x) * float(old_width - 1) / float(maxi(1, new_width - 1))
				var source_z := float(z) * float(old_depth - 1) / float(maxi(1, new_depth - 1))
				heights[index] = _sample_float_grid(old_heights, old_width, old_depth, source_x, source_z)
				vertex_colors[index] = _sample_color_grid(old_colors, old_width, old_depth, source_x, source_z, Color.WHITE)
				layer_weights[index] = _sample_color_grid(old_weights, old_width, old_depth, source_x, source_z, Color(1.0, 0.0, 0.0, 0.0))
			else:
				heights[index] = 0.0
				vertex_colors[index] = Color.WHITE
				layer_weights[index] = Color(1.0, 0.0, 0.0, 0.0)
	_rebuild_mesh()
	_rebuild_collision()

func _sample_float_grid(values: PackedFloat32Array, width: int, depth: int, x: float, z: float) -> float:
	if values.size() != width * depth:
		return 0.0
	var x0 := clampi(floori(x), 0, width - 1)
	var z0 := clampi(floori(z), 0, depth - 1)
	var x1 := mini(x0 + 1, width - 1)
	var z1 := mini(z0 + 1, depth - 1)
	var tx := x - float(x0)
	var tz := z - float(z0)
	var top := lerpf(values[z0 * width + x0], values[z0 * width + x1], tx)
	var bottom := lerpf(values[z1 * width + x0], values[z1 * width + x1], tx)
	return lerpf(top, bottom, tz)

func _sample_color_grid(values: PackedColorArray, width: int, depth: int, x: float, z: float, fallback: Color) -> Color:
	if values.size() != width * depth:
		return fallback
	var x0 := clampi(floori(x), 0, width - 1)
	var z0 := clampi(floori(z), 0, depth - 1)
	var x1 := mini(x0 + 1, width - 1)
	var z1 := mini(z0 + 1, depth - 1)
	var tx := x - float(x0)
	var tz := z - float(z0)
	var top := values[z0 * width + x0].lerp(values[z0 * width + x1], tx)
	var bottom := values[z1 * width + x0].lerp(values[z1 * width + x1], tx)
	return top.lerp(bottom, tz)

func initialize_grid(p_width: int, p_depth: int, p_cell_size: float) -> void:
	# Validate all dimensions before allocating arrays or generating geometry.
	# Keep the existing quality ceiling, but never allow malformed serialized values.
	_suppress_grid_setters = true
	grid_width = clampi(p_width, 9, 257)
	grid_depth = clampi(p_depth, 9, 257)
	cell_size = clampf(p_cell_size, 0.1, 16.0) if is_finite(p_cell_size) else 1.0
	_suppress_grid_setters = false
	heights.resize(grid_width * grid_depth)
	vertex_colors.resize(grid_width * grid_depth)
	layer_weights.resize(grid_width * grid_depth)
	for i in range(vertex_colors.size()):
		vertex_colors[i] = Color.WHITE
		layer_weights[i] = Color(1.0, 0.0, 0.0, 0.0)
	_rebuild_mesh()
	_rebuild_collision()

func set_heights(values: PackedFloat32Array, update_collision: bool = true) -> void:
	if values.size() != grid_width * grid_depth:
		push_error("Terrain height array size does not match the grid.")
		return
	# Reject corrupt/non-finite heightmaps before they can poison mesh bounds,
	# collision generation, camera framing, or serialized scene data.
	for height in values:
		if not is_finite(height) or absf(height) > 10000.0:
			push_error("Terrain heights must be finite and within -10000..10000.")
			return
	var constrained_heights := values.duplicate()
	var vertical_limit := maxf(1.0, max_height)
	for i in range(constrained_heights.size()):
		constrained_heights[i] = clampf(constrained_heights[i], -vertical_limit, vertical_limit)
	heights = constrained_heights
	_rebuild_mesh()
	if update_collision:
		_rebuild_collision()

func set_vertex_colors(values: PackedColorArray) -> void:
	if values.size() != grid_width * grid_depth:
		push_error("Terrain color array size does not match the grid.")
		return
	vertex_colors = values.duplicate()
	_rebuild_mesh()

func get_layer_texture(layer_index: int) -> Texture2D:
	if terrain_material == null:
		return null
	var names := ["grass_texture", "rock_texture", "sand_texture", "snow_texture"]
	if layer_index < 0 or layer_index >= names.size():
		return null
	return terrain_material.get_shader_parameter(names[layer_index])

func set_layer_texture(layer_index: int, texture: Texture2D) -> void:
	if terrain_material == null:
		terrain_material = _create_terrain_material()
	var names := ["grass_texture", "rock_texture", "sand_texture", "snow_texture"]
	if layer_index < 0 or layer_index >= names.size():
		return
	terrain_material.set_shader_parameter(names[layer_index], texture)
	set_surface_override_material(0, terrain_material)


func set_full_surface_texture(texture: Texture2D, stretch: bool = true) -> void:
	full_surface_texture = texture
	stretch_full_surface_texture = stretch
	if terrain_material == null:
		terrain_material = _create_terrain_material()
	terrain_material.set_shader_parameter("full_surface_texture", texture if texture else _make_noise_texture(97, 0.04))
	terrain_material.set_shader_parameter("use_full_surface_texture", texture != null)
	terrain_material.set_shader_parameter("stretch_full_surface_texture", stretch)
	set_surface_override_material(0, terrain_material)

func set_layer_weights(values: PackedColorArray) -> void:
	if values.size() != grid_width * grid_depth:
		push_error("Terrain layer-weight array size does not match the grid.")
		return
	layer_weights = values.duplicate()
	_rebuild_mesh()

func get_height_index(x: int, z: int) -> int:
	return z * grid_width + x

func get_vertex_local_position(x: int, z: int) -> Vector3:
	return Vector3(
		(float(x) - float(grid_width - 1) * 0.5) * cell_size,
		heights[get_height_index(x, z)],
		(float(z) - float(grid_depth - 1) * 0.5) * cell_size
	)

func sample_height_local(x: float, z: float) -> float:
	var gx := x / cell_size + float(grid_width - 1) * 0.5
	var gz := z / cell_size + float(grid_depth - 1) * 0.5
	if gx < 0.0 or gz < 0.0 or gx > grid_width - 1 or gz > grid_depth - 1:
		return -INF
	var x0 := clampi(floori(gx), 0, grid_width - 1)
	var z0 := clampi(floori(gz), 0, grid_depth - 1)
	var x1 := mini(x0 + 1, grid_width - 1)
	var z1 := mini(z0 + 1, grid_depth - 1)
	var fx := gx - x0
	var fz := gz - z0
	var h00 := heights[get_height_index(x0, z0)]
	var h10 := heights[get_height_index(x1, z0)]
	var h01 := heights[get_height_index(x0, z1)]
	var h11 := heights[get_height_index(x1, z1)]
	return lerpf(lerpf(h00, h10, fx), lerpf(h01, h11, fx), fz)

func _rebuild_mesh() -> void:
	if heights.size() != grid_width * grid_depth:
		heights.resize(grid_width * grid_depth)
	if vertex_colors.size() != grid_width * grid_depth:
		vertex_colors.resize(grid_width * grid_depth)
		for i in range(vertex_colors.size()):
			vertex_colors[i] = Color.WHITE
	if layer_weights.size() != grid_width * grid_depth:
		layer_weights.resize(grid_width * grid_depth)
		for i in range(layer_weights.size()):
			layer_weights[i] = Color(1.0, 0.0, 0.0, 0.0)
	var st := SurfaceTool.new()
	st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA8_UNORM)
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var lowest_height := 0.0
	for height in heights:
		lowest_height = minf(lowest_height, height)
	var bottom_y := lowest_height - maxf(0.1, base_thickness)
	for z in range(grid_depth - 1):
		for x in range(grid_width - 1):
			if not _cell_inside_footprint(x, z):
				continue
			var i00 := get_height_index(x, z)
			var i10 := get_height_index(x + 1, z)
			var i01 := get_height_index(x, z + 1)
			var i11 := get_height_index(x + 1, z + 1)
			# Top surface.
			_add_vertex(st, x, z, i00)
			_add_vertex(st, x, z + 1, i01)
			_add_vertex(st, x + 1, z, i10)
			_add_vertex(st, x + 1, z, i10)
			_add_vertex(st, x, z + 1, i01)
			_add_vertex(st, x + 1, z + 1, i11)
			# Underside closes the terrain into a solid, collision-ready volume.
			_add_bottom_vertex(st, x, z, i00, bottom_y)
			_add_bottom_vertex(st, x + 1, z, i10, bottom_y)
			_add_bottom_vertex(st, x, z + 1, i01, bottom_y)
			_add_bottom_vertex(st, x + 1, z, i10, bottom_y)
			_add_bottom_vertex(st, x + 1, z + 1, i11, bottom_y)
			_add_bottom_vertex(st, x, z + 1, i01, bottom_y)
			# Add vertical walls wherever this footprint cell borders empty space.
			var p00 := get_vertex_local_position(x, z)
			var p10 := get_vertex_local_position(x + 1, z)
			var p01 := get_vertex_local_position(x, z + 1)
			var p11 := get_vertex_local_position(x + 1, z + 1)
			if not _cell_inside_footprint(x, z - 1):
				_add_wall(st, p00, p10, bottom_y, i00, i10)
			if not _cell_inside_footprint(x, z + 1):
				_add_wall(st, p11, p01, bottom_y, i11, i01)
			if not _cell_inside_footprint(x - 1, z):
				_add_wall(st, p01, p00, bottom_y, i01, i00)
			if not _cell_inside_footprint(x + 1, z):
				_add_wall(st, p10, p11, bottom_y, i10, i11)
	# Share identical vertices to keep the 257x257 Android mesh bounded.
	st.index()
	st.generate_normals()
	mesh = st.commit()
	if mesh == null:
		push_error("Could not build the terrain mesh.")
		return
	if terrain_material == null:
		terrain_material = _create_terrain_material()
	set_surface_override_material(0, terrain_material)

func _create_terrain_material() -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
uniform sampler2D grass_texture : repeat_enable;
uniform sampler2D rock_texture : repeat_enable;
uniform sampler2D sand_texture : repeat_enable;
uniform sampler2D snow_texture : repeat_enable;
uniform sampler2D full_surface_texture : source_color, repeat_enable;
uniform bool use_full_surface_texture = false;
uniform bool stretch_full_surface_texture = true;
uniform vec3 grass_tint : source_color = vec3(0.25, 0.46, 0.18);
uniform vec3 rock_tint : source_color = vec3(0.38, 0.39, 0.40);
uniform vec3 sand_tint : source_color = vec3(0.68, 0.56, 0.34);
uniform vec3 snow_tint : source_color = vec3(0.88, 0.92, 0.96);
varying vec4 terrain_weights;
void vertex() {
	terrain_weights = CUSTOM0;
}
void fragment() {
	vec4 w = max(terrain_weights, vec4(0.0));
	w /= max(dot(w, vec4(1.0)), 0.0001);
	vec2 tiled_uv = UV * 12.0;
	vec3 grass = texture(grass_texture, tiled_uv).rgb * grass_tint;
	vec3 rock = texture(rock_texture, tiled_uv * 1.7).rgb * rock_tint;
	vec3 sand = texture(sand_texture, tiled_uv * 0.7).rgb * sand_tint;
	vec3 snow = texture(snow_texture, tiled_uv * 1.2).rgb * snow_tint;
	if (use_full_surface_texture) {
		vec2 image_uv = UV;
		if (!stretch_full_surface_texture) {
			image_uv = tiled_uv;
		}
		ALBEDO = texture(full_surface_texture, image_uv).rgb * COLOR.rgb;
	} else {
		ALBEDO = (grass * w.r + rock * w.g + sand * w.b + snow * w.a) * COLOR.rgb;
	}
	ROUGHNESS = 0.92;
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("grass_texture", _make_noise_texture(11, 0.035))
	material.set_shader_parameter("rock_texture", _make_noise_texture(37, 0.09))
	material.set_shader_parameter("sand_texture", _make_noise_texture(59, 0.055))
	material.set_shader_parameter("snow_texture", _make_noise_texture(83, 0.025))
	material.set_shader_parameter("full_surface_texture", _make_noise_texture(97, 0.04))
	material.set_shader_parameter("use_full_surface_texture", false)
	material.set_shader_parameter("stretch_full_surface_texture", true)
	return material

func _make_noise_texture(seed_value: int, frequency: float) -> NoiseTexture2D:
	var noise := FastNoiseLite.new()
	noise.seed = seed_value
	noise.frequency = frequency
	noise.fractal_octaves = 3
	var texture := NoiseTexture2D.new()
	texture.width = 128
	texture.height = 128
	texture.seamless = true
	texture.noise = noise
	return texture

func _cell_inside_footprint(x: int, z: int) -> bool:
	if x < 0 or z < 0 or x >= grid_width - 1 or z >= grid_depth - 1:
		return false
	if footprint_shape == 0:
		return true
	var nx := (float(x) + 0.5 - float(grid_width - 1) * 0.5) / maxf(0.5, float(grid_width - 1) * 0.5)
	var nz := (float(z) + 0.5 - float(grid_depth - 1) * 0.5) / maxf(0.5, float(grid_depth - 1) * 0.5)
	return nx * nx + nz * nz <= 1.0

func _add_custom_vertex(st: SurfaceTool, position: Vector3, color: Color, weights: Color, uv: Vector2) -> void:
	st.set_color(color)
	st.set_custom(0, weights)
	st.set_uv(uv)
	st.add_vertex(position)

func _add_vertex(st: SurfaceTool, x: int, z: int, color_index: int) -> void:
	_add_custom_vertex(st, get_vertex_local_position(x, z), vertex_colors[color_index], layer_weights[color_index], Vector2(float(x) / float(grid_width - 1), float(z) / float(grid_depth - 1)))

func _add_bottom_vertex(st: SurfaceTool, x: int, z: int, color_index: int, bottom_y: float) -> void:
	var position := get_vertex_local_position(x, z)
	position.y = bottom_y
	_add_custom_vertex(st, position, vertex_colors[color_index], layer_weights[color_index], Vector2(float(x) / float(grid_width - 1), float(z) / float(grid_depth - 1)))

func _add_wall(st: SurfaceTool, top_a: Vector3, top_b: Vector3, bottom_y: float, index_a: int, index_b: int) -> void:
	var bottom_a := Vector3(top_a.x, bottom_y, top_a.z)
	var bottom_b := Vector3(top_b.x, bottom_y, top_b.z)
	var uv_a := Vector2(top_a.x, top_a.z) / maxf(cell_size, 0.1)
	var uv_b := Vector2(top_b.x, top_b.z) / maxf(cell_size, 0.1)
	var color_a: Color = vertex_colors[index_a]
	var color_b: Color = vertex_colors[index_b]
	var weight_a: Color = layer_weights[index_a]
	var weight_b: Color = layer_weights[index_b]
	_add_custom_vertex(st, top_a, color_a, weight_a, uv_a)
	_add_custom_vertex(st, bottom_a, color_a, weight_a, uv_a)
	_add_custom_vertex(st, top_b, color_b, weight_b, uv_b)
	_add_custom_vertex(st, top_b, color_b, weight_b, uv_b)
	_add_custom_vertex(st, bottom_a, color_a, weight_a, uv_a)
	_add_custom_vertex(st, bottom_b, color_b, weight_b, uv_b)

func rebuild_collision() -> void:
	_rebuild_collision()

func _rebuild_collision() -> void:
	if mesh == null:
		push_warning("Terrain collision was not rebuilt because the terrain mesh is empty.")
		return
	if collision_body and is_instance_valid(collision_body):
		collision_body.free()
	collision_body = StaticBody3D.new()
	collision_body.name = "TerrainCollision"
	collision_body.collision_layer = 1
	collision_body.collision_mask = 1
	add_child(collision_body)
	if owner:
		collision_body.owner = owner
	var collision := CollisionShape3D.new()
	collision.name = "CollisionShape3D"
	collision.shape = mesh.create_trimesh_shape()
	if collision.shape == null:
		collision_body.free()
		collision_body = null
		push_error("Could not create a collision shape for this terrain mesh.")
		return
	collision_body.add_child(collision)
	if owner:
		collision.owner = owner

func apply_heightmap(image: Image, height_scale: float) -> void:
	if image.is_empty():
		push_warning("The supplied heightmap image is empty.")
		return
	if not is_finite(height_scale) or height_scale <= 0.0:
		push_error("Heightmap scale must be a finite positive number.")
		return
	var resized := image.duplicate()
	resized.resize(grid_width, grid_depth, Image.INTERPOLATE_BILINEAR)
	var next_heights := PackedFloat32Array()
	next_heights.resize(grid_width * grid_depth)
	for z in range(grid_depth):
		for x in range(grid_width):
			next_heights[get_height_index(x, z)] = resized.get_pixel(x, z).get_luminance() * height_scale
	set_heights(next_heights)

func create_foliage(count: int, seed_value: int = 1701) -> Node3D:
	var root := Node3D.new()
	root.name = "TerrainFoliage"
	var amount := clampi(count, 1, 5000)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	# Godot 4.7 has CylinderMesh but no ConeMesh primitive. A zero top radius
	# creates a cone while remaining compatible with the engine's built-in mesh API.
	var canopy_mesh := CylinderMesh.new()
	canopy_mesh.top_radius = 0.0
	canopy_mesh.bottom_radius = 0.65
	canopy_mesh.height = 1.8
	var trunk_mesh := CylinderMesh.new()
	trunk_mesh.top_radius = 0.12
	trunk_mesh.bottom_radius = 0.18
	trunk_mesh.height = 0.8
	var canopy_multi := MultiMesh.new()
	canopy_multi.transform_format = MultiMesh.TRANSFORM_3D
	canopy_multi.mesh = canopy_mesh
	canopy_multi.instance_count = amount
	var trunk_multi := MultiMesh.new()
	trunk_multi.transform_format = MultiMesh.TRANSFORM_3D
	trunk_multi.mesh = trunk_mesh
	trunk_multi.instance_count = amount
	var span_x := float(grid_width - 1) * cell_size
	var span_z := float(grid_depth - 1) * cell_size
	for i in range(amount):
		var x := rng.randf_range(-span_x * 0.48, span_x * 0.48)
		var z := rng.randf_range(-span_z * 0.48, span_z * 0.48)
		var y := sample_height_local(x, z)
		if is_inf(y):
			y = 0.0
		var scale := rng.randf_range(0.65, 1.45)
		var yaw := rng.randf_range(0.0, TAU)
		var basis := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * scale)
		canopy_multi.set_instance_transform(i, Transform3D(basis, Vector3(x, y + 1.15 * scale, z)))
		trunk_multi.set_instance_transform(i, Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3(scale, scale, scale)), Vector3(x, y + 0.4 * scale, z)))
	var canopy := MultiMeshInstance3D.new()
	canopy.name = "TreeCanopies"
	canopy.multimesh = canopy_multi
	var canopy_material := StandardMaterial3D.new()
	canopy_material.albedo_color = Color(0.12, 0.34, 0.16)
	canopy_material.roughness = 1.0
	canopy.material_override = canopy_material
	root.add_child(canopy)
	var trunks := MultiMeshInstance3D.new()
	trunks.name = "TreeTrunks"
	trunks.multimesh = trunk_multi
	var trunk_material := StandardMaterial3D.new()
	trunk_material.albedo_color = Color(0.28, 0.16, 0.08)
	trunks.material_override = trunk_material
	root.add_child(trunks)
	return root

func set_foliage_owner(node: Node) -> void:
	_assign_owner_recursive(node, owner)

func _assign_owner_recursive(node: Node, scene_owner: Node) -> void:
	if scene_owner:
		node.owner = scene_owner
	for child in node.get_children():
		_assign_owner_recursive(child, scene_owner)
