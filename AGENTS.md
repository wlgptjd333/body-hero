# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Body Hero는 Godot 4.6.1 기반 웹캠 1인칭 헬스 복싱 게임입니다. 자세한 프로젝트 구조와 코딩 규칙은 `README.md`, `.cursor/rules/`, `.cursor/skills/godot-health-fighter-4-6/SKILL.md`을 참고하세요.

### Services

| Service | How to run | Notes |
|---|---|---|
| Godot 게임 | `DISPLAY=:99 godot --rendering-driver opengl3 --path /workspace` | Xvfb 필요 (아래 참고) |
| Python ML tools | `/workspace/tools/venv_ml/bin/python <script>` | venv 경로 사용 |

### Running the Godot game (headless VM)

- 이 VM에는 GPU가 없으므로 반드시 `--rendering-driver opengl3`으로 소프트웨어 렌더링(llvmpipe)을 사용해야 합니다.
- 게임 실행 전 Xvfb 가상 디스플레이를 시작해야 합니다:
  ```bash
  Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
  export DISPLAY=:99
  ```
- ALSA 오디오 오류는 무시해도 됩니다. Godot이 자동으로 더미 오디오 드라이버로 폴백합니다.
- 게임 시작: 메인 메뉴에서 "게임 시작" 버튼 클릭 후, 키보드(A/D/Q/E/S)로 테스트 가능합니다.

### GDScript validation

- Godot 4.6에는 독립적인 CLI lint 도구가 없습니다. 스크립트 검증은 `godot --headless --import`로 프로젝트를 임포트한 후 에러 유무를 확인하는 방식이 가장 실용적입니다.

### Python ML tools

- Python venv 경로: `/workspace/tools/venv_ml/`
- 의존성: `tools/requirements_ml.txt` (mediapipe, opencv, tensorflow, flask 등)
- 웹캠이 없는 VM 환경에서는 `udp_send_mouse.py`로 마우스 기반 테스트가 가능합니다.
