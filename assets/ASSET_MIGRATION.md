# 에셋 이동 체크리스트

Godot에서 **FileSystem 패널로 드래그&드롭 이동**하면, 씬(`.tscn`)에 박혀있는 경로도 자동 갱신되어 가장 안전합니다.

## 1) 폴더 만들기

- `assets/audio/bgm/`
- `assets/audio/sfx/`
- `assets/textures/bg/`
- `assets/textures/characters/player/`
- `assets/textures/characters/enemies/` (적별 서브폴더, 예: `burger/`)
- `assets/textures/ui/`

이미 폴더가 있다면 생략해도 됩니다.

## 2) 오디오 이동 (레거시 정리)

- `assets/sfx_punch_hit.wav` → `assets/audio/sfx/sfx_punch_hit.wav`
- (BGM) `assets/audio/mainbgm.ogg` 또는 `bgm_main.ogg` → `assets/audio/bgm/mainbgm.ogg`

## 3) 이미지 이동 (레거시 정리)


- `assets/placeholder_enemy.svg` → `assets/textures/characters/placeholder_enemy.svg`
- `assets/placeholder_glove.svg` → `assets/textures/characters/placeholder_glove.svg`
- `assets/placeholder_bg.svg` → `assets/textures/ui/placeholder_bg.svg`

## 4) 복싱 스테이지 에셋 (현재 구조)

다음은 **게임에서 참조하는 최종 경로**입니다.

| 용도 | 경로 |
|------|------|
| 스테이지 배경 | `assets/textures/bg/bg_stage1_burger.png` |
| 플레이어 글러브 | `assets/textures/characters/player/left_glove.png`, `right_glove.png` |
| 버거 적 스프라이트 | `assets/textures/characters/enemies/burger/burger_idle_*.png`, `burger_punch_l_*.png`, `burger_hit_*.png`, `burger_ko_*.png` |

코드: `games/boxing/scripts/enemy.gd`, `player.gd`의 `res://assets/textures/...` 상수 및 `scenes/main.tscn`, `games/boxing/scenes/main.tscn`의 `ext_resource`.

원본 스크린샷 JPEG는 Git에 `work_images/reference/bg_stage1_burger.png.jpg`로 포함될 수 있습니다. 게임용 배경은 `assets/textures/bg/`의 PNG를 사용합니다.

## 5) `work_images/` 격리

- 루트에 **`work_images/.gdignore`**를 두면 Godot이 `work_images/` 전체를 임포트 대상에서 제외합니다.
- Cursor 검색 노이즈를 줄이려면 프로젝트 **`.cursorignore`**에 `work_images/`를 추가합니다.
- Python 파이프라인(`tools/sanitize_sprites.py`, `process_idle_aseprite.py` 등)은 파일 시스템 경로로 `work_images/`를 읽습니다. `.gdignore`는 Godot만 영향 줍니다.

## 6) 이동 후 확인

- 메인 메뉴에서 BGM이 재생되는지
- 게임에서 타격음이 들리는지
- 배경/캐릭터 이미지가 정상 표시되는지

문제가 있으면, 해당 노드의 Inspector에서 Texture/Stream 경로를 다시 지정하면 해결됩니다.
