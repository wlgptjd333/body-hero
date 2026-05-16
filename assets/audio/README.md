# 오디오 에셋

오디오 파일은 아래처럼 분리해서 관리합니다.

- `assets/audio/bgm/` : 배경음악(BGM)
- `assets/audio/sfx/` : 효과음(SFX)

## 권장 파일명

- 메인 메뉴 BGM: `assets/audio/bgm/mainbgm.ogg`
- 타격음(예): `assets/audio/sfx/sfx_punch_hit.wav`

## (중요) Godot 오디오 버스 만들기

설정 창의 **전체/게임/음악** 볼륨 슬라이더를 제대로 쓰려면 Godot에서 오디오 버스를 만들어야 합니다.

1. 에디터 하단 **Audio** 탭을 엽니다.
2. `Master` 아래에 버스를 2개 추가합니다.
   - `SFX`
   - `Music`

이후:
- 효과음 노드(펀치 등)는 `SFX`
- BGM 노드는 `Music`
버스로 재생되어, 설정에서 각각 조절됩니다.

