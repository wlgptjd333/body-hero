# GameState Singleton Rules

`GameState` is the single source of truth for global gameplay state.

AutoLoad: `GameState` (`res://scripts/game_state.gd`)

---

## Responsibilities

GameState owns:

- player HP / stamina / guard state
- upgrade levels + sweat balance (via `_upgrade_system`)
- persistent stats, records, stars
- achievements + progress
- shop inventory + equipment
- daily challenges + calorie tracking
- stage definitions + navigation
- difficulty settings
- display settings & window size
- demo mode flag (`_demo_mode`, `enter_demo_mode(amount)`, `is_demo_mode()`)

GameState delegates to internal modules (see `scripts/game_state/`):

| Module | Responsibility |
|--------|---------------|
| `workout_tracker.gd` | Workout sessions, calorie estimation, body profile |
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
| `webcam_bridge_internal.gd` | Webcam ML bridge process management |

---

## Rules

### Never duplicate global state

No local copies of stamina, HP, etc. in unrelated scene scripts.

Always access through GameState:

```gdscript
# correct
GameState.consume_stamina(GameState.STAMINA_PUNCH)

# incorrect
var stamina = 100
```

### Adding new global state

1. Add field to GameState (or relevant internal module if separable)
2. Expose helper method if needed
3. Access through `GameState`

---

## Related

- `AudioHelper` — separate AutoLoad for audio loading utility
