extends RefCounted
## Sporefire Beetle (Sporeveil Marsh (Cinderdeep – Mycelium Basin)). A massive, armor‑plated beetle about three
## times a human’s height. Its hull is cracked obsidian basalt, streaked with bright orange ember veins that
## pulse like a heartbeat, and a large glowing ember core protrudes from its back. Two ragged ash‑filled
## wing‑membranes flare from its sides, faintly shimmering with ember sparks, while its six spindly legs end in
## charcoal‑black talons. It barrels forward, spitting ignited spore clouds that linger and burn, then retreats
## into its shell to recharge its ember core.
## Made by Cinder AI. Faces +Z.

const SEED := 42

static func build(seed := SEED) -> VoxelModel:
	var b := VoxelBuilder.new(Vector3i(32, 32, 16), seed)
	var basalt := b.ramp(CinderPalette.BASALT)               # dark carapace
	var char   := b.ramp(CinderPalette.CHAR)                 # cracked veins
	var ember  := b.ramp(CinderPalette.EMBER, [0.35, 0.5, 0.7, 1.0, 1.4, 2.0])
	var ash    := b.ramp(CinderPalette.ASH)
	var cx := 16.0

	# ── Paint lambdas ---------------------------------------------------------
	var basalt_paint := func(p: Vector3i) -> int:
		var t : float = (p.y - 2.0) / 28.0 + (b.n01(Vector3(p), 1.5) - 0.5) * 0.3
		return b.pick(basalt, clamp(t, 0.0, 1.0), 0.07)

	var char_paint := func(p: Vector3i) -> int:
		# Cracked char appears on exposed surfaces with a noisy pattern.
		if b.exposed(p, Vector3i.UP) and b.n01(Vector3(p), 2.2) > 0.55:
			var t : float = 0.5 + (b.n01(Vector3(p), 0.9) - 0.5) * 0.2
			return b.pick(char, clamp(t, 0.0, 1.0), 0.05)
		return basalt_paint.call(p)

	var ember_paint := func(p: Vector3i) -> int:
		return b.pick(ember, 0.6, 0.05)

	var ash_paint := func(p: Vector3i) -> int:
		var t : float = (p.y - 2.0) / 22.0 + (b.n01(Vector3(p), 1.8) - 0.5) * 0.25
		return b.pick(ash, clamp(t, 0.0, 1.0), 0.07)

	# ── 1️⃣ Core Carapace – massive basalt ellipsoid ---------------------------
	b.ellipsoid(Vector3(cx, 6.0, 8.0), Vector3(13, 6, 6), basalt_paint, 0.07)

	# ── 2️⃣ Ember Core – glowing sphere on the back ----------------------------
	b.ellipsoid(Vector3(cx, 8.0, 10.0), Vector3(3, 3, 3), ember_paint, 0.0)

	# ── 3️⃣ Head Capsule – forward dome ----------------------------------------
	b.ellipsoid(Vector3(cx, 12.0, 4.0), Vector3(4, 4, 3), basalt_paint, 0.05)

	# ── 4️⃣ Horns – forward‑pointing spikes ------------------------------------
	for side: float in [-1.0, 1.0]:
		var base := Vector3(cx + side * 2.0, 13.0, 4.0)
		var tip  := base + Vector3(0, 0, 6.0)
		b.tube(base, tip, 1.2, 0.3, basalt_paint, 0.02)

	# ── 5️⃣ Dorsal Ridge – subtle top ridge ------------------------------------
	for i in range(3):
		var y : float = 10.0 + i * 2.0
		var rad : float = 5.0 - i
		b.ellipsoid(Vector3(cx, y, 8.0), Vector3(rad, 1.5, rad), basalt_paint, 0.03)

	# ── 6️⃣ Back Plate – reinforced char slab over ember core ------------------
	b.box(Vector3i(4, 4, 12), Vector3i(27, 10, 13), char_paint)

	# ── 7️⃣ Spore Sac Pods – bulging char ellipsoids on each side -------------
	for side: float in [-1.0, 1.0]:
		var center := Vector3(cx + side * 10.0, 6.0, 8.0)
		b.ellipsoid(center, Vector3(3, 3, 4), char_paint, 0.04)

	# ── 8️⃣ Ignition Vents – tiny ember boxes inside each sac -----------------
	for side: float in [-1.0, 1.0]:
		var base := Vector3i(int(cx + side * 10.0 - 1), 6, 8)
		b.box(base, base + Vector3i(1, 0, 1), ember_paint)

	# ── 9️⃣ Left Wing Membrane – thin ash plane --------------------------------
	b.box(Vector3i(2, 4, 8), Vector3i(13, 4, 15), ash_paint)

	# ── 🔟 Wing Veins – ember‑glowing tubes across the left wing ---------------
	for side: float in [-1.0, 1.0]:
		var start := Vector3(cx + side * 6.0, 4.0, 9.0)
		var end   := Vector3(cx + side * 6.0, 4.0, 14.0)
		b.tube(start, end, 0.4, 0.2, ember_paint, 0.0)

	# ── 1️⃣1️⃣ Mirror left wing to right side -----------------------------------
	b.mirror_x()

	# ── 1️⃣2️⃣ Front Legs – three pairs (x = 8,16,24, z = 6) -------------------
	for x_off in [8, 16, 24]:
		var hip  := Vector3(x_off, 0.0, 6.0)
		var knee := hip + Vector3(0, 5.0, -1.0)
		var foot := knee + Vector3(0, -3.0, 0)
		b.tube(hip, knee, 1.6, 1.2, basalt_paint, 0.03)   # upper leg
		b.tube(knee, foot, 1.2, 0.8, basalt_paint, 0.03)   # lower leg
		# Talon – pointy spike downwards
		var tip := foot + Vector3(0, -1.5, 0)
		b.tube(foot, tip, 0.8, 0.0, basalt_paint, 0.0)
		# Knee armor plate
		b.box(Vector3i(x_off - 1, 5, 6), Vector3i(x_off + 1, 5, 6), char_paint)

	# ── 1️⃣3️⃣ Hind Legs – three pairs (x = 8,16,24, z = 12) ------------------
	for x_off in [8, 16, 24]:
		var hip  := Vector3(x_off, 0.0, 12.0)
		var knee := hip + Vector3(0, 5.0, -1.0)
		var foot := knee + Vector3(0, -3.0, 0)
		b.tube(hip, knee, 1.6, 1.2, basalt_paint, 0.03)
		b.tube(knee, foot, 1.2, 0.8, basalt_paint, 0.03)
		var tip := foot + Vector3(0, -1.5, 0)
		b.tube(foot, tip, 0.8, 0.0, basalt_paint, 0.0)
		b.box(Vector3i(x_off - 1, 5, 12), Vector3i(x_off + 1, 5, 12), char_paint)

	# ── 1️⃣4️⃣ Dorsal Spike Row – short spikes along the top edge -------------
	for i in range(5):
		var x_pos : float = 6.0 + i * 5.0
		var base := Vector3(x_pos, 12.0, 12.0)
		var tip  := base + Vector3(0, 2.0, 0)
		b.tube(base, tip, 0.6, 0.2, basalt_paint, 0.0)

	# ── 1️⃣5️⃣ Underside Hull – smooth basalt base for stability ---------------
	b.box(Vector3i(2, 0, 2), Vector3i(29, 1, 13), basalt_paint)

	# ── 1️⃣6️⃣ Glow Accents – ember clusters on carapace edges -----------------
	var glow_positions := [
		Vector3i(10, 2, 5),
		Vector3i(22, 2, 5),
		Vector3i(16, 2, 14),
		Vector3i(8, 4, 9),
		Vector3i(24, 4, 9)
	]
	for pos in glow_positions:
		b.ellipsoid(Vector3(pos), Vector3(1, 1, 1), ember_paint)

	# ── 1️⃣7️⃣ Ash Dust Detailing – thin ash layers on wing edges and joints ---
	# Wing edges (already have thin plane, add a rim)
	b.box(Vector3i(2, 4, 8), Vector3i(2, 4, 15), ash_paint)
	b.box(Vector3i(13, 4, 8), Vector3i(13, 4, 15), ash_paint)
	# Leg joint dust (knees)
	for x_off in [8, 16, 24]:
		b.box(Vector3i(x_off, 5, 6), Vector3i(x_off, 5, 6), ash_paint)
		b.box(Vector3i(x_off, 5, 12), Vector3i(x_off, 5, 12), ash_paint)

	# ── 1️⃣8️⃣ Ember Eyes – bright ember spots on the head front ----------------
	var eye_offset : float = 2.0
	b.ellipsoid(Vector3(cx - eye_offset, 12.0, 2.0), Vector3(0.8, 0.8, 0.8), ember_paint)
	b.ellipsoid(Vector3(cx + eye_offset, 12.0, 2.0), Vector3(0.8, 0.8, 0.8), ember_paint)

	# ── 1️⃣9️⃣ Ember Vein Recolor – replace exposed basalt on back with ember ----
	b.recolor(func(p: Vector3i, current: int) -> int:
		if p.z > 10 and b.exposed(p, Vector3i.UP):
			if b.n01(Vector3(p), 3.0) > 0.6:
				return b.pick(ember, 0.5, 0.1)
		return current)

	# ── 2️⃣0️⃣ Safety – remove any floating voxels (should be none) ------------
	b.remove_floating()

	# ── Shading – light from above, shadow below --------------------------------
	b.shade([basalt, char], Vector3i.UP, 1)
	b.shade([basalt, char], Vector3i.DOWN, -2)

	return b.model
