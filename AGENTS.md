# Body Hero — Agent 개발 가이드

> Godot 4.6 + GDScript 2.0. 웹캠 기반 1인칭 복싱 게임.
> **목적: 앞으로 버그가 최대한 일어나지 않게 한다.**

---

## 1. 버그 방지용 절대 규칙

### 1.1 모든 스크립트는 `extends`로 시작
파일 최상단에 `extends Node` 또는 `extends Control` 등이 있어야 함. 없으면 **런타임 Parser Error**.

### 1.2 AutoLoad 등록 필수
`project.godot` → `[autoload]` 섹션에 등록된 파일만 전역 이름으로 접근 가능.  
등록 없이 `SomeName.func()` 호출 → **`Identifier not found` 런타임 에러**.

### 1.3 `theme_override_*` 프로퍼티 직접 대입 금지
- ❌ `node.theme_override_constants.separation = 6`
- ✅ `node.add_theme_constant_override("separation", 6)`
- ❌ `node.theme_override_font_sizes.font_size = 14`
- ✅ `node.add_theme_font_size_override("font_size", 14)`

### 1.4 enum/상수는 Godot 4.6 API 문서 기준
- Godot 4.6 공식 문서: https://docs.godotengine.org/en/stable/
- **CenterContainer가 자동 중앙정렬하므로**, VBoxContainer/HBoxContainer의 `alignment` 설정은 불필요
- deprecated 패턴(`BoxContainer.ALIGNMENT_CENTER` 등) 사용 금지

### 1.5 노드 reparenting 순서
```gdscript
# 반드시 이 순서
parent.remove_child(node)
new_parent.add_child(node)
```

### 1.6 `class_name` vs AutoLoad
- `class_name`만으로는 **싱글톤이 아님**
- 전역 헬퍼/매니저는 반드시 **`extends Node` + `project.godot` `[autoload]` 등록**

### 1.7 타입 힌트
- 변수/함수 모두 타입 명시: `var stamina: float = 100.0`, `func _process(delta: float) -> void:`
- 이름: 변수/함수 = `snake_case`, 상수 = `UPPER_SNAKE_CASE`

---

## 2. 프로젝트 구조

| 폴 | 내용 |
|------|------|
| `scripts/` | 전역 스크립트 (GameState, 메인메뉴, 홈허브 등) |
| `scripts/ui/` | UI 헬퍼/패널 스크립트 |
| `games/boxing/scripts/` | 복싱 게임 로직 |
| `games/boxing/scenes/` | 복싱 게임 씬 |
| `scenes/` | 메인 씬 (홈허브, 메인메뉴 등) |
| `scenes/ui/` | UI 패널 씬 |
| `assets/` | 텍스처, 오디오, 폰트 등 |
| `tools/` | Python ML/UDP 도구 |

### 주요 스크립트 역할
- `games/boxing/scripts/stage_1.gd` — UDP 수신 + 씬 초기화/연결
- `games/boxing/scripts/player.gd` — 펀치/가드/회피 Tween + 키보드 입력
- `games/boxing/scripts/enemy.gd` — 히트 판정, HP, 피격 연출
- `games/boxing/scripts/combat_director.gd` — 전투 판정, 콤보, 승/패
- `scripts/game_state.gd` — 전역 HP/스태미너 상태 (AutoLoad `GameState`)
- `scripts/ui/ui_theme_helper.gd` — UI 스타일 공통 함수 (AutoLoad `UIThemeHelper`)

---

## 3. GameState 싱글톤 규칙

- HP/스태미너 등 **게임 전역 상태는 반드시 `GameState`**를 통해 관리
- 예: `GameState.consume_stamina(GameState.STAMINA_PUNCH)`
- 씬/노드 안에 전역과 같은 의미의 값을 **중복 저장하는 새 필드 금지**
- 새 전역 수치 추가 시:
  1. `GameState`에 필드/상수 추가
  2. 다른 스크립트는 `GameState`를 통해 접근

---

## 4. Input & UDP 규칙

### InputMap
- `punch_left`, `punch_right`, `upper_left`, `upper_right`, `guard`

### UDP 데이터 포맷 (절대 변경 금지)
- **좌표 기반**: `"left_x,left_y,right_x,right_y"`
- **액션 기반**: `"punch_l"`, `"punch_r"`, `"upper_l"`, `"upper_r"`, `"guard"`, `"guard_end"`
- GDScript 쪽에서 **포맷 변경 금지**. 포맷 변경은 **Python/ML 쪽(`tools/*.py`)에서만** 처리

### 중복 방지
- **프레임당 1회**: `main.gd`에서 같은 프레임에 여러 패킷이 와도 첫 번째만 적용
- **`_busy` 플래그**: `player.gd`에서 애니 재생 중 새 펀치/어퍼는 받지 않음
- **스태미나 부족 시 무시**: `play_action` 안에서 `consume_stamina` 실패 시 즉시 return
- **펀치류 쿨다운**: `main.gd`의 `_last_punch_accepted_time`으로 0.35초 이내 동일 액션 무시

---

## 5. 애니메이션 & 히트 판정 규칙

### Leftovers KO! 스타일 (히트박스 없음)
- 플레이어 펀치가 **임팩트 시점**에 도달하면, **적이 회피 중인지만** 검사
- 회피 중 → 빗나감 (miss), 아니면 → 무조건 히트 (`enemy.take_damage(damage)`)
- 적 쪽은 **물리 히트박스(Area2D 충돌)를 사용하지 않음**

### 새 동작 추가 규칙
1. (필요 시) `GameState`에 스태미나 상수 추가
2. `player.gd`의 `play_action`에 새 액션 분기 추가
3. 기존 `_play_*` 패턴을 복사해, **임팩트 시점 콜백에서 `punch_impact.emit(해당_데미지)`** 호출
4. Tween 끝 콜백에서 `_busy = false` 복원

---

## 6. UI 스타일링 규칙

- **모든 UI 스타일 변경은 `UIThemeHelper` 사용**
- `.tscn`에서 직접 StyleBoxFlat을 만드는 것 지양 (중복/불일치)
- 동적 스타일링 시 `UIThemeHelper.style_button_primary(btn)` 등 호출

### UIThemeHelper 상수
| 상수 | 용도 |
|------|------|
| `C_BG` | `#0D0D12` 딥 다크 배경 |
| `C_PANEL` | 반투명 글래스 패널 배경 |
| `C_ACCENT` | `#4ECDC4` 청록/민트 포인트 컬러 |
| `C_TEXT_PRIMARY` | `#F0F0F5` 주 텍스트 |
| `C_TEXT_SECONDARY` | `#8A8A9A` 보조 텍스트 |

---

## 7. 코드 작성 후 체크리스트 (필수)

새 파일/스크립트를 추가할 때마다 아래를 확인:

- [ ] `extends XXX`가 파일 최상단에 있는가?
- [ ] AutoLoad로 사용하는 파일은 `project.godot` `[autoload]`에 등록되었는가?
- [ ] `theme_override_*` 프로퍼티를 직접 대입하지 않았는가? (`add_theme_*_override` 사용)
- [ ] enum/상수 이름이 Godot 4.6 API와 일치하는가?
- [ ] 노드 reparenting 순서가 안전한가? (remove → add)
- [ ] `null` 체크 (`if node:`)가 빠진 곳은 없는가?
- [ ] Godot 4.6 공식 문서에서 사용하는 API/상수를 검증했는가?

---

## 8. 일반 주의사항

- **이미지/에셋 생성 금지** — 사용자가 직접 교체할 것이므로 placeholder/임시만 사용
- **한국어 UI 텍스트** — 기본 언어는 한국어
- **Windows 환경** — 개발 환경은 Windows (DirectShow 웹캠 백엔드 기본)
- `.tscn` 파일은 텍스트로 직접 수정할 수 있으나, **노드 구조 변경/리소스 연결**은 가능하면 Godot 에디터에서 수행하도록 안내
- **절대 `git push` 금지** (사용자가 명시적으로 요청할 때만)
- `.uid` 파일은 Godot 4가 자동 생성 — 커밋에 포함해도 무관
