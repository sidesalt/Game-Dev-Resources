# Cinderdeep: 3D voxel remake, game design report

*Written 2026-10-12. This is a safety copy of the whole idea. It is also saved in GitHub at
`sidesalt/Game-Dev-Resources`, branch `ccr-031f1132-nxzsb1`, file `Projects/Cinder/docs/CINDERDEEP_GAME_DESIGN.md`.*

---

## 0. Quick answers

| Question | Answer |
|---|---|
| Where is the work happening? | **Not on your phone.** Claude works on a cloud computer. Every finished step is saved to your GitHub repo, and your phone only shows the progress. |
| 3D or 2.5D? | **Both.** The world and characters are real 3D voxel models. The camera looks down at an angle, like Diablo or Hades, so it plays like 2.5D and looks 3D. You can rotate and zoom it. |
| How far along is it? | The voxel tools work, and the first Cinder Caldera models are done: Cinder Hound, Ash Ghoul, Ash Revenant, Ember Wisp, Ash Vulture, ember crystals and the Cinder King's sword. The others are next: Cinder King, Pyroclast, Charred Treant, the hero and rocks. After them comes a small playable test area. |
| Is the "push" button in Odysseus done? | **Not yet.** Section 16 explains how it would work. I can build it as soon as you say yes. |

---

## 1. The vision in one paragraph

Cinderdeep is a dark-fantasy voxel world built on a living **mycelium network**. The network keeps pulling you back
from death, but only up to a point. You explore a huge, persistent open world of **13 biomes** while **hordes**
hunt you, and you fight through dungeons, craft, and survive. Each character has **one life** in the open world. If
you die in a dungeon, the mycelium drags you back to the surface. If you die in the open world, that character is
gone for good, and whatever killed you becomes a **Chaos Monster Lord** holding your banked **motes**. Your next
character has to hunt it down to get them back. The world remembers your decisions and changes because of them.
Later, you break through into the **multiverse**, where the game's whole art style changes.

---

## 2. Genre pillars (what kind of game it is)

1. **MMORPG.** There is one shared, persistent world, and other players' choices and deaths leave marks in it.
2. **Soulslike.** Combat is deliberate and punishing, built on stamina, timing, learning enemy patterns and
   recovering what you lost.
3. **Roguelite/roguelike.** Dungeons are made fresh for each run. One life per character, and some progress
   carries over between lives.
4. **Survival.** You manage hunger, warmth and heat, and each biome has its own hazards: ash storms, cold, spores.
5. **Crafting.** You gather from the voxel world and craft gear, camps, totems and beast gear.
6. **Dungeon crawler.** Dungeons are handmade or generated, with bosses. Dying in one is not permanent.
7. **Classic Mode.** The original 2D Cinderdeep stays on the title screen as its own mode, so nothing from the
   first game is lost.

---

## 3. Camera and look (3D vs 2.5D)

- **The models are real 3D.** Everything is built from small cubes: 32 per metre, so a person is about 56 cubes tall.
  - Lighting, shadows, glowing embers and fog all work.
  - The original pixel colours are kept. The palette was sampled straight from your sprites.
- **The camera feels 2.5D.**
  - The default is a tilted top-down view, about 50° down, following your character.
  - You can turn it in 45° steps and zoom in for boss fights.
  - This keeps the game readable when hordes swarm you, and it runs well on modest hardware.
- **Optional extras for later:**
  - A closer over-the-shoulder camera inside dungeons.
  - A pixel-art filter, which suits Classic Mode and the multiverse (section 11).

---

## 4. The world: a living mycelium network

- **The world is persistent.** It doesn't reset, and what happens stays happened.
- **The mycelium is the "save system" in the story.** It is why you come back from dungeon deaths, and its threads
  can be seen spreading across the land.
- **The world evolves with your decisions.** Examples:
  - Burn a forest, and it turns into Ashlands-style terrain over time.
  - Cleanse a fungal bloom, and the Sporeveil retreats.
  - Spare a boss, and it becomes a merchant or an enemy later.
  - Kill a faction leader, and that faction's patrols change.
- **The world is massive and full of content.** It has hand-placed landmarks, secret locations, random events,
  hidden DMT zones (section 6) and dungeon entrances.
