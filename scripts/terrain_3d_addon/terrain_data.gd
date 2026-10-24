@tool
extends MeshInstance3D
## Editable grid terrain for the custom Godot Android editor.

@export var grid_width: int = 65
@export var grid_depth: int = 65
@export var cell_size: float = 1.0
@export_storage var heights: PackedFloat32Array = PackedFloat32Array()
@export_storage var vertex_colors: PackedColorArray = PackedColorArray()
@export_storage var layer_weights: PackedColorArray = PackedColorArray()
var collision_body: StaticBody3D
var terrain_material: ShaderMaterial

func _ready() -> void:
	var existing_collision := get_node_or_null("TerrainCollision")
	if existing_collision is StaticBody3D:
		collision_body = existing_collision
	var existing_material := get_surface_override_material(0)
	if existing_material is ShaderMaterial:
		terrain_material = existing_material

func initialize_grid(p_width: int, p_depth: int, p_cell_size: float) -> void:
	grid_width = clampi(p_width, 9, 257)
	grid_depth = clampi(p_depth, 9, 257)
	cell_size = clampf(p_cell_size, 0.1, 16.0)
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
	heights = values.duplicate()
	_rebuild_mesh()
	if update_collision:
		_rebuild_collision()

func set_vertex_colors(values: PackedColorArray) -> void:
	if values.size() != grid_width * grid_depth:
		push_error("Terrain color array size does not match the grid.")
		return
	vertex_colors = values.duplicate()
	_rebuild_mesh()

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
	for z in range(grid_depth - 1):
		for x in range(grid_width - 1):
			var i00 := get_height_index(x, z)
			var i10 := get_height_index(x + 1, z)
			var i01 := get_height_index(x, z + 1)
			var i11 := get_height_index(x + 1, z + 1)
			# Winding is counter-clockwise from above so generated normals face upward.
			_add_vertex(st, x, z, i00)
			_add_vertex(st, x, z + 1, i01)
			_add_vertex(st, x + 1, z, i10)
			_add_vertex(st, x + 1, z, i10)
			_add_vertex(st, x, z + 1, i01)
			_add_vertex(st, x + 1, z + 1, i11)
	st.generate_normals()
	mesh = st.commit()
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
	ALBEDO = (grass * w.r + rock * w.g + sand * w.b + snow * w.a) * COLOR.rgb;
	ROUGHNESS = 0.92;
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("grass_texture", _make_noise_texture(11, 0.035))
	material.set_shader_parameter("rock_texture", _make_noise_texture(37, 0.09))
	material.set_shader_parameter("sand_texture", _make_noise_texture(59, 0.055))
	material.set_shader_parameter("snow_texture", _make_noise_texture(83, 0.025))
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

func _add_vertex(st: SurfaceTool, x: int, z: int, color_index: int) -> void:
	st.set_color(vertex_colors[color_index])
	st.set_custom(0, layer_weights[color_index])
	st.set_uv(Vector2(float(x) / float(grid_width - 1), float(z) / float(grid_depth - 1)))
	st.add_vertex(get_vertex_local_position(x, z))

func rebuild_collision() -> void:
	_rebuild_collision()

func _rebuild_collision() -> void:
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
	collision_body.add_child(collision)
	if owner:
		collision.owner = owner

func apply_heightmap(image: Image, height_scale: float) -> void:
	if image.is_empty():
		return
	var resized := image.duplicate()
	resized.resize(grid_width, grid_depth, Image.INTERPOLATE_BILINEAR)
	var next_heights := PackedFloat32Array()
	next_heights.resize(grid_width * grid_depth)
	for z in range(grid_depth):
		for x in range(grid_width):
			next_heights[get_height_index(x, z)] = resized.get_pixel(x, z).get_luminance() * height_scale
	set_heights(next_heights)

func create_foliage(count: int, seed_value: int = 1701) -> void:
	var old := get_node_or_null("TerrainFoliage")
	if old:
		old.free()
	var root := Node3D.new()
	root.name = "TerrainFoliage"
	add_child(root)
	if owner:
		root.owner = owner
	var amount := clampi(count, 1, 5000)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var canopy_mesh := ConeMesh.new()
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
	if owner:
		canopy.owner = owner
		trunks.owner = owner
