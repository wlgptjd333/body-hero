# Body Hero 리팩토링 계획서

## 1. 현재 문제점

`main.gd`가 500+ 줄로 **UDP 수신 / 게임 흐름 / 콤보 / 훈련장 / HUD / 일시정지 / 씬 전환**을 모두 담당하고 있습니다.

- **버그 위험**: 한 파일이 너무 많은 책임을 가짐
- **테스트 불가**: UDP 수신과 게임 로직이 뒤섞여 단위 테스트 불가
- **확장 불가**: 새 스테이지, 새 적, 난이도 추가 시 main.gd에 계속 누적

---

## 2. 목표 아키텍처

```
Main (Node2D)
├── StageManager (Node)          ← NEW
│   └── Enemy (Node2D)           ← 기존 그대로 (동적 생성)
├── Player (Node2D)              ← 기존 그대로
├── CombatManager (Node)         ← NEW
├── GameFlow (Node)              ← NEW
├── HUD (CanvasLayer)            ← 기존 그대로
│   └── HUDController (Script)   ← NEW (HUD에 부착)
├── Background (Sprite2D)        ← 기존 그대로
├── BGM (AudioStreamPlayer)      ← 기존 그대로
├── PauseLayer (CanvasLayer)     ← 기존 그대로
├── GameOverLayer (CanvasLayer)  ← 기존 그대로
├── WinLayer (CanvasLayer)       ← 기존 그대로
└── KoIntroLayer (CanvasLayer)   ← 기존 그대로
```

---

## 3. 각 스크립트 역할 (미래 콘텐츠 대응 포함)

### `main.gd` — UDP Coordinator + Wiring

**책임:**
- UDP 서버 생명주기 (open / poll / close)
- 웹캠 ML 브리지 스케줄링
- UDP 수신 → `CombatManager`로 라우팅만 담당
- 씬 초기화 시 노드 간 시그널 연결 (StageManager ↔ CombatManager ↔ GameFlow 등)
- 씬 종료 시 정리 (UDP stop, 시그널 disconnect)

**미래 대응:**
- 새 입력 소스(게임패드, 모바일 터치) 추가 시 이 파일만 수정

---

### `stage_manager.gd` — Stage Controller

**책임:**
- 스테이지 설정 로드 (적 종류, 배경, BGM, 난이도 계수)
- 적 생성 / 파괴 / 리스폰
- 배경/BGM 설정
- 스테이지 타이머 (플레이 시간, 클리어 시간 기록)
- **데이터 기반**: `StageConfig` 리소스 또는 Dictionary로 스테이지 정의

**현재:**
- 1개 스테이지 (Burger)만 관리
- 트레이닝 모드일 때 더미 적 생성/리스폰

**미래 대응:**
- `stage_01_burger.tres`, `stage_02_ramen.tres` 등 데이터 파일만 추가
- Tower 모드: `get_unlocked_floors()`, `progress_floor()`
- 난이도: config에 `difficulty_modifiers` 추가 (적 HP 배율, 공격 속도 등)

```gdscript
# StageConfig 예시
class_name StageConfig
extends Resource
@export var enemy_scene: PackedScene
@export var background_texture: Texture2D
@export var bgm_stream: AudioStream
@export var enemy_hp_multiplier: float = 1.0
@export var enemy_attack_speed_multiplier: float = 1.0
@export var is_boss: bool = false
```

---

### `combat_manager.gd` — Combat System

**책임:**
- 플레이어 펀치 임팩트 수신 → 적 피격/회피 판정
- 적 공격 수신 → 플레이어 피해/가드 판정
- 콤보 시스템
- 훈련장 액션 카운트
- 승/패 조건 체크 (HP <= 0 → GameFlow에 notify)

**주요 시그널:**
```gdscript
signal combat_win(kill_count: int)           # training mode
signal combat_stage_clear(clear_sec: float)  # normal mode
signal combat_game_over
signal combo_changed(count: int)
signal training_action_logged(action: String)
```

**미래 대응:**
- 새 공격 동작 추가 → 여기서 hit/miss 판정 로직만 추가
- 콤보 시스템 확장 (콤보 게이지, 필살기) → 이 파일에서 처리
- 난이도 → StageConfig의 multiplier를 받아 데미지/HP 계산에 적용

---

### `game_flow.gd` — Flow Controller

**책임:**
- 일시정지 토글 / 일시정지 오버레이
- KO 연출 시퀀스
- GameOver / Win 오버레이 표시 (데이터는 CombatManager가, 표시는 이 파일이)
- 씬 전환 (재시작, 메뉴로)
- 일시정지 중 설정 패널 관리

**중요:** 게임 로직을 결정하지 않음. CombatManager가 "게임오버됐어"라고 알려주면 화멧에만 표시.

**미래 대응:**
- 컷씬 → `play_cutscene(cutscene_data)` 메서드 추가
- 새 게임 모드 (서바이벌, 타임어택) → 모드별 flow 분기

---

### `hud_controller.gd` — HUD Manager

**책임:**
- 모든 HUD 노드 참조 (@onready)
- ProgressBar 값 업데이트 (적 HP, 플레이어 HP, 스태미너)
- 플레이 시간 라벨
- 콤보 라벨
- 훈련장 라벨 (처치 횟수, 액션 카운트)
- GameOver/Win 화면의 칼로리/시간 라벨 텍스트 설정

**원칙:** 이 파일은 **결정**하지 않음. CombatManager/GameFlow가 "이 값으로 바꿔"라고 알려주면 화면에만 반영.

**미래 대응:**
- 스킨/의상 → `apply_cosmetic(skin_id)`로 HUD 색상/폰트 변경
- 새 게이지 (콤보 게이지, 보스 체크포인트) → 이 파일에 추가

---

### `game_state.gd` — Persistent State (기존 + 확장)

**현재:** HP, 스태미너, 업그레이드, 통계, 도전과제

**추가할 것:**
- `unlocked_floors: Array[int]` — 타워 등반 진행도
- `owned_skins: Array[String]` — 상점에서 구매한 스킨
- `equipped_skin: String` — 현재 장착 중인 스킨
- `owned_backgrounds: Array[String]` — 구매한 배경
- `equipped_background: String` — 현재 배경
- `total_coins: int` — 상점 재화 (스웨트와 별도)

**미래 대응:**
- 모든 저장 데이터의 중앙 집중화
- 상점, 진행도, 도전과제 모두 여기서 관리

---

## 4. 리팩토링 단계 (4단계로 나누어 안전하게 진행)

### Phase 1: HUDController 추출 (가장 안전)

**변경 파일:**
- `games/boxing/scenes/main.tscn` — HUD CanvasLayer에 `HUDController` 스크립트 부착
- `games/boxing/scripts/ui/hud_controller.gd` — NEW
- `games/boxing/scripts/main.gd` — HUD 관련 코드 제거

**이전 방법:**
1. `main.gd`의 모든 HUD @onready 참조와 HUD 업데이트 메서드를 복사
2. `hud_controller.gd`에 붙여넣기
3. `main.gd`에서 HUD 관련 코드 삭제
4. `main.gd`가 HUDController를 참조하고 메서드를 호출하도록 변경

**안전장치:** 기능 변경 없음. 단순 이동.

---

### Phase 2: GameFlow 추출

**변경 파일:**
- `games/boxing/scenes/main.tscn` — GameFlow 노드 추가
- `games/boxing/scripts/ui/game_flow.gd` — NEW
- `games/boxing/scripts/main.gd` — pause, overlay, scene transition 제거

**이전 방법:**
1. `main.gd`의 pause, game over, win, KO intro, 씬 전환 메서드를 복사
2. `game_flow.gd`에 붙여넣기
3. `main.gd`에서 해당 코드 삭제
4. 시그널로 연결: CombatManager → GameFlow (win/lose 신호)

**안전장치:** 기능 변경 없음.

---

### Phase 3: CombatManager 추출

**변경 파일:**
- `games/boxing/scenes/main.tscn` — CombatManager 노드 추가
- `games/boxing/scripts/combat_manager.gd` — NEW
- `games/boxing/scripts/main.gd` — combat, combo, training 관련 코드 제거

**이전 방법:**
1. `main.gd`의 _on_player_punch_impact, _on_enemy_attack, _on_enemy_died, combo 로직, training 로직을 복사
2. `combat_manager.gd`에 붙여넣기
3. `main.gd`에서 해당 코드 삭제
4. 시그널로 연결

**주의:** 이 단계에서 게임 로직의 흐름이 시그널 기반으로 바뀜. 테스트 필수.

---

### Phase 4: StageManager 추출

**변경 파일:**
- `games/boxing/scenes/main.tscn` — StageManager 노드 추가
- `games/boxing/scripts/stage_manager.gd` — NEW
- `games/boxing/scripts/main.gd` — enemy spawn, BGM, background 로직 제거

**미래를 위한 설계:**
- StageConfig 리소스를 도입하여 스테이지를 데이터로 정의
- `StageManager.load_stage(config: StageConfig)` 메서드 제공

---

## 5. 시그널 흐름 (리팩토링 후)

```
[UDP] → main.gd → combat_manager.gd
                                    ↓
[Player punch] → player.gd → punch_impact → combat_manager.gd
                                                        ↓
[Enemy hit/miss] → combat_manager.gd → enemy.take_damage() / attack_missed
                                                        ↓
[Enemy died] → enemy.gd → died → combat_manager.gd
                                          ↓ (if normal mode)
                              stage_manager.gd (record clear time)
                                          ↓
                              game_flow.gd (show win/KO)
                                          ↓
                              hud_controller.gd (update win labels)

[Enemy attack] → enemy.gd → enemy_attack → combat_manager.gd
                                          ↓
                              player.gd (guard fx / take damage fx)
                              game_state.gd (HP update)
                                          ↓ (if HP <= 0)
                              game_flow.gd (show game over)
```

---

## 6. 미래 콘텐츠와의 연결

| 미래 콘텐츠 | 담당 스크립트 | 방법 |
|-----------|-------------|------|
| **스토리 컷씬** | `game_flow.gd` | `play_cutscene()` 메서드 추가. 씬 위에 CutsceneOverlay CanvasLayer 추가 |
| **스테이지 추가** | `stage_manager.gd` | `StageConfig` 리소스 파일만 추가 |
| **타워 등반 (1F, 2F)** | `stage_manager.gd` + `game_state.gd` | `unlocked_floors`, `current_floor` 추가 |
| **여러 몬스터** | `stage_manager.gd` | `StageConfig.enemy_scene`을 다른 PackedScene으로 교체 |
| **상점 (스킨/옷/배경)** | `game_state.gd` + `hud_controller.gd` | `owned_skins`, `equipped_skin` 추가. HUD에 적용 함수 추가 |
| **최종보스** | `stage_manager.gd` + `enemy.gd` | `is_boss = true`인 StageConfig. Boss HP bar 추가 |
| **난이도** | `stage_manager.gd` + `combat_manager.gd` | `StageConfig`에 modifier 추가. CombatManager가 multiplier 적용 |
| **매일 접속 동기부여** | `game_state.gd` | 도전과제/연속출석/데일리 보상 확장 |

---

## 7. 리팩토링하지 말아야 할 것

- **`player.gd`**: 이미 역할이 명확함 (애니메이션/입력)
- **`enemy.gd`**: 이미 역할이 명확함 (AI/피격 연출)
- **씬 전환 경로**: 이미 `SCENE_MAIN`, `SCENE_MAIN_MENU` 등으로 상수화되어 있음
- **GameState 구조**: 이미 싱글톤으로 잘 설계됨

---

## 8. 결론

main.gd를 4개 파일로 나누되, **기능 변경 없이 순수 이동**을 원칙으로 합니다.

진행 순서:
1. Phase 1 (HUDController) — 가장 안전
2. Phase 2 (GameFlow) — UI 로직 이동
3. Phase 3 (CombatManager) — 게임 로직 이동
4. Phase 4 (StageManager) — 미래를 위한 설계

각 Phase마다 **커밋 + 테스트**를 거칩니다.

진행할까요?
