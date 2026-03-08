# UDP로 Godot에 액션 보내기 (고정 글러브 + 행동 트리거)

**Godot에는 웹캠/MediaPipe 플러그인을 설치할 필요가 없습니다.**  
Godot은 **UDP 포트 4242**에서 **액션 문자열**만 받습니다. 글러브는 화면에 고정되어 있고, 행동이 감지되면 해당 애니만 재생됩니다.

## 동작 순서 (중요)

1. **먼저 Godot에서 게임 실행** (F5)
2. **그다음** 웹캠 스크립트 실행: `python udp_send_webcam.py`
3. **잽 / 어퍼컷 / 가드** 동작을 하면 Godot에서 해당 애니가 재생됩니다.

키보드만으로 테스트: **A**=왼손 잽, **D**=오른손 잽, **Q**=왼손 어퍼컷, **E**=오른손 어퍼컷, **S**=가드.

## 전송되는 액션

| 액션      | UDP 문자열 | 설명           |
|-----------|------------|----------------|
| 왼손 잽   | `jab_l`    | 왼손이 오른쪽으로 빠르게 |
| 오른손 잽 | `jab_r`    | 오른손이 왼쪽으로 빠르게 |
| 왼손 어퍼컷 | `upper_l` | 왼손이 위로 빠르게 |
| 오른손 어퍼컷 | `upper_r` | 오른손이 위로 빠르게 |
| 양손 가드 | `guard`    | 양손을 얼굴 쪽에 올려 유지 |
| 왼손 훅  | `hook_l`   | 왼손 옆에서 말아 들어오기 (ML 판정 시) |
| 오른손 훅 | `hook_r`  | 오른손 옆에서 말아 들어오기 (ML 판정 시) |

**훅(hook_l, hook_r)** 은 ML 파이프라인(`udp_send_webcam_ml.py` + 학습 데이터에 hook 수집) 사용 시 전송됩니다.

## 웹캠 사용 (udp_send_webcam.py)

한 번만 설치:
```cmd
pip install mediapipe opencv-python
```
- 최신 mediapipe는 **Tasks API**로 동작하며, 처음 실행 시 Pose 모델을 자동 다운로드합니다.
- 실행 시 나오는 `W0000` / `INFO` 메시지는 무시해도 됩니다.

실행 (CMD):
```cmd
cd c:\Users\User\Documents\body-hero\tools
python udp_send_webcam.py
```
프로젝트 루트에서라면:
```cmd
cd tools
python udp_send_webcam.py
```

감도/쿨다운은 스크립트 상단 상수(`JAB_VEL_MIN`, `COOLDOWN_SEC` 등)에서 조정할 수 있습니다.

**딥러닝 판정**으로 바꾸고 싶다면 → [README_ML.md](README_ML.md) (데이터 수집 → 학습 → ML 서버 + `udp_send_webcam_ml.py`).

## 안 될 때

- **액션이 안 먹으면**: Godot을 **먼저** 실행했는지, 같은 PC에서 Python을 실행했는지 확인하세요.
- **인식이 너무 잘 되거나 안 되면**: `udp_send_webcam.py` 안의 `JAB_VEL_MIN`, `UPPERCUT_DY_MIN`, `GUARD_Y_THRESHOLD`, `COOLDOWN_SEC` 값을 조정해 보세요.
