# Enemy FSM 리팩터링 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace boolean-gate + parallel-timer enemy behavior with a minimal, predictable FSM (5 states, centralized transitions).

**Architecture:** Single-file local FSM inside `enemy.gd`. `EnemyState` enum replaces boolean flags. `transition_to()` is the sole transition authority. `_enter_state()` / `_exit_state()` lifecycle. ATTACK has internal STARTUP/ACTIVE/RECOVERY sub-phases. External contract (`take_damage()`, `is_evading()`, signals) unchanged.

**Tech Stack:** Godot 4.6 + GDScript 2.0, no frameworks, no plugins.

**참조:** `docs/superpowers/specs/2026-05-15-enemy-fsm-design.md`

---

### Task 1: `transition_to()` + `EnemyState` enum + `_process` dispatch

**Modify:** `games/boxing/scripts/enemy.gd`

Goal: Establish FSM infrastructure while old booleans still work. No behavioral change yet.

- [ ] **Step 1: Add enum and state variable**

```gdscript
# 상단에 추가
enum EnemyState { IDLE, ATTACK, EVADE, HIT, DEAD }

# 기존 booleans 근처에 추가
var _current_state: int = EnemyState.IDLE
var _state_enter_time: int = 0
```

- [ ] **Step 2: Add `transition_to()`**

```gdscript
const DEBUG_FSM := true

func transition_to(next: int, reason := "") -> void:
    if next == _current_state:
        if DEBUG_FSM:
            push_warning("transition_to(%s) but already in %s" % [EnemyState.keys()[next], EnemyState.keys()[_current_state]])
        return
    if DEBUG_FSM:
        print("[FSM] %s -> %s (%s)" % [EnemyState.keys()[_current_state], EnemyState.keys()[next], reason])
    _exit_state(_current_state)
    _current_state = next
    _state_enter_time = Time.get_ticks_msec()
    _enter_state(_current_state)

func _enter_state(state: int) -> void:
    pass  # 각 Task에서 채움

func _exit_state(state: int) -> void:
    pass  # 각 Task에서 채움
```

- [ ] **Step 3: Add `_process` dispatch alongside existing logic**

```gdscript
# _process(delta): 기존 _update_attack_pattern / _update_evade_pattern 호출 유지
# FSM update를 병렬로 추가 (아직 전환 안 함, coexistence)

func _process(delta: float) -> void:
    if _is_dead:
        return
    if not ai_enabled:
        return

    # FSM update (새로 추가 — 아직 기존 코드 coexist)
    _update_fsm(delta)

    # 기존 로직 유지 (아직 제거 안 함)
    _update_attack_pattern(delta)
    _update_evade_pattern(delta)

func _update_fsm(delta: float) -> void:
    pass  # Task 2에서 채움
```

- [ ] **Step 4: Git commit**

```bash
git add games/boxing/scripts/enemy.gd
git commit -m "refactor: add EnemyState enum and transition_to() infrastructure"
```

---

### Task 2: IDLE dispatch + timer ownership 전환

**Modify:** `games/boxing/scripts/enemy.gd`

Goal: IDLE becomes sole decision state. Timer accumulation moves into IDLE. Coexist with old system — test each change.

- [ ] **Step 1: Convert IDLE update**

```gdscript
func _update_fsm(delta: float) -> void:
    match _current_state:
        EnemyState.IDLE:
            _update_idle(delta)

func _update_idle(delta: float) -> void:
    _attack_idle_timer -= delta
    _evade_idle_timer -= delta

    if _attack_idle_timer <= 0.0:
        transition_to(EnemyState.ATTACK, "attack timer expired")
        return
    if _evade_idle_timer <= 0.0:
        transition_to(EnemyState.EVADE, "evade timer expired")
        return
```

- [ ] **Step 2: Add `_reset_timers()`**

```gdscript
func _reset_timers() -> void:
    _attack_idle_timer = randf_range(
        attack_delay_min * _difficulty_mult,
        attack_delay_max * _difficulty_mult
    )
    _evade_idle_timer = randf_range(
        evade_idle_min * _difficulty_mult,
        evade_idle_max * _difficulty_mult
    )
```

- [ ] **Step 3: Wire IDLE enter**

```gdscript
func _enter_state(state: int) -> void:
    match state:
        EnemyState.IDLE:
            _reset_timers()
```

- [ ] **Step 4: Playtest** — Open Godot, run a stage, observe that idle timer transitions work. Old attack/evade still runs via `_update_attack_pattern` / `_update_evade_pattern` — that's fine for now.

- [ ] **Step 5: Git commit**

```bash
git add games/boxing/scripts/enemy.gd
git commit -m "refactor: IDLE as sole decision state with timer ownership"
```

---

### Task 3: EVADE + ATTACK dispatch 전환

**Modify:** `games/boxing/scripts/enemy.gd`

Goal: EVADE and ATTACK states handle their own lifecycle. Old parallel loops still running — this is transitional.

- [ ] **Step 1: Add EVADE enter/exit**

```gdscript
func _enter_state(state: int) -> void:
    match state:
        EnemyState.IDLE:
            _reset_timers()
        EnemyState.EVADE:
            _start_evade_tween()

func _exit_state(state: int) -> void:
    match state:
        EnemyState.EVADE:
            if is_instance_valid(_evade_tween):
                _evade_tween.kill()
```

- [ ] **Step 2: Add EVADE update**

```gdscript
func _update_fsm(delta: float) -> void:
    match _current_state:
        EnemyState.IDLE:
            _update_idle(delta)
        EnemyState.EVADE:
            _update_evade(delta)

func _update_evade(delta: float) -> void:
    pass  # tween handles movement
```

- [ ] **Step 3: Wire evade tween completion to transition**

```gdscript
# _start_evade_tween() 내부:
_evade_tween.finished.connect(_on_evade_finished.bind(), CONNECT_ONE_SHOT)

func _on_evade_finished() -> void:
    transition_to(EnemyState.IDLE, "evade complete")
```

- [ ] **Step 4: Add ATTACK enter**

```gdscript
enum AttackPhase { STARTUP, ACTIVE, RECOVERY }
var _attack_phase: int = AttackPhase.STARTUP
var _attack_phase_timer: float = 0.0

func _enter_state(state: int) -> void:
    match state:
        EnemyState.ATTACK:
            _attack_phase = AttackPhase.STARTUP
            _attack_phase_timer = attack_telegraph_duration
            _play_attack_animation()
```

- [ ] **Step 5: Add ATTACK update (simple version, all phases timer-driven)**

```gdscript
func _update_fsm(delta: float) -> void:
    match _current_state:
        EnemyState.IDLE:
            _update_idle(delta)
        EnemyState.ATTACK:
            _update_attack(delta)
        EnemyState.EVADE:
            _update_evade(delta)

func _update_attack(delta: float) -> void:
    _attack_phase_timer -= delta
    match _attack_phase:
        AttackPhase.STARTUP:
            if _attack_phase_timer <= 0.0:
                _attack_phase = AttackPhase.ACTIVE
                _attack_phase_timer = attack_active_duration
                _emit_impact()
        AttackPhase.ACTIVE:
            if _attack_phase_timer <= 0.0:
                _attack_phase = AttackPhase.RECOVERY
                _attack_phase_timer = attack_recovery_duration
        AttackPhase.RECOVERY:
            if _attack_phase_timer <= 0.0:
                transition_to(EnemyState.IDLE, "attack complete")
```

- [ ] **Step 6: Add ATTACK exit cleanup**

```gdscript
func _exit_state(state: int) -> void:
    match state:
        EnemyState.ATTACK:
            _stop_attack_animation()
        EnemyState.EVADE:
            if is_instance_valid(_evade_tween):
                _evade_tween.kill()
```

- [ ] **Step 7: Playtest** — Godot에서 stage 실행. FSM이 attack/evade를 처리하는지 확인. 기존 `_update_attack_pattern`/`_update_evade_pattern`이 아직 살아있어 중복 실행될 수 있음 — 다음 Task에서 제거.

- [ ] **Step 8: Git commit**

```bash
git add games/boxing/scripts/enemy.gd
git commit -m "refactor: EVADE and ATTACK states with phase lifecycle"
```

---

### Task 4: HIT를 상태로 전환 + `take_damage()` 정리

**Modify:** `games/boxing/scripts/enemy.gd`
**Modify:** `games/boxing/scripts/combat_director.gd` (최소)

Goal: HIT becomes a proper interrupt state. Remove ticket system. Cleanup ownership in `_exit_state()`.

- [ ] **Step 1: Add HIT enter/update/exit**

```gdscript
func _enter_state(state: int) -> void:
    match state:
        EnemyState.HIT:
            _hit_timer = hit_stagger_duration
            _play_hit_animation()
            _flash_hit()
            emit_signal("hit_received")

func _update_fsm(delta: float) -> void:
    match _current_state:
        EnemyState.HIT:
            _update_hit(delta)

func _update_hit(delta: float) -> void:
    _hit_timer -= delta
    if _hit_timer <= 0.0:
        transition_to(EnemyState.IDLE, "stagger end")
```

- [ ] **Step 2: Rewrite `take_damage()`**

```gdscript
func take_damage(damage: float) -> void:
    hp -= damage

    if hp <= 0.0:
        if _current_state != EnemyState.DEAD:
            transition_to(EnemyState.DEAD, "hp <= 0")
        return

    if _current_state == EnemyState.HIT:
        _hit_timer = hit_stagger_duration  # combo — stagger refresh
        return

    transition_to(EnemyState.HIT, "take_damage")
```

- [ ] **Step 3: Remove ticket system**

기존 변수 `_hit_anim_ticket`, `_hit_ticket_counter` 제거.
`_on_hit_anim_finished()` 콜백 정리 — HIT 상태에서는 `_update_hit`의 timer가 stagger 종료 관리.

- [ ] **Step 4: Update CombatDirector (is_evading)**

```gdscript
# enemy.gd에 추가
func is_evading() -> bool:
    return _current_state == EnemyState.EVADE

# combat_director.gd — 변경 없음 (is_evading() contract 유지)
```

- [ ] **Step 5: Playtest** — Godot에서 hit 반응, 콤보 타이밍, stagger 정상 작동 확인.

- [ ] **Step 6: Git commit**

```bash
git add games/boxing/scripts/enemy.gd
git commit -m "refactor: convert HIT to FSM state, remove ticket system"
```

---

### Task 5: 기존 boolean flags + 병렬 루프 제거

**Modify:** `games/boxing/scripts/enemy.gd`

Goal: Remove deprecated code after FSM is verified working.

- [ ] **Step 1: Remove `_is_attacking`, `_is_evading`, `_is_dead`**

Search entire file for these variables. Replace `_is_dead` checks with `_current_state == EnemyState.DEAD`.

- [ ] **Step 2: Remove `_update_attack_pattern(delta)` and `_update_evade_pattern(delta)`**

Delete both functions entirely. Remove their calls from `_process()`.

```gdscript
func _process(delta: float) -> void:
    if _current_state == EnemyState.DEAD:
        return
    if not ai_enabled:
        return
    _update_fsm(delta)
```

- [ ] **Step 3: Remove `_hit_anim_ticket` / `_hit_ticket_counter` (if not already removed)**

- [ ] **Step 4: Playtest** — 전체 플로우 테스트: idle → attack → hit → evade → dead. Boss phase 전환. Training mode.

- [ ] **Step 5: Git commit**

```bash
git add games/boxing/scripts/enemy.gd
git commit -m "refactor: remove deprecated boolean flags and parallel loops"
```

---

### Task 6: StageConfig + 난이도 연동

**Modify:** `games/boxing/scripts/stage_config.gd`
**Modify:** `games/boxing/scripts/enemy.gd`

- [ ] **Step 1: Add `enemy_recovery_mult` to StageConfig**

```gdscript
# games/boxing/scripts/stage_config.gd
@export var enemy_recovery_mult: float = 1.0
```

- [ ] **Step 2: Wire recovery_mult in enemy.gd**

```gdscript
func _apply_difficulty_stats(difficulty: String) -> void:
    var recovery_mult := 1.0
    match difficulty:
        "EASY":
            recovery_mult = 1.5
        "HARD":
            recovery_mult = 0.7

    recovery_mult *= _stage_config.enemy_recovery_mult if _stage_config.enemy_recovery_mult > 0 else 1.0
    recovery_mult = clamp(recovery_mult, 0.5, 2.0)

    attack_recovery_duration = base_attack_recovery_duration * recovery_mult
```

- [ ] **Step 3: Git commit**

```bash
git add games/boxing/scripts/stage_config.gd games/boxing/scripts/enemy.gd
git commit -m "feat: add enemy_recovery_mult to stage config, wire difficulty scaling"
```

---

### Task 7: DEBUG_FSM 강화 + final polish

**Modify:** `games/boxing/scripts/enemy.gd`
**Modify:** `docs/AGENTS.md`

- [ ] **Step 1: Add state duration logging on transition**

```gdscript
func transition_to(next: int, reason := "") -> void:
    if DEBUG_FSM and _state_enter_time > 0:
        var duration = Time.get_ticks_msec() - _state_enter_time
        print("[FSM] %s lasted %dms" % [EnemyState.keys()[_current_state], duration])
    # ... rest of transition_to ...
```

- [ ] **Step 2: Add AGENTS.md reference**

```
Enemy FSM spec: docs/superpowers/specs/2026-05-15-enemy-fsm-design.md
```

- [ ] **Step 3: Final playtest** — 모든 스테이지(1/2/3), Training, Boss, EASY/NORMAL/HARD 각각 1분 이상 플레이.

- [ ] **Step 4: Git commit**

```bash
git add games/boxing/scripts/enemy.gd docs/AGENTS.md
git commit -m "refactor: final FSM polish, DEBUG_FSM logging, AGENTS.md reference"
```

---

## Spec Coverage Check

| Spec 요구사항 | Task |
|--------------|------|
| EnemyState enum (5 states) | Task 1 |
| `transition_to()` 단일 창구 | Task 1 |
| `_enter_state()` / `_exit_state()` lifecycle | Task 1 (+ 각 Task에서 채움) |
| IDLE만 decision state | Task 2 |
| Timer ownership centralized | Task 2 |
| ATTACK STARTUP/ACTIVE/RECOVERY sub-phase | Task 3 |
| EVADE tween-based, 단순 유지 | Task 3 |
| HIT 최우선 인터럽트 + stagger | Task 4 |
| `take_damage()` 단순화 | Task 4 |
| ticket 시스템 제거 | Task 4, 5 |
| boolean flags 제거 | Task 5 |
| `is_evading()` contract 유지 | Task 4 |
| CombatDirector 최소 변경 | Task 4 |
| StageConfig `enemy_recovery_mult` | Task 6 |
| Difficulty recovery scaling | Task 6 |
| DEBUG_FSM logging | Task 1, 7 |
| Nested transition 금지 | Task 1 (`push_warning`) |
| Production에서 DEBUG_FSM 비활성화 가능 | Task 1 (`const DEBUG_FSM`) |
