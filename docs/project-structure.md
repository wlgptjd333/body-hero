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

* punch / uppercut animation (tween + AnimatedSprite2D)
* guard (3초 timeout 강제 해제, `GUARD_MIN_DURATION`/`GUARD_MAX_DURATION`)
* squat (HP regen)
* keyboard + UDP input handling
* busy flags (per-hand `_busy_left/right`, global `_busy_global`)

---

### enemy.gd

Responsibilities:

* **Enemy FSM**: 5 states (IDLE/ATTACK/EVADE/HIT/DEAD), `transition_to()` 단일 창구
* **Attack sub-phase**: STARTUP→ACTIVE→RECOVERY, animation frame-driven (`frame_changed` signal)
* hit reaction / VFX (CPUParticles2D multi-layer)
* damage handling / HP management
* training respawn (`reset_for_respawn`)

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
