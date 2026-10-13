# Cinderdeep voxel asset guide (read by the Cinder AI)

This guide is sent to the AI with every `make` request. Edit it to teach the AI how to build better monsters.

## Art direction
- Dark ember-and-ash soulslike world. Bodies are soot, ash, char, bone, iron, basalt. Ember, flame and lava are
  the accents: eyes, cracks, mouths, cores, weapon edges. Glow covers at most 10% of the surface.
- Only palette colours exist. There is no blue, green or purple. "Glowing" always means EMBER, FLAME, LAVA, GOLD or
  CRYSTAL with emission.
- A strong silhouette comes first: it must read as one creature from far away. Exaggerate one feature (a huge jaw,
  long arms, a hunched back, antlers).

## Scale and orientation
- The hound (30 x 44 x 64) is a medium enemy. Small: about 24-40 per side. Large or boss: up to 96.
- Y is up and the monster stands on y = 0. It faces +Z, so the head, eyes and claws point towards high z. X is
  left/right: centre it at `cx = size.x / 2.0` and build pairs with `for side in [-1.0, 1.0]:`.
- Keep every part inside the grid. A part that runs past the edge gets cut off.

## Building forms (most important)
- Bodies, heads and muscles are **ellipsoids** (with wobble 0.05-0.15 for organic surfaces). Limbs, necks, tails,
  horns, spikes and claws are **tapered tubes** (`rb` smaller than `ra`, `rb = 0` gives a point). Overlap them so
  they read as one body.
- `box` is only for man-made or crystal things: armour plates, blades, bricks. Never for heads, bodies or legs.
- Work in three passes:
  1. Big masses: hips, ribcage and chest, head. That's 3-5 overlapping ellipsoids along the spine.
  2. Secondary forms: neck, jaw, legs (upper and lower tube with a bent knee), tail, wings, horns, armour.
  3. Details: claws (3 per foot), teeth, brow ridge, spikes along the spine, cracks, rivets, drips, nostrils.
- Joints bend: the knee point is not on the straight line from hip to foot. Arms hang forward or out.
- Eyes sit **on the surface** at the front of the head: put them at the head's front edge (centre z + radius z - 1),
  2-3 voxels apart. Make them the brightest voxels, with a darker voxel just behind.

## Lessons from the AI's first monsters (Ash Brute, 2026-10-12)
- Hands and feet grow out of the arm and leg tubes: a fist is an ellipsoid overlapping the end of the forearm, with
  tube fingers or claws. A box floating beside the arm reads as a brick.
- "Hunched" means the chest sits forward of the hips (chest centre z = hips z + 6 or more) and the head hangs low
  and forward. Shoulders are wider than the hips on brutes.
- The asked-for signature feature (lava cracks, a burning back) must be big and visible in the preview, which
  views the model from the front, 30° to its left and a little above. Put it on the top, front or sides, not only
  the back.
- Standing creatures touch the ground (feet, legs or belly at y = 0). Flying ones may hover, but every part must
  connect to the body: `b.remove_floating()` keeps what touches the lowest part and deletes loose pieces.
- Stray glowing specks floating above the head ruin the read. Finish with `b.remove_floating()` as the very
  last shape step (before shading), and keep eyes touching the head.

## Painting
- A shape's `paint` is ONE palette index or a lambda `func(p: Vector3i) -> int`. Never pass a whole ramp (the value
  from `b.ramp(...)`): use `b.pick(ramp, t, jitter)` inside a lambda, or `b.noisy(ramp, ...)`.
- Paint gradients, not flat colour: darker low and at the back, lighter on top. Use
  `t = (p.y - low) / height + (b.n01(Vector3(p), scale) - 0.5) * 0.5`, as the hound's `fur_paint` does.
- Use 2-4 ramps: one main body ramp, one secondary (bone, iron or char), and one glow ramp with rising emission such
  as `[0.35, 0.5, 0.7, 1.0, 1.4, 2.0]`.
- Finish with `b.shade([body ramps], Vector3i.UP, 1)` and `b.shade([body ramps], Vector3i.DOWN, -2)`, then a
  `b.recolor(...)` pass for glowing cracks, using noise on exposed voxels, as the hound's spine does.

## Common mistakes the checks reject
- Godot refuses `var x := cx + side * 3.0` when `side` comes from an untyped loop. Write
  `for side: float in [-1.0, 1.0]:` or give the type (`var x: float = ...`). Indent with tabs only.
- Passing a ramp as paint. Boxes for organic bodies. Eyes hidden inside the head. Parts floating in the air or past
  the grid. Fewer than about 18 shape calls. Calling anything outside VoxelBuilder, CinderPalette and vector maths.
