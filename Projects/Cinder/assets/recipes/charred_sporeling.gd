extends RefCounted
## Charred Sporeling (Sporeveil Marsh (Cinderdeep – Mycelium Basin)). A low, hunched mound of cracked basalt
## and charred fungal husk, about two heads tall. Its back is riddled with ember‑glowing spore pods that pulse
## a sickly orange, while thin veins of blackened ash run across its sides. When it moves, a faint plume of
## ash‑colored spores drifts from its mouth and the gaps between its legs. It erupts a burst of explosive
## spores on contact, then darts away to regroup and repeat the pattern.
## Made by Cinder AI. Faces +Z.

const SEED := 42


static func build(seed := SEED) -> VoxelModel:
	var b := VoxelBuilder.new(Vector3i(28, 20, 28), seed)

	# --------------------------------------------------------------------
	# Ramps ---------------------------------------------------------------
	var ash    : PackedInt32Array = b.ramp(CinderPalette.ASH)
	var char   : PackedInt32Array = b.ramp(CinderPalette.CHAR)
	var ember  : PackedInt32Array = b.ramp(CinderPalette.EMBER, [0.35, 0.5, 0.7, 1.0, 1.4, 2.0])

	var cx : float = 14.0
	var cz : float = 14.0

	# --------------------------------------------------------------------
	# Paint lambdas --------------------------------------------------------
	var ash_paint := func(p: Vector3i) -> int:
		var t : float = (p.y / 20.0) + (b.n01(Vector3(p), 1.3) - 0.5) * 0.3
		return b.pick(ash, t, 0.08)

	var char_paint := func(p: Vector3i) -> int:
		var t : float = (p.y / 20.0) + (b.n01(Vector3(p), 1.6) - 0.5) * 0.35
		return b.pick(char, t, 0.07)

	var ember_paint := func(p: Vector3i) -> int:
		var t : float = 0.55 + (b.n01(Vector3(p), 2.0) - 0.5) * 0.25
		return b.pick(ember, t, 0.05)

	var carve := func(p: Vector3i) -> int:
		return 0   # delete voxel (used for cavities)

	# --------------------------------------------------------------------
	# 1️⃣ Torso – ash ellipsoid (20×12×20) ----------------------------------
	b.ellipsoid(
		Vector3(cx, 6.0, cz),               # centre
		Vector3(10.0, 6.0, 10.0),           # radii
		ash_paint,
		0.09)

	# 2️⃣ Back fungal mat – thin ash slab (16×2×16) -------------------------
	b.box(
		Vector3i(int(cx - 8), 4, int(cz - 8)),
		Vector3i(int(cx + 7), 5, int(cz + 7)),
		ash_paint)

	# 3️⃣ Head – ash ellipsoid (12×8×12) ------------------------------------
	b.ellipsoid(
		Vector3(cx, 13.0, cz),              # centre
		Vector3(6.0, 4.0, 6.0),             # radii
		ash_paint,
		0.07)

	# 4️⃣ Crown spikes – four ember tubes on top of head ------------------
	for side_x: float in [-1.0, 1.0]:
		for side_z: float in [-1.0, 1.0]:
			var base : Vector3 = Vector3(cx + side_x * 2.5, 17.0, cz + side_z * 2.5)
			var tip  : Vector3 = base + Vector3(side_x, 2.0, side_z).normalized() * 3.0
			b.tube(base, tip, 0.5, 0.0, ember_paint, 0.04)

	# 5️⃣ Spine ridge – char tube (2×10×2) ---------------------------------
	b.tube(
		Vector3(cx, 6.0, cz),               # base
		Vector3(cx, 12.0, cz),              # tip
		1.0, 1.0,                           # ra, rb
		char_paint,
		0.05)

	# 6️⃣ Ember spikes along ridge – char base, ember tip -----------------
	for i in 5:
		var y0 : float = 7.0 + i * 1.2
		var tip : Vector3 = Vector3(cx + (i % 2) * 2.0 - 1.0, y0 + 1.5, cz + 2.0)
		b.tube(
			Vector3(cx, y0, cz),
			tip,
			0.6, 0.0,
			ember_paint,
			0.03)

	# 7️⃣ Veins of ash – thin char columns on sides -----------------------
	for side: float in [-1.0, 1.0]:
		var col_x : float = cx + side * 6.0
		var radius_func := func(t: float) -> float:
			# slight bulge in the middle
			return 0.5 + 0.2 * b.n01(Vector3(t, 0, 0), 2.5)
		b.column(col_x, cz, 2, 10, radius_func, char_paint)

	# 8️⃣ Legs – char tapered tubes ----------------------------------------
	for side: float in [-1.0, 1.0]:
		var leg_x : float = cx + side * 6.0
		b.tube(
			Vector3(leg_x, 0.0, cz),        # foot
			Vector3(leg_x, 6.0, cz),        # hip
			2.0, 2.0,                       # constant radius (diameter 4)
			char_paint,
			0.04)

		# 8️⃣️⃣ Claws – three ember tubes per foot -------------------------
		for claw_idx: int in 3:
			var angle : float = deg_to_rad(30.0 * (claw_idx - 1))
			var dir   : Vector3 = Vector3(sin(angle), 0.3, cos(angle)).normalized()
			var foot  : Vector3 = Vector3(leg_x, 0.0, cz)
			var tip   : Vector3 = foot + dir * 3.0
			b.tube(foot, tip, 0.4, 0.0, ember_paint, 0.03)

	# 9️⃣ Spore pods – ember ellipsoids ------------------------------------
	var pod_centers : Array[Vector3] = [
		Vector3(cx - 4.0, 8.0, cz + 4.0),   # A
		Vector3(cx + 4.0, 8.0, cz + 4.0),   # B
		Vector3(cx, 10.0, cz - 4.0)        # C
	]
	for pc in pod_centers:
		var rad : float = 3.0 if pc.z > cz else 2.5
		b.ellipsoid(pc, Vector3(rad, rad, rad), ember_paint, 0.06)

		# 9️⃣️⃣ Vent protrusions – 2×2×2 ash boxes around each pod ----------
		for ox: float in [-1.0, 1.0]:
			for oy: float in [-1.0, 1.0]:
				for oz: float in [-1.0, 1.0]:
					var vp : Vector3 = pc + Vector3(ox, oy, oz)
					b.box(
						Vector3i(int(vp.x - 1), int(vp.y - 1), int(vp.z - 1)),
						Vector3i(int(vp.x), int(vp.y), int(vp.z)),
						ash_paint)

	# 🔟 Mouth cavity – carve a 4×2×4 box on front of head -----------------
	b.box(
		Vector3i(int(cx - 2), 12, int(cz + 6)),
		Vector3i(int(cx + 1), 13, int(cz + 9)),
		carve)

	# 1️⃣1️⃣ Ember rim around mouth – thin ember tube ----------------------
	b.tube(
		Vector3(cx - 2.5, 12.5, cz + 6.0),
		Vector3(cx + 2.5, 12.5, cz + 6.0),
		0.5, 0.5,
		ember_paint,
		0.02)

	# 1️⃣2️⃣ Teeth – four ember boxes inside mouth -------------------------
	for side: float in [-1.0, 1.0]:
		b.box(
			Vector3i(int(cx - 1 + side), 12, int(cz + 7)),
			Vector3i(int(cx + side), 13, int(cz + 8)),
			ember_paint)

	# 1️⃣3️⃣ Spore spray nozzle – ember block inside mouth -----------------
	b.box(
		Vector3i(int(cx - 1), 12, int(cz + 7)),
		Vector3i(int(cx), 13, int(cz + 8)),
		ember_paint)

	# 1️⃣4️⃣ Flare ember core – small ember ellipsoid inside spine ridge -----
	b.ellipsoid(
		Vector3(cx, 9.5, cz),               # centre
		Vector3(1.5, 1.5, 1.5),             # radii (3×3×3)
		ember_paint,
		0.05)

	# 1️⃣5️⃣ Back plates – ash boxes along spine ---------------------------
	for i in 3:
		var y0 : int = 7 + i * 3
		var y1 : int = y0 + 1
		b.box(
			Vector3i(int(cx - 2), y0, int(cz - 2)),
			Vector3i(int(cx + 1), y1, int(cz + 1)),
			ash_paint)

	# 1️⃣6️⃣ Ash dust particles – scattered 1×1×1 voxels -------------------
	for i in 30:
		var rx : int = int(cx - 9 + b.n01(Vector3(i * 3.1, i * 7.2, i * 11.3), 2.0) * 18)
		var ry : int = int(b.n01(Vector3(i * 5.5, i * 2.2, i * 9.9), 1.0) * 3)
		var rz : int = int(cz - 9 + b.n01(Vector3(i * 4.4, i * 6.6, i * 1.1), 2.0) * 18)
		b.set_v(Vector3i(rx, ry, rz), ash[0])

	# 1️⃣7️⃣ Surface cracks – random ember specks on exposed ash ---------
	b.recolor(func(p: Vector3i, current: int) -> int:
		if b.exposed(p, Vector3i.UP) and b.n01(Vector3(p), 3.5) < 0.07:
			# 15 % chance to replace exposed ash with ember crack
			if b.n01(Vector3(p), 1.0) < 0.15:
				return b.pick(ember, 0.6, 0.08)
		return current)

	# 1️⃣8️⃣ Glow on exposed ember parts – brighten ember on surfaces -------
	b.recolor(func(p: Vector3i, current: int) -> int:
		if b.on_surface(p) and current >= ember[0] and current <= ember[ember.size() - 1]:
			# push a step up the ember ramp for lit voxels
			var idx : int = current - ember[0]
			idx = clamp(idx + 1, 0, ember.size() - 1)
			return ember[idx]
		return current)

	# --------------------------------------------------------------------
	# Clean floating voxels ------------------------------------------------
	b.remove_floating()

	# --------------------------------------------------------------------
	# Shading ---------------------------------------------------------------
	b.shade([ash, char], Vector3i.UP, 1)
	b.shade([ash, char], Vector3i.DOWN, -2)

	return b.model
