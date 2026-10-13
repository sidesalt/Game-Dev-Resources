@tool
class_name VoxelBuilder
extends RefCounted
## Procedural authoring helpers on top of VoxelModel.
##
## Shape functions take a `paint` argument: either a palette index (0 carves
## voxels away) or a Callable(p: Vector3i) -> int evaluated per voxel. Points
## and radii are in voxel units; voxel (x, y, z) has its centre at +0.5.

var model: VoxelModel
var rng := RandomNumberGenerator.new()
var noise := FastNoiseLite.new()


func _init(size: Vector3i, seed := 1) -> void:
	model = VoxelModel.create(size)
	rng.seed = seed
	noise.seed = seed
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 0.15


#region Palette

## Registers one material and returns its palette index. `color` is a Color or
## an HTML string such as "#ff6a1a".
func mat(color: Variant, emission := 0.0, roughness := 0.9, metallic := 0.0) -> int:
	return model.add_material(Color(color), emission, roughness, metallic)


## Registers a dark-to-light ramp. `emission` is a float or one value per colour.
func ramp(colors: Array, emission: Variant = 0.0, roughness := 0.9, metallic := 0.0) -> PackedInt32Array:
	var out := PackedInt32Array()
	for i in colors.size():
		var e: float = emission[i] if emission is Array else emission
		out.append(mat(colors[i], e, roughness, metallic))
	return out


## Picks a ramp entry for t in [0, 1], plus optional random jitter.
func pick(r: PackedInt32Array, t: float, jitter := 0.0) -> int:
	if jitter > 0.0:
		t += rng.randf_range(-jitter, jitter)
	return r[clampi(int(t * r.size()), 0, r.size() - 1)]


## Smooth noise in roughly [0, 1] at a voxel-space position.
func n01(p: Vector3, scale := 1.0) -> float:
	return noise.get_noise_3dv(p * scale) * 0.5 + 0.5


## Painter that walks a ramp with smooth noise blotches plus per-voxel jitter.
func noisy(r: PackedInt32Array, base := 0.5, spread := 0.35, jitter := 0.12, scale := 1.0) -> Callable:
	return func(p: Vector3i) -> int:
		return pick(r, base + (n01(Vector3(p), scale) - 0.5) * 2.0 * spread, jitter)

#endregion

#region Voxel access

func paint_at(paint: Variant, p: Vector3i) -> int:
	if paint is Callable:
		return paint.call(p)
	return paint


func set_v(p: Vector3i, paint: Variant) -> void:
	if model.has_point(p):
		model.set_voxel(p, paint_at(paint, p))


func get_v(p: Vector3i) -> int:
	return model.get_voxel(p)


func solid(p: Vector3i) -> bool:
	return model.is_solid(p)


## True if the voxel has an empty neighbour in direction `dir`.
func exposed(p: Vector3i, dir: Vector3i) -> bool:
	return not model.is_solid(p + dir)


## True if any of the six neighbours is empty.
func on_surface(p: Vector3i) -> bool:
	for dir: Vector3i in [Vector3i.UP, Vector3i.DOWN, Vector3i.LEFT, Vector3i.RIGHT, Vector3i.FORWARD, Vector3i.BACK]:
		if not model.is_solid(p + dir):
			return true
	return false

#endregion

#region Shapes

## Fills the inclusive box between two corners.
func box(a: Vector3i, b: Vector3i, paint: Variant) -> void:
	var lo := a.min(b).clamp(Vector3i.ZERO, model.size - Vector3i.ONE)
	var hi := a.max(b).clamp(Vector3i.ZERO, model.size - Vector3i.ONE)
	for z in range(lo.z, hi.z + 1):
		for y in range(lo.y, hi.y + 1):
			for x in range(lo.x, hi.x + 1):
				set_v(Vector3i(x, y, z), paint)


## Ellipsoid; `wobble` (0..1) distorts the surface with noise for organic shapes.
func ellipsoid(center: Vector3, radii: Vector3, paint: Variant, wobble := 0.0) -> void:
	var reach := radii * (1.0 + wobble) + Vector3.ONE
	var bounds := _bounds(center - reach, center + reach)
	for z in range(bounds[0].z, bounds[1].z + 1):
		for y in range(bounds[0].y, bounds[1].y + 1):
			for x in range(bounds[0].x, bounds[1].x + 1):
				var c := Vector3(x, y, z) + Vector3(0.5, 0.5, 0.5)
				var limit := 1.0
				if wobble > 0.0:
					limit += wobble * (n01(c) - 0.5) * 2.0
				if ((c - center) / radii).length_squared() <= limit * limit:
					set_v(Vector3i(x, y, z), paint)


## Tapered capsule from `a` to `b` with radius `ra` at `a` and `rb` at `b`.
## Good for logs, branches, legs and crystals (rb = 0 gives a point).
func tube(a: Vector3, b: Vector3, ra: float, rb: float, paint: Variant, wobble := 0.0) -> void:
	var reach := Vector3.ONE * (maxf(ra, rb) * (1.0 + wobble) + 1.0)
	var bounds := _bounds(a.min(b) - reach, a.max(b) + reach)
	var ab := b - a
	var len2 := maxf(ab.length_squared(), 0.0001)
	for z in range(bounds[0].z, bounds[1].z + 1):
		for y in range(bounds[0].y, bounds[1].y + 1):
			for x in range(bounds[0].x, bounds[1].x + 1):
				var c := Vector3(x, y, z) + Vector3(0.5, 0.5, 0.5)
				var t := clampf((c - a).dot(ab) / len2, 0.0, 1.0)
				var radius := lerpf(ra, rb, t)
				if wobble > 0.0:
					radius *= 1.0 + wobble * (n01(c) - 0.5) * 2.0
				if c.distance_to(a + ab * t) <= radius:
					set_v(Vector3i(x, y, z), paint)


## Vertical column centred on (cx, cz) from row y0 to y1 inclusive. `radius` is
## a float or a Callable(t: float) -> float with t going 0..1 from y0 to y1,
## which gives cones, bulges (barrels) and tiers (trees).
func column(cx: float, cz: float, y0: int, y1: int, radius: Variant, paint: Variant) -> void:
	for y in range(maxi(y0, 0), mini(y1, model.size.y - 1) + 1):
		var t := 0.0 if y1 == y0 else float(y - y0) / float(y1 - y0)
		var r: float = radius.call(t) if radius is Callable else radius
		if r <= 0.0:
			continue
		var x0 := maxi(int(floor(cx - r)), 0)
		var x1 := mini(int(ceil(cx + r)), model.size.x - 1)
		var z0 := maxi(int(floor(cz - r)), 0)
		var z1 := mini(int(ceil(cz + r)), model.size.z - 1)
		for z in range(z0, z1 + 1):
			for x in range(x0, x1 + 1):
				var dx := x + 0.5 - cx
				var dz := z + 0.5 - cz
				if dx * dx + dz * dz <= r * r:
					set_v(Vector3i(x, y, z), paint)


## One-voxel-thick line between two points.
func line(a: Vector3, b: Vector3, paint: Variant) -> void:
	var d := (b - a).abs()
	var steps := maxi(int(ceil(maxf(d.x, maxf(d.y, d.z)) * 2.0)), 1)
	for i in steps + 1:
		set_v(Vector3i(a.lerp(b, float(i) / steps).floor()), paint)

#endregion

#region Passes

## Repaints every solid voxel with fn(p: Vector3i, current: int) -> int.
## Returning 0 deletes the voxel.
func recolor(fn: Callable) -> void:
	var size := model.size
	var updates := {}
	for z in size.z:
		for y in size.y:
			for x in size.x:
				var p := Vector3i(x, y, z)
				var current := model.voxels[model.index_of(p)]
				if current != 0:
					var next: int = fn.call(p, current)
					if next != current:
						updates[p] = next
	# Applied afterwards so `fn` always sees the unmodified model.
	for p: Vector3i in updates:
		model.set_voxel(p, updates[p])


## Pixel-art style shading: voxels whose face points along `dir` move `steps`
## along their ramp (positive = lighter). Use UP to catch light on tops and
## DOWN with negative steps to darken undersides. Only touches listed ramps.
func shade(ramps: Array, dir: Vector3i, steps := 1, chance := 1.0) -> void:
	var remap := {}
	for r: PackedInt32Array in ramps:
		for i in r.size():
			remap[r[i]] = r[clampi(i + steps, 0, r.size() - 1)]
	recolor(func(p: Vector3i, current: int) -> int:
		if remap.has(current) and exposed(p, dir) and (chance >= 1.0 or rng.randf() < chance):
			return remap[current]
		return current)


## Mirrors the left half (x < size.x / 2) onto the right half.
func mirror_x() -> void:
	var size := model.size
	for z in size.z:
		for y in size.y:
			for x in size.x / 2:
				model.set_voxel(Vector3i(size.x - 1 - x, y, z), model.get_voxel(Vector3i(x, y, z)))


## Randomly removes surface voxels at or above `min_y` for a weathered silhouette.
func erode(chance: float, min_y := 0) -> void:
	recolor(func(p: Vector3i, current: int) -> int:
		if p.y >= min_y and on_surface(p) and rng.randf() < chance:
			return 0
		return current)


## Deletes voxels that are not connected (face to face) to the lowest filled
## layer: the ground for standing models, the underside for flying ones.
func remove_floating() -> void:
	var size := model.size
	var seen := PackedByteArray()
	seen.resize(model.voxels.size())
	var stack: Array[Vector3i] = []
	var low := 0
	for y in size.y:
		low = y
		var found := false
		for z in size.z:
			for x in size.x:
				if model.is_solid(Vector3i(x, y, z)):
					found = true
		if found:
			break
	for z in size.z:
		for x in size.x:
			var p := Vector3i(x, low, z)
			if model.is_solid(p):
				seen[model.index_of(p)] = 1
				stack.append(p)
	while not stack.is_empty():
		var p: Vector3i = stack.pop_back()
		for dir: Vector3i in [Vector3i.UP, Vector3i.DOWN, Vector3i.LEFT, Vector3i.RIGHT, Vector3i.FORWARD, Vector3i.BACK]:
			var q := p + dir
			if model.is_solid(q) and seen[model.index_of(q)] == 0:
				seen[model.index_of(q)] = 1
				stack.append(q)
	for i in model.voxels.size():
		if seen[i] == 0:
			model.voxels[i] = 0

#endregion


func _bounds(lo: Vector3, hi: Vector3) -> Array[Vector3i]:
	var top := model.size - Vector3i.ONE
	return [Vector3i(lo.floor()).clamp(Vector3i.ZERO, top), Vector3i(hi.ceil()).clamp(Vector3i.ZERO, top)]
