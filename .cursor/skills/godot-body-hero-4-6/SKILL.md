---
name: godot-body-hero-4-6
description: Godot 4.6.1 기반 Body Hero 복싱 게임에서 GDScript, 씬, UDP 연동을 수정하거나 확장할 때 프로젝트 구조와 ML 파이프라인을 안전하게 유지하도록 돕는 스킬. Godot 4.6, GDScript, main.tscn, GameState, UDP 웹캠/ML 연동 작업이 언급될 때 사용한다.
---

# Godot Body Hero 4.6

## 목적

이 스킬은 **Body Hero** 프로젝트에서 Godot 4.6.1과 GDScript를 다룰 때,

- 기존 **씬/스크립트 구조**를 존중하고,
- **전역 상태(GameState)**와 **UDP/ML 연동 규칙**을 지키며,
- Godot 4.x 스타일에 맞는 코드를 제안

하도록 돕는다.

사용자는 보통 다음과 같은 작업을 요청한다:

- 새로운 펀치/회피/가드 동작 추가
- 스태미너/HP/밸런스 조정
- UDP/웹캠/ML 액션을 게임 안 로직과 연결
- HUD/UI로 상태 표시

이 스킬은 이런 작업을 할 때 **프로젝트에 이미 있는 패턴을 재사용**하도록 유도해야 한다.

---

## 언제 이 스킬을 사용할 것인가

이 스킬은 다음과 같은 키워드/상황이 나오면 적극적으로 적용한다:

- 파일: `scripts/main.gd`, `scripts/player.gd`, `scripts/enemy.gd`, `scripts/game_state.gd`, `scenes/main.tscn`
- 키워드: "펀치", "스태미너", "UDP", "웹캠", "ML 판정", "GameState", "Input Map"
- 요청 유형:
  - 새 펀치/동작/회피/가드 추가
  - 스태미너/HP/HUD 게이지 조정
  - UDP/웹캠/ML 액션을 게임 로직에 연결
  - main 씬/플레이어/적 구조를 건드리는 변경

다른 일반 Godot 질문(예: 전혀 다른 프로젝트의 UI 튜토리얼)은 이 스킬이 아닌, 기본 Godot 4.6 문서와 일반 지식으로 처리한다.

---

## 공식 Godot 문서 연동

- 엔진 전반의 기능, 노드/씬 구조, GDScript 문법, 베스트 프랙티스에 대해서는 **Godot 4.6 공식 문서**를 1차 기준으로 삼는다.  
  - [Godot 4.6 공식 문서](https://docs.godotengine.org/en/stable/)
- 이 스킬은 위 문서의 내용을 **Body Hero 프로젝트 구조와 UDP/ML 파이프라인에 맞게 적용**하는 역할을 한다.

---

## 프로젝트 개요

- 엔진: **Godot 4.6.1**
- 장르: 웹캠 1인칭 헬스 복싱 게임
- 메인 씬: `scenes/main.tscn`
- 주요 스크립트:
  - `scripts/main.gd` — UDP 수신 + 글러브 위치 보정
  - `scripts/player.gd` — 펀치/가드/회피 Tween + 키보드 폴백
  - `scripts/enemy.gd` — 히트 판정, HP, 피격 연출
  - `scripts/game_state.gd` — 전역 HP/스태미너 상태 (AutoLoad `GameState`)
- Python/ML/테스트 도구: `tools/*.py`, `tools/README_ML.md`, `README.md`

---

## Godot 4.6 / GDScript 작성 원칙

1. **GDScript 2 문법 사용**
   - 타입 힌트: `var stamina: float = 100.0`
   - 함수 시그니처: `func _process(delta: float) -> void:`
2. **기존 코드 스타일 존중**
   - 변수/함수/상수 이름은 기존과 같은 영어 스네이크 케이스 유지.
   - 주석/설명은 한국어로 작성해도 된다.
3. **역할 분리**
   - 전역 상태: `GameState` 싱글톤 (`scripts/game_state.gd`)
   - 입력/애니메이션: `scripts/player.gd`
   - 적/피격 처리: `scripts/enemy.gd`
   - 네트워크/UDP: `scripts/main.gd` 및 `tools/*.py`

새 기능을 구현할 때는 **기존 역할에 맞는 파일에 코드를 추가**하는 방식을 우선으로 한다.

---

## .cursor/rules 와의 관계

이 프로젝트에는 `.cursor/rules/` 아래에 여러 규칙 파일이 있다:

- `core.mdc` — 항상 적용되는 GDScript/Godot 핵심 규칙 (타입 힌트, GameState 기본 원칙 등)
- `structure.mdc` — 씬/스크립트/도구 구조와 역할
- `input-udp.mdc` — InputMap, UDP 포맷, 액션 문자열/`play_action` 패턴
- `animation-hit.mdc` — Tween, `_busy`, 히트박스 on/off 패턴
- `gamestate.mdc` — GameState 전역 상태 관리 상세 규칙
- `ml-python.mdc` — ML/UDP Python 도구와 Godot 연동 규칙

이 스킬은 위 규칙들을 **요약 + 작업 흐름 중심으로 묶은 상위 가이드**이며, 규칙과 충돌하는 내용을 새로 만들지 않는다.

## GameState 활용 가이드

`scripts/game_state.gd`는 AutoLoad 싱글톤으로 등록되어 있으며, HP/스태미너 등 전역 수치를 담당한다.

- 스태미너 소모:
  - `GameState.consume_stamina(GameState.STAMINA_JAB)`
  - `GameState.consume_stamina(GameState.STAMINA_HOOK)`
- 비율 계산:
  - `GameState.get_stamina_ratio()`
  - `GameState.get_player_hp_ratio()`
**규칙**:

- HP/스태미너/피로도와 비슷한 개념을 추가할 때는, 가능하면 `GameState`에 새 필드를 추가하고 이를 통해 관리한다.
- 씬/노드 안에 전역과 중복되는 상태 변수를 새로 만들지 않는다.
- AutoLoad로 등록된 이름(`GameState`)을 그대로 사용한다.

---

## 플레이어 액션 및 애니메이션 패턴

`scripts/player.gd`는 Tween으로 펀치/가드/회피를 연출하고, 액션 이름을 기반으로 동작을 실행한다.

- 액션 엔트리 포인트: `play_action(action: String) -> void`
- 키보드 폴백: `_process`에서 `Input.is_action_just_pressed`로 테스트
- 주요 액션:
  - `"jab_l"`, `"jab_r"`
  - `"upper_l"`, `"upper_r"`
  - `"hook_l"`, `"hook_r"`
  - `"guard"`, `"guard_end"`
  - `"dodge_l"`, `"dodge_r"`

**패턴**:

1. 액션 이름에 따라 `GameState.consume_stamina(...)`로 스태미너를 먼저 확인한다.
2. `_busy` 플래그로 애니메이션 중 중복 입력을 막는다.
3. 전용 함수에서 Tween 생성:
   - `_play_jab`, `_play_uppercut`, `_play_hook`, `_play_guard_enter`, `_play_guard_exit`, `_play_dodge`
4. 글러브 히트박스 on/off:
   - `_set_glove_hit(glove, true/false)`에서 `collision_layer`를 토글한다.

**이 스킬이 할 일**:

- 새로운 동작을 추가할 때, 위 패턴을 그대로 따르는 코드를 제안한다.
- 이미 있는 `_play_*` 함수 패턴을 재사용하고, `_busy`, `_guarding` 등 상태 플래그를 일관되게 활용한다.

---

## 입력(InputMap) 및 테스트

README 기준 기본 키보드는 다음과 같다:

- `punch_left` — 기본 예시: `A`
- `punch_right` — 기본 예시: `D`
- 나머지 액션(`upper_left`, `upper_right`, `guard`, 회피 등)은 필요에 따라 InputMap에서 추가 가능.

코드를 수정하거나 예시를 제시할 때:

- InputMap 수정 경로를 명시한다:  
  `프로젝트 → 프로젝트 설정(Project Settings) → Input Map`
- 키보드 기반 테스트 로직은 가능하면 `scripts/player.gd`의 `_process` 안 패턴을 참고한다.

---

## UDP / ML 연동 규칙

이 프로젝트는 Python 스크립트(`tools/udp_send_webcam.py`, `udp_send_webcam_ml.py`, `udp_send_mouse.py` 등)를 통해 UDP로 데이터를 보내고, Godot에서 이를 받아 동작한다.

### 데이터 포맷

- 좌표 기반 모드:
  - `"left_x,left_y,right_x,right_y"` 형식 문자열
- 액션 기반 모드 (ML/threshold 공통):
  - `"jab_l"`, `"jab_r"`, `"upper_l"`, `"upper_r"`, `"hook_l"`, `"hook_r"`, `"guard"`, `"guard_end"`

**이 스킬은 GDScript 측에서 포맷을 바꾸지 않도록 해야 한다.**

- Godot 쪽 제안:
  - 주어진 문자열 포맷을 파싱해 `play_action(...)` 호출 또는 글러브 좌표 업데이트를 한다.
- 포맷 변경 또는 ML 모델 구조 변경 제안:
  - Python/ML 쪽 (`tools/README_ML.md`, `pose_server.py`, `udp_send_webcam_ml.py` 등)을 수정하는 방향을 안내한다.

---

## ML 파이프라인 요약 (참고용)

자세한 내용은 `tools/README_ML.md`를 따르면 되고, 이 스킬은 **Godot 코드에 영향을 주는 부분만 요약**한다.

- 포즈 데이터 수집: `collect_pose_data.py`
- 학습: `train_pose_classifier.py` → `pose_classifier.keras`
- 추론 서버: `pose_server.py` (Flask, `/predict`)
- Godot 연동: `udp_send_webcam_ml.py`가 액션 문자열을 UDP로 전송

Godot 입장에서는:

- UDP로 전달되는 액션 문자열만 잘 받으면 되므로,
- GDScript에서는 **새 모델/옵션을 의식하지 않고도 같은 인터페이스**를 유지하도록 설계한다.

---

## 작업별 체크리스트

### 1. 새 펀치/동작 추가하기

1. `GameState`에 필요하면 새 스태미너 상수 추가 (`STAMINA_*`).
2. `player.gd`의 `play_action`에 새 액션 분기 추가.
3. `_play_*` 계열 함수 패턴을 복사해 새 동작용 트윈/히트박스 로직을 구현.
4. InputMap에 새 액션 키를 추가(선택 사항).
5. UDP/ML 쪽에서 새 액션 문자열을 보낼지 여부를 검토하고, 필요시 `tools/*.py`에 반영하도록 안내.

### 2. 밸런스(스태미너/HP) 조정하기

1. `scripts/game_state.gd`에서 관련 상수/최대치만 조정한다.
2. 스태미너/HP를 중복 저장하지 않고, 기존 getter(`get_stamina_ratio`, `get_player_hp_ratio`)를 활용한다.
3. HUD/게이지를 수정할 때는 Godot 씬에서 노드 구조를 존중하며, 값은 `GameState`에서 읽는다.

### 3. UDP/웹캠 테스트/디버깅

1. Godot 게임 먼저 실행(F5).
2. `tools/udp_send_mouse.py` 또는 `udp_send_webcam.py`, `udp_send_webcam_ml.py` 실행.
3. 문제가 생기면:
   - 포트/호스트, 문자열 포맷이 README와 일치하는지 확인.
   - Godot `scripts/main.gd`의 수신 부분에서 로그를 찍어 디버깅(예: `print(udp_string)`).

---

## 예시: AI가 따라야 할 답변 스타일

- **Godot 코드 제안 시**:
  - GDScript 2 문법 사용.
  - `GameState`와 기존 `player.gd` 패턴을 재사용.
  - UDP 포맷을 바꾸지 않고, 주어진 문자열을 파싱해 `play_action`을 호출하는 방향으로 설계.
- **ML/데이터 관련 질문 시**:
  - 먼저 `tools/README_ML.md`의 워크플로를 요약 설명.
  - Python 버전, 가상환경, `requirements_ml.txt` 설치 여부를 체크리스트처럼 안내.
  - Godot 쪽 수정이 필요한지 여부를 명확히 구분해 말한다.

이 스킬을 사용할 때는 항상 **프로젝트에 이미 존재하는 패턴을 우선 관찰하고, 거기에 자연스럽게 이어 붙이는 형태**로 코드를 제안한다.
