# 텍스처(이미지) 에셋

이미지 파일은 아래처럼 폴더를 나눠 관리합니다.

- `assets/textures/bg/` : 배경
- `assets/textures/characters/player/` : 플레이어(글러브 등)
- `assets/textures/characters/enemies/<이름>/` : 적 스프라이트 (예: `burger/`)
- `assets/textures/ui/` : UI 이미지

권장: Godot의 FileSystem 패널에서 드래그&드롭으로 옮기세요(경로·UID 자동 갱신).

작업 파이프라인용 파일은 `work_images/`에 두고, 게임에 태울 최종본만 `assets/`에 둡니다(`work_images/.gdignore` 참고).
