# Body Hero — Domain Language

> Webcam-based first-person boxing game. Godot 4.6 + GDScript.

## Domain Concepts

**Stage (스테이지)**
A boxing match scenario with a specific enemy (Bulgogi Burger, Cola Monster, Fries Monster). Each stage has its own enemy config, background, and BGM.

**Player (플레이어)**
The user's avatar. Has HP, stamina, left/right gloves. Performs actions: punch, uppercut, guard, squat (HP regen).

**Enemy (적)**
AI opponent. Has HP, attack patterns, evade patterns. Can be a boss with phase transitions.

**Enemy FSM (적 상태 기계)**
5개 상태: IDLE(decision), ATTACK(STARTUP→ACTIVE→RECOVERY), EVADE, HIT(interrupt), DEAD.
모든 전환은 `transition_to()` 단일 창구. IDLE만 행동 결정.

**AttackPhase (ATTACK sub-phase)**
ATTACK 상태 내부 3단계: STARTUP(telegraph) → ACTIVE(hit window, impact frame에서 `enemy_attack` emit) → RECOVERY(후딜).
타이머가 아닌 AnimatedSprite2D의 `frame_changed`/`animation_finished` 시그널로 구동. sprite 없을 시 timer fallback.

**Combat (전투)**
Resolution of player actions vs enemy state. Punch hits if enemy isn't evading. Damage is multiplied by combo.

**Guard (가드)**
Defensive stance. Reduces incoming damage. Has a minimum duration before release. 3초 초과 시 강제 해제(UDP 끊김 방어).

**Combo (콤보)**
Consecutive successful hits. Increases damage multiplier.

**Training (훈련장)**
Practice mode with infinite dummy respawn. No enemy attacks. Tracks action counts.

**HUD (헤드업 디스플레이)**
Game UI: HP/stamina bars, combo label, play time, training counters.

**Pause (일시정지)**
Overlay during gameplay. Resume, settings, quit options.

**Webcam ML Bridge (웹캠 ML 브릿지)**
Python process that captures webcam input and sends UDP packets (action strings or coordinate data).

**Boss Phase (보스 페이즈)**
HP threshold triggers phase transition. Player picks a buff before the phase starts.

**Demo Mode (시연 모드)**
설정 → 사용자 탭. 모든 데이터 초기화 + 스웨트 지급(기본 999). `GameState.enter_demo_mode(amount)`.

**Achievement Popup (업적 팝업)**
CanvasLayer + Panel + Label 조합. 우측 하단 고정, 3.5초 후 fade out. 여러 개 시 위로 쌓임. Signal notification only — state mutation 금지.

## Architecture Roles

**GameState** — Global singleton. Owns all persistent state: HP/stamina, stats, achievements, shop, webcam ML lifecycle, difficulty, stage definitions.

**Stage** — Root node of a boxing scene. Owns UDP server, child nodes (Player, Enemy, CombatDirector, UIDirector, StageManager).

**CombatDirector** — Combat resolution logic: hit/miss, combo, win/loss, training kill count. Signal-based communication.

**UIDirector** — HUD updates, overlay visibility (game over, win, KO intro, achievement popups). No game logic.

**StageManager** — Stage setup: background fitting, audio loading, viewport management.

**HitImpactSystem** — AutoLoad singleton. Screen shake, hitstop, camera flash.
