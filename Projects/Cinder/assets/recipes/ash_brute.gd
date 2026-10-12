extends RefCounted
## Ash Brute (Cinder Caldera – Ember Falls). A hulking, hunched figure that towers over ordinary ash ghouls,
## its back split open like cooling lava, with glowing fissures leaking amber light. The bulk of its body is a
## dense, cracked ash stone, dark grey with smoldering orange veins, while the cracked back glows white‑hot at
## the fissure tips. Its limbs are thick, blocky, and covered in a thin layer of soot‑black ash, and
## ember‑bright eyes flare from its shallow skull. Subtle ember particles drift off its shoulders, giving a
## faint, perpetual ember‑mist aura. It lumbers forward with heavy, staggered swings, using its cracked back to
## unleash bursts of lava‑spattered shockwaves on each hit.
## Made by Cinder AI. Faces +Z.

const SEED := 42


static func build(seed := SEED) -> VoxelModel:
	var b := VoxelBuilder.new(Vector3i(32, 56, 24), seed)
	var ash := b.ramp(CinderPalette.ASH)                                   # main body
	var lava := b.ramp(CinderPalette.LAVA, [0.35, 0.5, 0.7, 1.0, 1.4, 2.0]) # cracked back (emissive)
	var ember := b.ramp(CinderPalette.EMBER, [0.5, 0.8, 1.2, 1.6, 2.0, 2.5])# glowing accents
	var cx : float = 16.0
	var cz : float = 12.0

	# -------------------------------------------------------------------------
	# Paint callables – add organic noise to ash and lava surfaces.
	# -------------------------------------------------------------------------
	var ash_paint := b.noisy(ash, 0.5, 0.3, 0.1, 2.0)
	var lava_paint := b.noisy(lava, 0.6, 0.3, 0.12, 1.5)
	var ember_paint := b.noisy(ember, 0.7, 0.2, 0.05, 1.0)

	# -------------------------------------------------------------------------
	# 1. Core torso – large ash ellipsoid.
	# -------------------------------------------------------------------------
	b.ellipsoid(Vector3(cx, 20.0, cz), Vector3(8.0, 12.0, 6.0), ash_paint, 0.07)

	# -------------------------------------------------------------------------
	# 2. Cracked back fissure – lava‑colored ellipsoid, slightly raised.
	# -------------------------------------------------------------------------
	b.ellipsoid(Vector3(cx, 32.0, cz), Vector3(7.5, 4.0, 2.0), lava_paint, 0.08)

	# -------------------------------------------------------------------------
	# 3. Neck – tapered tube from torso to head.
	# -------------------------------------------------------------------------
	b.tube(Vector3(cx, 38.0, cz + 2.0), Vector3(cx, 44.0, cz + 4.0), 2.0, 3.0, ash_paint, 0.04)

	# -------------------------------------------------------------------------
	# 4. Head – ash ellipsoid with a shallow mouth.
	# -------------------------------------------------------------------------
	b.ellipsoid(Vector3(cx, 44.0, cz + 6.0), Vector3(5.0, 5.0, 5.0), ash_paint, 0.05)

	# -------------------------------------------------------------------------
	# 5. Ember eyes – bright ember spheres at the front of the skull.
	# -------------------------------------------------------------------------
	var eye_offset : float = 2.5
	for side: float in [-1.0, 1.0]:
		var eye_center := Vector3(cx + side * eye_offset, 46.0, cz + 10.0)
		b.ellipsoid(eye_center, Vector3(1.0, 1.0, 1.0), ember_paint, 0.0)

	# -------------------------------------------------------------------------
	# 6. Teeth – small ash boxes inside the mouth.
	# -------------------------------------------------------------------------
	var tooth_z : float = cz + 9.0
	for i in range(2):
		var tx : float = cx - 1.0 + i * 2.0
		var t_min := Vector3i(int(tx - 0.5), 42, int(tooth_z - 0.5))
		var t_max := Vector3i(int(tx + 0.5), 44, int(tooth_z + 0.5))
		b.box(t_min, t_max, ash_paint)

	# -------------------------------------------------------------------------
	# 7‑9. Right arm – upper arm, forearm, three claw spikes.
	# -------------------------------------------------------------------------
	# Upper arm
	b.tube(Vector3(cx + 9.0, 30.0, cz), Vector3(cx + 14.0, 38.0, cz), 2.0, 2.5, ash_paint, 0.03)
	# Forearm
	b.tube(Vector3(cx + 14.0, 38.0, cz), Vector3(cx + 18.0, 44.0, cz), 2.5, 2.0, ash_paint, 0.03)
	# Claws (three pointed tubes)
	for i in range(3):
		var angle : float = -0.2 + i * 0.2
		var dir := Vector3(1.0, 0.0, angle).normalized()
		var a := Vector3(cx + 18.0, 44.0, cz) + dir * 0.0
		var b_end := a + dir * 2.0
		b.tube(a, b_end, 0.5, 0.0, ember_paint, 0.0)

	# -------------------------------------------------------------------------
	# 10‑12. Left arm – mirrored via side loop (creates separate shape calls).
	# -------------------------------------------------------------------------
	for side: float in [-1.0, 1.0]:
		if side > 0.0:
			continue # right side already built
		# Upper arm
		b.tube(Vector3(cx + side * 9.0, 30.0, cz), Vector3(cx + side * 14.0, 38.0, cz), 2.0, 2.5, ash_paint, 0.03)
		# Forearm
		b.tube(Vector3(cx + side * 14.0, 38.0, cz), Vector3(cx + side * 18.0, 44.0, cz), 2.5, 2.0, ash_paint, 0.03)
		# Claws
		for i in range(3):
			var angle : float = -0.2 + i * 0.2
			var dir := Vector3(side, 0.0, angle).normalized()
			var a := Vector3(cx + side * 18.0, 44.0, cz) + dir * 0.0
			var b_end := a + dir * 2.0
			b.tube(a, b_end, 0.5, 0.0, ember_paint, 0.0)

	# -------------------------------------------------------------------------
	# 13‑15. Right leg – thigh, shin, foot.
	# -------------------------------------------------------------------------
	# Thigh
	b.tube(Vector3(cx + 5.0, 0.0, cz), Vector3(cx + 5.0, 20.0, cz), 3.0, 2.5, ash_paint, 0.04)
	# Shin
	b.tube(Vector3(cx + 5.0, 20.0, cz), Vector3(cx + 5.0, 38.0, cz), 2.5, 2.0, ash_paint, 0.04)
	# Foot (box)
	var foot_min := Vector3i(int(cx + 3.0), 0, int(cz - 4.0))
	var foot_max := Vector3i(int(cx + 7.0), 4, int(cz))
	b.box(foot_min, foot_max, ash_paint)

	# -------------------------------------------------------------------------
	# 16‑18. Left leg – mirrored via side loop.
	# -------------------------------------------------------------------------
	for side: float in [-1.0, 1.0]:
		if side > 0.0:
			continue # right side already built
		# Thigh
		b.tube(Vector3(cx + side * 5.0, 0.0, cz), Vector3(cx + side * 5.0, 20.0, cz), 3.0, 2.5, ash_paint, 0.04)
		# Shin
		b.tube(Vector3(cx + side * 5.0, 20.0, cz), Vector3(cx + side * 5.0, 38.0, cz), 2.5, 2.0, ash_paint, 0.04)
		# Foot
		var f_min := Vector3i(int(cx + side * 3.0), 0, int(cz - 4.0))
		var f_max := Vector3i(int(cx + side * 7.0), 4, int(cz))
		b.box(f_min, f_max, ash_paint)

	# -------------------------------------------------------------------------
	# 19. Shoulder plates – ash‑colored armour slabs.
	# -------------------------------------------------------------------------
	for side: float in [-1.0, 1.0]:
		var sp_min := Vector3i(int(cx + side * 12.0 - 2.0), 22, int(cz - 2.0))
		var sp_max := Vector3i(int(cx + side * 12.0 + 1.0), 28, int(cz + 1.0))
		b.box(sp_min, sp_max, ash_paint)

	# -------------------------------------------------------------------------
	# 20‑22. Back spikes – thin lava‑glowing tubes along the cracked back.
	# -------------------------------------------------------------------------
	for i in range(3):
		var y_base : float = 30.0 + i * 4.0
		var x_offset : float = -4.0 + i * 4.0
		var a := Vector3(cx + x_offset, y_base, cz)
		var b_end := Vector3(cx + x_offset, y_base + 6.0, cz)
		b.tube(a, b_end, 0.5, 0.0, ember_paint, 0.0)

	# -------------------------------------------------------------------------
	# 23. Back armor plate – a flat ash slab covering the fissure.
	# -------------------------------------------------------------------------
	var back_plate_min := Vector3i(int(cx - 7.0), 30, int(cz - 1))
	var back_plate_max := Vector3i(int(cx + 6.0), 38, int(cz + 1))
	b.box(back_plate_min, back_plate_max, ash_paint)

	# -------------------------------------------------------------------------
	# 24‑26. Ambient ember particles – scattered bright ember voxels.
	# -------------------------------------------------------------------------
	var particle_positions := [
		Vector3(-5, 48, -3), Vector3(6, 50, 2), Vector3(-6, 45, 4),
		Vector3(7, 47, -2), Vector3(0, 49, 0)
	]
	for off in particle_positions:
		var pos := Vector3i(int(cx + off.x), int(off.y), int(cz + off.z))
		b.set_v(pos, ember[5])   # brightest ember voxel

	# -------------------------------------------------------------------------
	# Shading – light from above, deeper shadows below.
	# -------------------------------------------------------------------------
	b.shade([ash], Vector3i.UP, 1)
	b.shade([ash], Vector3i.DOWN, -2)

	# -------------------------------------------------------------------------
	# Final model.
	# -------------------------------------------------------------------------
	return b.model
