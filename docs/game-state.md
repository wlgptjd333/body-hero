# GameState Singleton Rules

`GameState` is the single source of truth for global gameplay state.

AutoLoad: `GameState` (`res://scripts/game_state.gd`)

---

## Responsibilities

GameState owns:

- player HP / stamina / guard state
- upgrade levels (sweat-based)
- persistent stats, records, stars
- achievements + progress
- shop inventory + equipment
- daily challenges + calorie tracking
- stage definitions + navigation
- difficulty settings
- display settings & window size

GameState delegates to internal modules:

- `game_state/webcam_bridge_internal.gd` — ML process lifecycle
- `game_state/workout_tracker.gd` — Calorie estimation and workout sessions
- `game_state/shop.gd` — Inventory and consumable logic
- `game_state/daily_challenges.gd` — Daily challenge progress and calendar sync
- `game_state/persistence.gd` — Save/load serialization

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
