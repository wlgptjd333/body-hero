# Body Hero

웹캠 1인칭 헬스 복싱 게임 (Godot 4.6) — Punch your screen to fight! Real-time body tracking with webcam.

## CMD 명령어 정리 (Windows)

프로젝트 폴더로 이동:
```cmd
cd c:\Users\User\Documents\body-hero
```

**웹캠으로 게임 플레이 (threshold 판정):**
```cmd
cd c:\Users\User\Documents\body-hero\tools
pip install mediapipe opencv-python
python udp_send_webcam.py
```
※ Godot에서 게임을 **먼저** 실행한 뒤 웹캠 스크립트를 실행하세요.

**ML(딥러닝) 판정 사용 시 (데이터 수집 → 학습 → 서버 → ML 웹캠):**
```cmd
cd c:\Users\User\Documents\body-hero\tools
py -3.12 -m venv venv_ml
venv_ml\Scripts\activate
pip install -r requirements_ml.txt
python collect_pose_data.py
python train_pose_classifier.py
python pose_server.py
```
다른 터미널에서:
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\activate
python udp_send_webcam_ml.py
```

**마우스로 글러브 테스트:**
```cmd
cd c:\Users\User\Documents\body-hero\tools
python udp_send_mouse.py
```

## 빠른 실행

1. **Godot 4.6**으로 `project.godot` 열기
2. **F5** 또는 재생 버튼으로 실행
3. **키보드 테스트**: **A** = 왼손 펀치, **D** = 오른손 펀치  
   (입력이 안 되면 **프로젝트 → 프로젝트 설정 → Input Map**에서 `punch_left`에 A, `punch_right`에 D 추가)

## UDP 웹캠 테스트 (마우스로 글러브 움직이기)

1. Godot에서 게임 실행
2. 터미널에서:
   ```bash
   cd tools
   python udp_send_mouse.py
   ```
3. 마우스를 움직이면 글러브가 마우스 위치를 따라감 (Windows는 별도 패키지 없이 동작)

## 폴더 구조

- `scenes/main.tscn` — 메인 씬 (Background, Enemy, Player 글러브, HUD)
- `scripts/main.gd` — UDP 수신 + 글러브 위치 보정
- `scripts/player.gd` — 펀치 Tween, 키보드 입력
- `scripts/enemy.gd` — 히트판정, HP, 맞을 때 깜빡임
- `tools/udp_send_mouse.py` — UDP 테스트용 (마우스 → Godot)

## 다음 단계

- 햄버거 시트 등 에셋을 `scenes/main.tscn`의 Enemy / Background / 글러브 스프라이트에 연결
- MediaPipe로 손목 좌표 추출 후 `"left_x,left_y,right_x,right_y"` 형식으로 UDP 전송
