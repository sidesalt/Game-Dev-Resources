extends SceneTree
## Bakes Cinder's voxel assets.
##
##   godot --headless --path . --import                       # once, registers classes
##   godot --headless --path . --script res://tools/bake.gd    # bake
##   godot --headless --path . --import                       # import new .vox files
##
## Step 1: every recipe in assets/recipes/ is written to assets/vox/<name>.vox,
##         unless that file already exists (it may have been edited by hand in
##         MagicaVoxel). Pass --force to regenerate from the recipe anyway.
## Step 2: every .vox in assets/vox/ (hand-made ones too) gets a ready-to-place
##         scene in assets/scenes/: mesh, collision and, if it glows, a light.
##
## Options (after `--`): --force, --only=campfire,barrel, --report=failed.txt (lists
## recipes that did not build)

const RECIPE_DIR := "res://assets/recipes/"
const VOX_DIR := "res://assets/vox/"
const SCENE_DIR := "res://assets/scenes/"
const EMBER_LIGHT := preload("res://assets/ember_light.gd")


func _init() -> void:
	var force := false
	var only := PackedStringArray()
	var report := ""
	for arg in OS.get_cmdline_user_args():
		if arg == "--force":
			force = true
		elif arg.begins_with("--report="):
			report = arg.trim_prefix("--report=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",", false)

	DirAccess.make_dir_recursive_absolute(VOX_DIR)
	DirAccess.make_dir_recursive_absolute(SCENE_DIR)

	for file in DirAccess.get_files_at(RECIPE_DIR):
		if not file.ends_with(".gd"):
			continue
		var asset := file.get_basename()
		if not only.is_empty() and asset not in only:
			continue
		var vox_path := VOX_DIR + asset + ".vox"
		if FileAccess.file_exists(vox_path) and not force:
			print("keep   %s (exists; --force to regenerate)" % vox_path)
			continue
		var recipe: GDScript = load(RECIPE_DIR + file)
		# A broken recipe (say, a bad AI one) is skipped and reported instead of
		# stopping every other asset from building.
		if recipe == null or not recipe.can_instantiate() or not recipe.has_method("build"):
			_fail(asset, "does not load (script error)")
			continue
		var start := Time.get_ticks_msec()
		var tune := Tuning.load_for(asset)
		var seed: int = int(tune.seed) if int(tune.seed) > 0 else _const(recipe, "SEED", 1)
		var built: Variant = recipe.build(seed)
		if not built is VoxelModel or (built as VoxelModel).count_solid() == 0:
			_fail(asset, "build() did not return a model")
			continue
		var model: VoxelModel = built
		Tuning.apply(model, tune, seed)
		var err := VoxIO.save_file(model, ProjectSettings.globalize_path(vox_path))
		if err != OK:
			push_error("Could not write %s: %s" % [vox_path, error_string(err)])
			continue
		print("recipe %s -> %s (%d voxels, %d colours, %d ms)" % [
			asset, vox_path, model.count_solid(), model.colors.size() - 1, Time.get_ticks_msec() - start])

	for file in DirAccess.get_files_at(VOX_DIR):
		if not file.ends_with(".vox"):
			continue
		var asset := file.get_basename()
		if not only.is_empty() and asset not in only:
			continue
		_bake_scene(asset)
	if report != "":
		var out := FileAccess.open(report, FileAccess.WRITE)
		if out:
			out.store_string("\n".join(failed) + ("\n" if not failed.is_empty() else ""))
	quit()


var failed := PackedStringArray()


func _fail(asset: String, why: String) -> void:
	push_error("FAILED %s: %s" % [asset, why])
	failed.append(asset)


func _bake_scene(asset: String) -> void:
	var vox_path := VOX_DIR + asset + ".vox"
	var model := VoxIO.load_file(vox_path)
	if model == null:
		return
	var recipe: GDScript = null
	if FileAccess.file_exists(RECIPE_DIR + asset + ".gd"):
		recipe = load(RECIPE_DIR + asset + ".gd")
	var pivot: Vector3 = _const(recipe, "PIVOT", Vector3(0.5, 0.0, 0.5))
	var collision: String = _const(recipe, "COLLISION", "convex")
	var voxel_size := VoxelMesher.DEFAULT_VOXEL_SIZE
	var offset := VoxelMesher.pivot_offset(model, pivot)

	var mesh := VoxelMesher.build(model, voxel_size, pivot)
	# Saved as a reference to the imported .vox, so edits in MagicaVoxel flow
	# straight into this scene on the next import.
	mesh.take_over_path(vox_path)

	var root := Node3D.new()
	root.name = asset.to_pascal_case()
	var size_scale: float = Tuning.load_for(asset).scale
	root.scale = Vector3.ONE * size_scale
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "Mesh"
	mesh_instance.mesh = mesh
	_add(root, root, mesh_instance)

	if collision != "none":
		var body := StaticBody3D.new()
		body.name = "Body"
		_add(root, root, body)
		var shape := CollisionShape3D.new()
		shape.name = "Shape"
		if collision == "trunk":
			var radius: float = _const(recipe, "TRUNK_RADIUS", 2.0)
			var cylinder := CylinderShape3D.new()
			cylinder.radius = radius * voxel_size
			cylinder.height = model.size.y * voxel_size
			shape.shape = cylinder
			shape.position = Vector3(0, cylinder.height * 0.5 - offset.y * voxel_size, 0)
		else:
			shape.shape = mesh.create_convex_shape(true, true)
		_add(root, body, shape)

	var glow := model.emissive_summary()
	if not glow.is_empty():
		var light := OmniLight3D.new()
		light.name = "EmberLight"
		light.set_script(EMBER_LIGHT)
		light.light_color = (glow.color as Color).lerp(Color("#ffb070"), 0.35)
		light.light_energy = clampf(0.3 + sqrt(glow.weight) * 0.05, 0.3, 1.4)
		light.omni_range = clampf(1.0 + sqrt(glow.count) * 0.06, 1.0, 5.0)
		light.omni_attenuation = 1.4
		# Lights sit inside their own glowing voxels, which would block shadows.
		light.shadow_enabled = false
		light.position = (glow.center - offset) * voxel_size + Vector3(0, 2.0 * voxel_size, 0)
		_add(root, root, light)

	var packed := PackedScene.new()
	packed.pack(root)
	var scene_path := SCENE_DIR + asset + ".tscn"
	var err := ResourceSaver.save(packed, scene_path)
	root.free()
	if err != OK:
		push_error("Could not save %s: %s" % [scene_path, error_string(err)])
	else:
		print("scene  %s (%d triangles)" % [scene_path, mesh.surface_get_array_index_len(0) / 3 if mesh.get_surface_count() else 0])


func _add(root: Node, parent: Node, child: Node) -> void:
	parent.add_child(child)
	child.owner = root


func _const(script: GDScript, key: String, fallback: Variant) -> Variant:
	if script == null:
		return fallback
	return script.get_script_constant_map().get(key, fallback)
