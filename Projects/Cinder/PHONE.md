# Cinder on your phone: easy commands

Your phone's own AI keeps improving the Cinderdeep voxel models. You don't need Claude for it.

## Install (one time, about 10 minutes)

1. Install **Termux** from F-Droid, and **Termux:Widget** too if you want home-screen buttons.
2. Open Termux, paste this line, and press Enter:

   ```
   curl -fsSL https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/phone/install.sh | bash
   ```

3. When it shows a code, open the link, sign in to GitHub and type the code. That's the only question it asks.

To get the Claude command line as well, use this line instead:

```
curl -fsSL https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/phone/install.sh | bash -s -- --claude
```

## The commands

| Type this | What happens |
|---|---|
| `monster` | A brand new monster, designed and built for free on GitHub (see ODYSSEUS.md). |
| `monster a lava golem` | A new monster from your idea. |
| `push` | The AI improves the next model a little and saves it. |
| `push 5` | It does that 5 times in a row. |
| `ask make the hound glow more` | The AI makes the change you asked for. |
| `look` | Opens the newest pictures. They update about 5 minutes after a push. |
| `undo` | Takes back the last AI change. |
| `status` | Shows recent changes and how much phone memory is free. |
| `stop` | Turns the AI off and frees memory. Use it when you're done. |
| `menu` | Number buttons for everything above. |

**Home-screen buttons:** add the Termux:Widget widget, and you get **Cinder Push**, **Cinder Menu**, **Cinder Look**
and **Cinder Stop** to tap.

## Why it can't break anything

- **The AI only changes safe settings** for each model: size, glow, brightness, tint, colour strength, wear and
  variation. Each one has a safe limit.
- **Bad answers are thrown away**, and the game files themselves are never touched.
- **Every change can be taken back** with `undo`.
- **GitHub rebuilds the 3D models and pictures automatically** after each push (`.github/workflows/cinder-voxels.yml`).

## Memory

- **Normal AI:** `qwen2.5:1.5b`, about 1 GB.
- **Low memory:** when the phone has less than about 1.8 GB free, it switches to the tiny `qwen2.5:0.5b` by itself.
- **After each answer:** the AI unloads within 30 seconds, and `stop` turns it off completely.
