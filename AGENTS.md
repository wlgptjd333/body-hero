# Body Hero — Agent 개발 가이드

> Godot 4.6 + GDScript 프로젝트. 웹캠 기반 1인칭 복싱 게임.

---

## 1. Godot 버전

- **Godot 4.6** (정확히 `4.6`)
- GDScript 2.0 문법 사용
- Forward Plus 렌더러
- Godot 4.6 공식 문서: https://docs.godotengine.org/en/stable/

---

## 2. GDScript 기본 규칙 (버그 방지용)

### 2.1 모든 스크립트는 `extends`로 시작해야 함
```gdscript
extends Node        # OK
extends Control     # OK

# 아래는 절대 안 됨 (런타임 Parser Error)
# const C := 1
```

### 2.2 AutoLoad (싱글톤) 등록 필수
- `project.godot` → `[autoload]` 섹션에 등록된 파일만 전역 이름으로 접근 가능
- 새로운 전역 헬퍼/매니저를 만들면 **반드시 `project.godot`에 추가**할 것
- 등록 없이 `SomeName.func()` 호출 → `Identifier not found` 런타임 에러

### 2.3 `theme_override_*` 프로퍼티 직접 대입 금지
- ❌ `node.theme_override_constants.separation = 6`
- ✅ `node.add_theme_constant_override("separation", 6)`
- ❌ `node.theme_override_font_sizes.font_size = 14`
- ✅ `node.add_theme_font_size_override("font_size", 14)`

### 2.4 Enum 상수 접근
- Godot 4.6에서 대부분의 enum은 클래스 상수 형태로 접근
- `BoxContainer.ALIGNMENT_CENTER` (deprecated pattern, avoid)
- **CenterContainer가 자동 중앙정렬하므로 VBoxContainer/HBoxContainer alignment 설정 불필요**
- Godot 4.6 API 문서에서 정확한 상수명 확인 후 사용

### 2.5 노드 reparenting 시 주의
```gdscript
# 안전한 순서
parent.remove_child(node)
new_parent.add_child(node)
# remove_child 후 즉시 접근핸도 null 아님 (아직 참조 유지)
```

### 2.6 `class_name` vs AutoLoad
- `class_name UIThemeHelper` — 다른 스크립트에서 `UIThemeHelper`로 접근 가능
- **AutoLoad에 등록 안 된 `class_name`은 싱글톤이 아님**
- 전역 상태/헬퍼는 **AutoLoad + extends Node** 조합이 가장 안전

### 2.7 타입 힌트
- 가능하면 변수/함수 모두 타입 명시
- 예: `var stamina: float = 100.0`, `func _process(delta: float) -> void:`
- 이름 규칙: 변수/함수는 snake_case, 상수는 UPPER_SNAKE_CASE

---

## 3. 프로젝트 구조

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
- `games/boxing/scripts/main.gd` — UDP 수신 + 글러브 위치 보정
- `games/boxing/scripts/player.gd` — 펀치/가드/회피 Tween + 키보드 폭백
- `games/boxing/scripts/enemy.gd` — 히트 판정, HP, 피격 연출
- `scripts/game_state.gd` — 전역 HP/스태미너 상태 (AutoLoad `GameState`)

---

## 4. UI 스타일링 규칙

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

## 5. GameState 싱글톤 규칙

- HP/스태미너/제자리걸음 등 게임 전역 상태는 **반드시 AutoLoad 싱글톤 `GameState`**를 통해 관리
- 예: `GameState.consume_stamina(GameState.STAMINA_PUNCH)`
- 씬/노드 안에 전역과 같은 의미의 값을 중복 저장하는 새 필드를 만들지 않는다
- 새로운 전역 수치를 추가할 때는 `GameState`에 필드/상수 추가 → 다른 스크립트는 `GameState`를 통해 접근

---

## 6. Input & UDP 규칙

### InputMap / 키보드 입력
- `punch_left`, `punch_right` (기본 A·D 외 Z·C 등 여러 키를 같은 액션에 매핑 가능)
- `upper_left`, `upper_right`
- `guard` (및 필요 시 `guard_end`)

### UDP 데이터 포맷 (절대 변경 금지)
- **좌표 기반 모드**: `"left_x,left_y,right_x,right_y"`
- **액션 기반 모드**: `"punch_l"`, `"punch_r"`, `"upper_l"`, `"upper_r"`, `"guard"`, `"guard_end"`
- GDScript 쪽에서 **UDP 데이터 포맷을 변경하거나 새 포맷을 제안하지 않는다**
- 포맷 변경/확장은 항상 Python/ML 쪽(`tools/*.py`)에서만 처리

### UDP 액션 수신 — 쿨다운·중복 방지
- **프레임당 1회만 적용**: `main.gd`에서 같은 프레임에 여러 패킷이 와도 첫 번째 액션만 적용
- **동작 중 추가 입력 차단**: `player.gd`의 `_busy` 플래그로 애니 재생 중 새 펀치/어퍼는 받지 않음
- **스태미나 부족 시 무시**: `play_action` 안에서 `GameState.consume_stamina(...)` 실패 시 즉시 return
- **게임 쪽 액션 쿨다운**: `main.gd`의 `_apply_glove_data`에서 펀치류에 대해 `ACTION_COOLDOWN_SEC`(예: 0.35초) 이내의 동일 액션은 무시

---

## 7. 애니메이션 & 히트 판정 규칙

### 피격 판정 (히트박스 없음, Leftovers KO! 스타일)
- 플레이어 펀치가 **임팩트 시점**에 도달하면, **적이 회피 중인지만** 검사
- 적이 회피 중 → 빗나감 (miss), 회피 중이 아님 → 무조건 히트 (`enemy.take_damage(damage)`)
- 적 쪽은 **물리 히트박스(Area2D 충돌)를 사용하지 않는다**

### 새 펀치/동작 추가 규칙
1. (필요 시) `GameState`에 스태미너 상수 추가
2. `player.gd`의 `play_action`에 새 액션 분기 추가
3. 기존 `_play_*` 패턴을 복사해, **임팩트 시점 콜백에서 `punch_impact.emit(해당_데미지)`** 호출
4. Tween 끝 콜백에서 `_busy = false` 복원

---

## 8. Python / ML 도구

- `tools/` 폴더 내 스크립트는 Python 3.12 가상환경 `venv_ml` 사용
- TensorFlow, MediaPipe, OpenCV 의존성 존재
- 프로젝트 외부에 패키지 설치 금지
- ML 관련 커맨드는 `tools/README_ML.md`의 워크플로를 우선 따른다

---

## 9. 커밋 / 푸시 규칙

- **절대 `git push` 금지** (사용자가 명시적으로 요청할 때만)
- `git commit`은 사용자 요청 시 또는 작업 단위 완료 시 수행
- `.uid` 파일은 Godot 4가 자동 생성 — 커밋에 포함필도 무관

---

## 10. 코드 작성 후 체크리스트 (필수)

새 파일/스크립트를 추가할 때마다 아래를 확인:

- [ ] `extends XXX`가 파일 최상단에 있는가?
- [ ] AutoLoad로 사용하는 파일은 `project.godot` `[autoload]`에 등록되었는가?
- [ ] `theme_override_*` 프로퍼티를 직접 대입하지 않았는가? (`add_theme_*_override` 사용)
- [ ] enum/상수 이름이 Godot 4.6 API와 일치하는가?
- [ ] 노드 reparenting 순서가 안전한가? (remove → add)
- [ ] `null` 체크 (`if node:`)가 빠진 곳은 없는가?
- [ ] Godot 4.6 공식 문서에서 사용하는 API/상수를 검증했는가?

---

## 11. 일반 주의사항

- **이미지/에셋 생성 금지** — 사용자가 직접 교체할 것이므로 placeholder/임시만 사용
- **한국어 UI 텍스트** — 기본 언어는 한국어
- **Windows 환경** — 개발 환경은 Windows (DirectShow 웹캠 백엔드 기본)
- `.tscn` 파일은 텍스트로 직접 수정할 수 있으나, **노드 구조 변경/리소스 연결**은 가능하면 Godot 에디터에서 수행하도록 안내
