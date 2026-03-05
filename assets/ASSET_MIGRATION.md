# 에셋 이동 체크리스트 (권장)

Godot에서 **FileSystem 패널로 드래그&드롭 이동**하면, 씬(`.tscn`)에 박혀있는 경로도 자동 갱신되어 가장 안전합니다.

## 1) 폴더 만들기

- `assets/audio/bgm/`
- `assets/audio/sfx/`
- `assets/textures/bg/`
- `assets/textures/characters/`
- `assets/textures/ui/`

이미 폴더가 있다면 생략해도 됩니다.

## 2) 오디오 이동

- `assets/sfx_punch_hit.wav` → `assets/audio/sfx/sfx_punch_hit.wav`
- (BGM) `assets/audio/mainbgm.ogg` 또는 `bgm_main.ogg` → `assets/audio/bgm/mainbgm.ogg`

## 3) 이미지 이동

- `assets/bg_leftovers_ko.png` → `assets/textures/bg/bg_leftovers_ko.png`
- `assets/placeholder_enemy.svg` → `assets/textures/characters/placeholder_enemy.svg`
- `assets/placeholder_glove.svg` → `assets/textures/characters/placeholder_glove.svg`
- `assets/placeholder_bg.svg` → `assets/textures/ui/placeholder_bg.svg`

## 4) 이동 후 확인

- 메인 메뉴에서 BGM이 재생되는지
- 게임에서 타격음이 들리는지
- 배경/캐릭터 이미지가 정상 표시되는지

문제가 있으면, 해당 노드의 Inspector에서 Texture/Stream 경로를 다시 지정하면 해결됩니다.

