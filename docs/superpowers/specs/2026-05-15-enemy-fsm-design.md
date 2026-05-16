# Enemy FSM 리팩터링 — 설계 명세

## 목표

현재 boolean gate + parallel timer 기반 Enemy 행동 시스템을 예측 가능한 최소 FSM으로 전환.
"FSM purity"가 아닌 "transition predictability"가 핵심 기준.

## 제약

- Generic FSM framework 금지 — `enemy.gd` 내부 local FSM으로만 구현
- 기존 외부 contract 유지 — `take_damage()`, `is_evading()`, 시그널들
- StageConfig Resource serialization 안 깨기
- CombatDirector/Boss/Training 시스템 변경 최소화

## 상태 정의

```gdscript
enum EnemyState { IDLE, ATTACK, EVADE, HIT, DEAD }

# ATTACK 상태 내부 sub-phase (외부 비공개)
enum AttackPhase { STARTUP, ACTIVE, RECOVERY }
```

## 핵심 규칙

1. **IDLE만 decision state** — 타이머 누적 및 행동 선택은 IDLE에서만. ATTACK/EVADE/HIT 상태에서는 새로운 행동 결정 금지
2. **모든 전환은 `transition_to()` 단일 창구** — `_enter_state()` / `_exit_state()` 생명주기
3. **HIT는 최우선 인터럽트** — ATTACK/EVADE/IDLE 중 어느 상태에서도 진입 가능
4. **DEAD > HIT > 일반** — 사망 체크가 모든 상태 전환보다 우선
5. **Timer ownership centralized** — attack/evade idle timer는 IDLE 진입 시에만 리셋
6. **Nested/reentrant transitions 금지** — signal/tween/animation callback에서 `transition_to()` 직접 호출 금지. 필요한 경우 `call_deferred()` 사용
7. **`transition_to()` must stay lightweight** — side-effect는 `_enter_state()`에 위임. `transition_to()` 자체에 audio/VFX/gameplay 로직 추가 금지

## 상태 전환표

| 현재 상태 | 전환 조건 | 다음 상태 |
|-----------|----------|-----------|
| IDLE | attack idle timer 만료 | ATTACK |
| IDLE | evade idle timer 만료 | EVADE |
| IDLE | `take_damage()` | HIT |
| ATTACK | RECOVERY 완료 | IDLE |
| ATTACK | `take_damage()` (인터럽트) | HIT |
| EVADE | tween 완료 | IDLE |
| EVADE | `take_damage()` (인터럽트) | HIT |
| HIT | stagger timer 만료 | IDLE |
| HIT | `take_damage()` (재진입, stagger refresh) | HIT |
| * | HP ≤ 0 | DEAD |

## ATTACK Lifecycle

```
STARTUP (0.7s) → ACTIVE (0.08s) → RECOVERY (0.25~0.3s)
```

- STARTUP: telegraph, 애니메이션 재생, interrupt 가능
- ACTIVE: instant strike window, 지속 데미지 상태 아님. 진입 시 `emit_signal("enemy_attack")` 한 번만
- RECOVERY: 후딜, 취약 시간, 난이도에 따라 길이 조절. Combat rhythm과 punish window 유지가 목적 — 단순 지연이 아님
- Sub-phase는 `EnemyState.ATTACK` 내부 implementation detail, 외부 노출 금지

## HIT 처리

- `take_damage()`는 HP만 변경하고 `transition_to(HIT)` 요청
- cleanup은 `_exit_state()`에 위임 — `_cancel_attack()` 별도 호출 금지
- HIT 재진입 시 stagger timer refresh (연속타 콤보)
- Signal(`hit_received`)은 notification only — VFX/HUD/sound. Signal 핸들러에서 `transition_to()` 직접 호출 금지 (hidden transition source 방지)

## 난이도 연동

```gdscript
EASY:   recovery_mult = 1.5  # 긴 후딜
NORMAL: recovery_mult = 1.0
HARD:   recovery_mult = 0.7  # 짧은 후딜
clamp(recovery_mult, 0.5, 2.0)
```

`StageConfig`에 `enemy_recovery_mult` 옵션 필드 추가 (없으면 1.0 fallback). 기존 StageConfig Resource의 serialization을 건드리지 말 것.

## 인터페이스 (변경 없음)

- `func take_damage(damage: float)` — 시그니처 동일
- `func is_evading() -> bool` — 내부 구현만 변경
- 시그널: `hit_received`, `died`, `enemy_attack`, `phase_changed`
- `ai_enabled` / `reset_for_respawn()` — Training 모드 유지

## DEBUG_FSM

```gdscript
const DEBUG_FSM := true
func transition_to(next, reason := "") -> void:
    print("[FSM] %s -> %s (%s)" % [current, next, reason])
```

추가로:
- 중복 전환 경고 (`if next == _current_state: push_warning(...)`)
- `_state_enter_time` 기록 (tuning/debugging 용)
- Production build에서는 쉽게 비활성화 가능해야 함 (단일 const 변경)

## 파일 구조 예상

`enemy.gd`: 764줄 → ~550줄
- Enums → State 변수 → Timers → Lifecycle → Transition → IDLE → ATTACK → EVADE → HIT → DEAD → Difficulty → External API

제거: `_is_attacking`, `_is_evading`, `_is_dead`, `_hit_anim_ticket`, `_update_attack_pattern()`, `_update_evade_pattern()`

## 구현 순서 (권장)

1. `transition_to()` + `EnemyState` enum + `_process` dispatch 도입 (기존 코드 coexist)
2. IDLE / ATTACK / EVADE 순차 전환 (병렬 타이머 제거)
3. ATTACK sub-phase (STARTUP/ACTIVE/RECOVERY) 분리
4. HIT를 ticket → state lifecycle으로 전환
5. 기존 boolean flags 제거 및 cleanup 정리
6. DEBUG_FSM + 전체 재생 테스트

각 단계마다 Godot 실행 → 1-2분 플레이 테스트 → commit.
