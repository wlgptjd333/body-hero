# UDP로 Godot에 액션 보내기 (고정 글러브 + 행동 트리거)

**Godot에는 웹캠/MediaPipe 플러그인을 설치할 필요가 없습니다.**  
Godot은 **UDP 포트 4242**에서 **액션 문자열**만 받습니다. 글러브는 화면에 고정되어 있고, 행동이 감지되면 해당 애니만 재생됩니다.

## 동작 순서 (중요)

1. **먼저 Godot에서 게임 실행** (F5)
2. **ML 판정(권장)**: `python udp_send_webcam_ml.py` 실행  
   - 로컬에 `pose_classifier_seq_len4.keras` 또는 `pose_classifier_seq.keras`가 있으면 **pose_server 없이** 바로 동작합니다(4프레임 모델이 있으면 그쪽을 우선).  
   - 모델이 없으면 `pose_server.py`를 먼저 실행한 뒤 `udp_send_webcam_ml.py`를 실행하세요.
3. **펀치 / 어퍼컷 / 가드** 동작을 하면 Godot에서 해당 애니가 재생됩니다.

※ 서버/ML 없이 빠르게 테스트만 하려면: `python udp_send_webcam.py` (휴리스틱 판정, 좌우 펀치만)

키보드만으로 테스트: **A**=왼손 펀치, **D**=오른손 펀치, **Q**=왼손 어퍼컷, **E**=오른손 어퍼컷, **S**=가드. (**Z**/**C**는 InputMap의 보조 펀치 키.)

## 전송되는 액션

| 액션      | UDP 문자열 | 설명           |
|-----------|------------|----------------|
| 왼손 펀치 | `punch_l`  | ML·게임 공통 |
| 오른손 펀치 | `punch_r` | ML·게임 공통 |
| 왼손 어퍼컷 | `upper_l` | 왼손이 위로 빠르게 |
| 오른손 어퍼컷 | `upper_r` | 오른손이 위로 빠르게 |
| 양손 가드 | `guard`    | 양손을 얼굴 쪽에 올려 유지 |

**ML**(`udp_send_webcam_ml.py`)은 시퀀스 모델 클래스 `punch_l`/`punch_r`을 그대로 UDP로 보냅니다. 구 데이터의 옛 라벨은 `relabel_pose_with_collect.py` 등으로 `punch_*`에 맞추면 됩니다.

## 웹캠 사용 — ML 판정 (권장)

게임 연결 시 **udp_send_webcam_ml.py** 사용을 권장합니다. 가드는 단일 프레임, 펀치는 시퀀스 딥러닝으로 판정합니다.

**pose_server 없이 실행 가능**: 스크립트가 **로컬에서 직접 추론**할 수 있습니다. 아래 모델 파일이 `tools` 폴더에 있으면 pose_server를 켜지 않아도 됩니다.

- **pose_classifier_seq_len4.keras** (권장, 4프레임) **또는** **pose_classifier_seq.keras** (8프레임) — 시퀀스 펀치/가드 판정. 둘 다 있으면 **4프레임 모델을 우선** 로드합니다(반응 속도가 빠른 쪽을 게임 기본으로 둠).
- **pose_classifier.keras** (선택) — 가드 단일 프레임 폴백. 없으면 시퀀스 모델만 사용합니다.

로컬 추론 시 `tensorflow`, `numpy`가 필요합니다 (`pip install tensorflow numpy`). 모델이 없거나 TensorFlow가 없으면 기존처럼 **pose_server**로 HTTP 요청합니다 (이때는 `python pose_server.py`를 먼저 실행).

### Python 환경: ML과 스프라이트(rembg) 분리 권장

`sanitize_sprites.py`용으로 `rembg` / `onnxruntime` 등을 **ML과 같은 가상환경(또는 전역 Python)** 에 설치하면 `protobuf`·`numpy`·Windows DLL 조합이 바뀌어 **`udp_send_webcam_ml.py`가 ImportError나 DLL 오류로 안 켜질 수 있습니다.**

**권장:** 가상환경을 둘로 나눕니다.

1. **ML·웹캠·Godot 연동 전용**  
   프로젝트 루트에서 `python -m venv .venv_ml` → 활성화 → `pip install -r tools/requirements_ml.txt`  
   → `udp_send_webcam_ml.py`, `pose_server.py`, 학습 스크립트는 **항상 이 venv**에서 실행.
2. **스프라이트 배경 제거 전용(선택)**  
   `python -m venv .venv_sprites` → `pip install -r tools/requirements_sprites.txt` → `sanitize_sprites.py`만 여기서 실행.

이미 한 환경에 다 설치해 꼬였다면: ML용 venv를 새로 만들고 `requirements_ml.txt`만 다시 깔거나, 같은 venv에서 `pip install -r tools/requirements_ml.txt --force-reinstall` 를 시도해 보세요.

**동작 확인(ML venv에서):**  
`python -c "import cv2; import tensorflow; from mediapipe.tasks.python import vision; print('ok')"`

1. 데이터 수집·학습 → [README_ML.md](README_ML.md) (학습 후 `tools`에 `.keras` 파일 생성)
2. **(로컬 추론)** 게임 실행(F5) 후: `python udp_send_webcam_ml.py`  
   - 로컬 모델/TensorFlow가 없으면 **pose_server를 같은 스크립트가 자동으로 띄움** (이미 5000 포트에 서버가 있으면 그대로 사용).  
   - 자동 시작을 끄려면: `python udp_send_webcam_ml.py --no-auto-server` 후 별도 터미널에서 `python pose_server.py`
3. 외부 웹캠을 쓰면 카메라 번호를 지정하세요: `python udp_send_webcam_ml.py --camera-index 1`

## 웹캠 사용 — 휴리스틱만 (테스트용)

ML 서버 없이 동작만 확인할 때: `python udp_send_webcam.py`

한 번만 설치: `pip install mediapipe opencv-python`

실행 (CMD):
```cmd
cd c:\Users\User\Documents\body-hero\tools
python udp_send_webcam.py
```

감도/쿨다운은 스크립트 상단 상수에서 조정할 수 있습니다.

## 시퀀스 길이 (학습·실행 모두 기본 4프레임)

학습·서버·클라이언트 모두 **시퀀스 길이 4프레임**이 기본입니다. 4프레임은 약 0.13초 분량의 동작을 보고 분류하므로 반응이 빠릅니다.

- 학습: `train_pose_classifier_seq.py` 인자 없이 실행하면 **4프레임 모델**을 학습해 `pose_classifier_seq_len4.keras` 로 저장.
- 게임/추론: `udp_send_webcam_ml.py`, `pose_server.py`, `test_pose_live.py` 모두 `pose_classifier_seq_len4.keras` 가 있으면 그것을 우선 로드하고, 없을 때만 `pose_classifier_seq.keras`(8프레임)로 폴백.

```cmd
cd tools
python train_pose_classifier_seq.py            :: 기본 4프레임 모델 (pose_classifier_seq_len4.keras)
python train_pose_classifier_seq.py --seq-len 8 :: 8프레임 모델을 별도로 학습 (pose_classifier_seq.keras)
```

> 시퀀스 길이가 다르면 모델 입력 텐서 모양이 달라져서 **별개의 모델 파일**이 만들어집니다. 4프레임용 가중치를 8프레임 입력에 그대로 쓸 수 없습니다. 그래서 학습할 때 `--seq-len` 을 바꿔주면 자동으로 다른 파일로 저장됩니다.
>
> 학습이 끝났을 때 “게임이 우선 로드하는 모델”과 다른 파일을 갱신했다면 콘솔에 경고가 출력됩니다.

다른 길이를 쓰려면 `--seq-len 12` 등으로 지정한 뒤, `pose_server` / `udp_send_webcam_ml` / `test_pose_live` 의 모델 우선순위 분기를 같은 값으로 맞추세요. 학습 시 **임팩트 이후 구간만** 사용하므로 `pose_recordings_meta.json`에 `impact_idx`가 있어야 합니다.

## udp_send_webcam_ml.py 렉이 심할 때

스크립트 상단 상수로 부하를 줄일 수 있습니다.

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `PROCESS_W`, `PROCESS_H` | 320, 240 | 처리 해상도. 더 낮추면 가벼움 (예: 256, 192) |
| `PROCESS_EVERY_N_FRAMES` | 2 | 이 프레임 수마다만 포즈+ML 실행 (3으로 하면 더 가벼움) |
| `FPS_TARGET` | 24 | 목표 FPS. 20 이하로 낮추면 CPU 여유 생김 |

ML 예측은 백그라운드 스레드에서 수행되므로 서버 응답이 느려도 메인 루프가 멈추지 않습니다.

## 안 될 때

- **액션이 안 먹으면**: Godot을 **먼저** 실행했는지, 같은 PC에서 Python을 실행했는지 확인하세요.
- **인식이 너무 잘 되거나 안 되면**: `udp_send_webcam.py` 안의 `PUNCH_VELOCITY_MIN`, `UPPERCUT_DY_MIN`, `GUARD_Y_THRESHOLD`, `COOLDOWN_SEC` 값을 조정해 보세요.
