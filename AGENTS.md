# Body Hero — Agent 개발 가이드

> Godot 4.6 + GDScript 프로젝트. 웹캠 기반 1인칭 복싱 게임.

---

## 1. Godot 버전

- **Godot 4.6** (정확히 `4.6`)
- GDScript 2.0 문법 사용
- Forward Plus 렌더러

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
- ✅ `HBoxContainer.ALIGNMENT_CENTER` (Godot 4.6 기준, `AlignmentMode` enum)
- ⚠️ `BoxContainer.ALIGN_CENTER` — **VBoxContainer/HBoxContainer의 `alignment` 프로퍼티는 `BoxContainer.AlignmentMode` 타입**이지만, CenterContainer 등 다른 컨테이너 안에서는 **설정 불필요**
- Godot 4.6에서 `BoxContainer.ALIGN_CENTER`는 존재하지만, **CenterContainer 낭비 사용 금지**

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

## 5. 커밋 / 푸시 규칙

- **절대 `git push` 금지** (사용자가 명시적으로 요청할 때만)
- `git commit`은 사용자 요청 시 또는 작업 단위 완료 시 수행
- `.uid` 파일은 Godot 4가 자동 생성 — 커밋에 포함필도 무관

---

## 6. 코드 작성 후 체크리스트 (필수)

새 파일/스크립트를 추가할 때마다 아래를 확인:

- [ ] `extends XXX`가 파일 최상단에 있는가?
- [ ] AutoLoad로 사용하는 파일은 `project.godot` `[autoload]`에 등록되었는가?
- [ ] `theme_override_*` 프로퍼티를 직접 대입하지 않았는가? (`add_theme_*_override` 사용)
- [ ] enum/상수 이름이 Godot 4.6 API와 일치하는가?
- [ ] 노드 reparenting 순서가 안전한가? (remove → add)
- [ ] `null` 체크 (`if node:`)가 빠진 곳은 없는가?

---

## 7. Python / ML 도구

- `tools/` 폴더 내 스크립트는 Python 3.12 가상환경 `venv_ml` 사용
- TensorFlow, MediaPipe, OpenCV 의존성 존재
- 프로젝트 외부에 패키지 설치 금지

---

## 8. 일반 주의사항

- **이미지/에셋 생성 금지** — 사용자가 직접 교체할 것이므로 placeholder/임시만 사용
- **한국어 UI 텍스트** — 기본 언어는 한국어
- **Windows 환경** — 개발 환경은 Windows (DirectShow 웹캠 백엔드 기본)
