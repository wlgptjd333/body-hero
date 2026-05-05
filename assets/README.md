# Assets 정리

이 프로젝트는 에셋을 종류별로 폴더를 나눠 관리합니다.

## 권장 폴더 구조

- `assets/audio/` : 오디오
  - `assets/audio/bgm/` : 배경음악
  - `assets/audio/sfx/` : 효과음
- `assets/textures/` : 이미지(텍스처)
  - `assets/textures/bg/` : 배경 (예: 스테이지 `bg_stage1_burger.png`)
  - `assets/textures/characters/player/` : 플레이어 글러브 등
  - `assets/textures/characters/enemies/<이름>/` : 적 스프라이트 (예: `burger/burger_idle_*.png`)
  - `assets/textures/ui/` : UI 이미지

**Godot 런타임**에서 쓰는 최종 텍스처·오디오는 위 `assets/` 트리에만 둡니다.

## 작업용 원본 (`work_images/`)

레퍼런스·전처리·파이프라인 산출물은 프로젝트 루트의 `work_images/` (`reference/`, `input/`, `output/`)에 둡니다. 이 폴더에는 **`work_images/.gdignore`**가 있어 Godot이 임포트하지 않습니다. Python 도구(`tools/work_images_paths.py` 등)는 계속 이 경로를 사용할 수 있습니다.

## 빠른 안내

- 오디오 위치/규칙은 `assets/audio/README.md` 참고
- 텍스처 세부는 `assets/textures/README.md` 참고
- 과거 이동 체크리스트·현재 구조 요약은 `assets/ASSET_MIGRATION.md` 참고
