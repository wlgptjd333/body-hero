# Body Hero — Agent Rules

Godot 4.6 + GDScript 2.0 webcam boxing game.

## Project Conventions

* In-game UI text should be in Korean

## Important Project Constraints

Never change:

* UDP protocol format
* Global GameState ownership rules

Always verify:

* Godot 4.6 API compatibility
* AutoLoad registration
* `extends` at file top
* Safe node reparenting order
* No direct `theme_override_*` assignments

## Reference Docs

Core references:

* CONTEXT.md

Design specs:

* docs/superpowers/specs/2026-05-15-enemy-fsm-design.md

Official documentation:

* <https://docs.godotengine.org/en/stable/>

Project reference docs:

* docs/game-state.md
* docs/godot-gotchas.md
* docs/udp-protocol.md
* docs/ui-rules.md
* docs/project-structure.md
* docs/scene-file-rules.md

## Testing

GUT (Godot Unit Test) addon is installed at `addons/gut/`.

* Tests live in `tests/unit/` and `tests/integration/`
* Test files must start with `test_` and use `extends GutTest`
* Run: Open Godot editor → Projects → Gut → Run all tests
* CLI: `godot -s addons/gut/gut_cmdln.gd -d --path .` (if godot available)
* Before fixing a bug: write a failing test first

## GameState Modules (scripts/game_state/)

GameState delegates to submodules via RefCounted scripts:

| Module | Responsibility |
|--------|---------------|
| `workout_tracker.gd` | Session tracking, calories, body profile |
| `shop.gd` | Shop items, purchases, equipment |
| `daily_challenges.gd` | Daily challenge rolling & progress |
| `persistence.gd` | Save/load to ConfigFile |
| `achievements.gd` | Achievement defs, unlock, progress |
| `difficulty.gd` | Difficulty get/set/label/multiplier |
| `stage_progress.gd` | Stars, records, clear times, stage defs |
| `boss_manager.gd` | Boss phase, buff selection, effects |
| `webcam_settings.gd` | Camera/display/window mode settings |
| `training.gd` | Training mode toggle |
| `upgrade_system.gd` | Sweat, HP/stamina/recover upgrades |
| `webcam_bridge_internal.gd` | Webcam ML bridge process mgmt |

GameState.gd keeps only: HP, stamina, guard, guard_mastery, signals, and thin delegation wrappers.
