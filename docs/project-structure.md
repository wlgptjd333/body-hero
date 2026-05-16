# Project Structure

## Core Folders

| Folder                  | Purpose                     |
| ----------------------- | --------------------------- |
| `scripts/`              | Global scripts and managers |
| `scripts/ui/`           | Shared UI helpers           |
| `games/boxing/scripts/` | Boxing gameplay logic       |
| `games/boxing/scenes/`  | Boxing scenes               |
| `scenes/`               | Main scenes                 |
| `scenes/ui/`            | UI scenes/panels            |
| `assets/`               | Fonts, textures, audio      |
| `tools/`                | Python ML + UDP tooling     |

---

## Important Scripts

### stage.gd

Location:

```txt
games/boxing/scripts/stage.gd
```

Unified stage scene controller (replaces former stage_1/2/3.gd).

Responsibilities:

* UDP receive
* gameplay initialization
* scene setup
* combat wiring

Parameterized by `StageConfig` resource per-stage.

---

### player.gd

Responsibilities:

* punch animation
* squat (HP regen) / guard
* tween logic
* keyboard input
* impact timing
* busy flags

---

### enemy.gd

Responsibilities:

* hit reaction
* HP management
* damage handling
* hit effects

---

### combat_director.gd

Responsibilities:

* combat flow
* combo resolution
* win/loss
* high-level combat rules

---

### game_state.gd

Global singleton.

Responsibilities:

* player HP / stamina / guard
* achievements, shop, persistence
* stage definitions, difficulty, display settings
* delegates webcam ML bridge to internal module

AutoLoad required. See `docs/game-state.md` for full rules.

---

### ui_theme_helper.gd

Global UI styling helper.

Responsibilities:

* button styles
* panel styles
* shared theme constants

AutoLoad required.

---

### AudioHelper

Audio loading utility.

Static method: `AudioHelper.try_load_stream(player, paths)`

AutoLoad required.

---

### HitImpactSystem

Camera shake, hitstop, flash overlay.

AutoLoad required.

---

## Architectural Philosophy

### Gameplay logic stays isolated

Avoid coupling:

* UI ↔ combat
* networking ↔ animation
* ML ↔ gameplay rules

---

### Prefer explicit ownership

Each system should have:

* one clear owner
* one responsibility

Avoid:

* duplicated logic
* shared mutable state
* hidden dependencies

---

## Refactor Policy

Prefer:

* incremental refactors
* isolated improvements
* surgical edits

Avoid:

* full rewrites
* speculative architecture
* unnecessary abstraction
