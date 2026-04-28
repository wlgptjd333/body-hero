# Body Hero

웹캠 1인칭 헬스 복싱 게임 (Godot 4.6) — Punch your screen to fight! Real-time body tracking with webcam.

## CMD 명령어 정리 (Windows)

프로젝트 폴더로 이동:
```cmd
cd c:\Users\User\Documents\body-hero
```

**웹캠으로 게임 플레이 (권장: ML 시퀀스 판정):**

※ 연속 8프레임으로 학습·추론하는 시퀀스 모델 사용 (정확도 우수).  
※ **작업 디렉터리는 항상 `tools` 폴더** (`c:\Users\User\Documents\body-hero\tools`). 가상환경은 이 안의 `venv_ml`에 둡니다.  
※ **activate 없이** `venv_ml\Scripts\python.exe`로 실행하면 됩니다 (경로만 맞으면 됨).

**최초 1회** (venv_ml이 없을 때):

```cmd
cd c:\Users\User\Documents\body-hero\tools
py -3.12 -m venv venv_ml
venv_ml\Scripts\python.exe -m pip install -r requirements_ml.txt
```

**이후 매번** (데이터 수집 → 학습 → 서버):

```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe collect_pose_data.py --camera-index 0 --camera-backend auto
venv_ml\Scripts\python.exe train_pose_classifier_seq.py
venv_ml\Scripts\python.exe pose_server.py
```
`collect_pose_data.py`는 **기본으로 매 녹화·백스페이스 직후** `pose_data.json`과 `pose_recordings_meta.json`을 디스크에 저장합니다(Q 전 크래시 대비). 끄려면 `--no-autosave`. **웹캠 선택**: `--camera-index`(0~9), `--camera-backend`(auto|default|dshow|msmf). USB가 안 열리면 `dshow`와 인덱스 1·2를 시도하거나, 게임 **설정 → 웹캠**과 동일하게 맞춘 뒤 **「포즈 녹화」** 버튼으로 실행할 수 있습니다.

`train_pose_classifier_seq.py`는 기본 **좌우 반전 증강**(L/R 라벨 스왑) + **펀치·어퍼 L:R 쌍 소수 오버샘플**을 켭니다. 예전 모델은 `upper_l`/`upper_r` 혼동이 나기 쉬우니 **재학습**을 권장합니다.

**L/R 헷갈림 점검·일괄 학습 (펀치·어퍼 공통):**
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe report_pose_lr_balance.py
venv_ml\Scripts\python.exe train_pose_lr_focused.py
```
- `report_pose_lr_balance.py`: 프레임·시퀀스 기준으로 `punch_l`/`punch_r`, `upper_l`/`upper_r` 개수 비율 출력(옛 라벨 문자열이 있으면 그대로 집계).
- **메타와 `pose_data.json` 라벨이 어긋남** (콘솔 녹화 횟수는 정상인데 프레임에 어퍼 등이 없음 등): `venv_ml\Scripts\python.exe relabel_pose_with_collect.py` → 메타 구간·누른 키 기준으로 랜드마크는 유지하고 라벨만 `collect` 로직으로 재생성. 먼저 `venv_ml\Scripts\python.exe relabel_pose_with_collect.py --dry-run` 권장. `start_index` 유지는 `--in-place`.
- **메타만 데이터보다 김** (`인덱스 초과: start=… len(data)=…`): `relabel_pose_with_collect.py`가 **기본으로** 메타 끝(phantom 녹화)을 잘라 맞춘 뒤 진행합니다. 보정 끄기: `--no-repair-meta`.
- `train_pose_lr_focused.py`: 위 리포트 → 시퀀스 학습 → (선택) 단일 프레임 가드 모델까지 연속 실행. `--skip-single` 로 가드 모델만 생략.
- 시퀀스만 따로: `venv_ml\Scripts\python.exe train_pose_classifier_seq.py` (`--no-balance-lr-pairs` 로 오버샘플 끔, `--lr-oversample-max-ratio 8` 등으로 강도 조절).

가드 인식·유지 개선: `pose_classifier.keras`(단일 프레임)가 있으면 서버가 가드를 단일 프레임으로 먼저 판정합니다. 없으면 `venv_ml\Scripts\python.exe train_pose_classifier.py` 한 번 실행해 두세요.

**게임 연결:** Godot에서 게임 실행(F5) 후, 다른 터미널에서:
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe udp_send_webcam_ml.py
```
※ 웹캠이 안 켜지면: 게임을 먼저 켠 상태에서 `udp_send_webcam_ml.py`를 실행했는지 확인하세요. 게임 화면 하단에 웹캠 안내 문구가 보입니다.

**USB 웹캠 / 카메라 번호:** OpenCV 기준 기본은 인덱스 `0`(내장)입니다. USB만 쓰는 경우 `1` 또는 `2`인 경우가 많습니다. Windows에서는 기본으로 **DirectShow를 먼저** 시도해 인덱스가 기대와 맞는 경우가 많습니다(`--camera-backend auto`, 스크립트 기본값). 여전히 내장만 켜지면 설정에서 인덱스를 바꾸거나 `venv_ml\Scripts\python.exe udp_send_webcam_ml.py --camera-index 1 --camera-backend dshow` 를 시험해 보세요.

게임 **설정**에서 카메라를 고른 뒤 **적용**하면 저장되고, 복싱 스테이지 자동 실행 시 `--camera-index`로 넘어갑니다. 수동 실행 예:

```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe udp_send_webcam_ml.py --camera-index 1
```

**목록 새로고침(설정 UI):** `venv_ml`과 `list_cameras.py`가 있으면 설정에서 열리는 카메라 인덱스만 스캔합니다. 터미널만 쓸 때는 `venv_ml\Scripts\python.exe list_cameras.py` (stdout) 또는 `… list_cameras.py C:\temp\out.txt`.

**자동 실행(복싱 스테이지):** `tools/venv_ml/Scripts/python.exe`와 `udp_send_webcam_ml.py`가 있으면 게임이 브리지를 띄웁니다. **설정 → 카메라 / 카메라 API**에서 저장한 `--camera-index`·`--camera-backend`가 그대로 전달됩니다(Windows 저장 파일 없을 때 기본 API는 DirectShow). **다시하기**로 같은 씬을 다시 열면 인덱스·API가 같을 때는 프로세스를 끄지 않고 유지합니다. 게임 종료(메뉴 종료) 시에만 브리지를 끕니다. 에디터에서 복싱 메인 노드의 **Auto Launch Webcam Ml**을 끄면 비활성화합니다.

**해상도·카메라 저장:** 설정에서 **적용**하면 `user://display_settings.cfg`에 창 크기와 카메라 인덱스가 저장되어 다음 실행부터 반영됩니다.

**ML 없이 테스트만 (휴리스틱 판정):** `venv_ml` 없이도 되면 시스템 `python`으로 `udp_send_webcam.py` 실행 가능. 가상환경을 쓰려면 `venv_ml\Scripts\python.exe udp_send_webcam.py` — USB는 동일하게 `--camera-index` 사용. 서버·학습 없이 동작 확인용.

**녹화 데이터 삭제:**
- **녹화 중**: **Backspace** → 방금 녹화한 1회만 취소 (Q로 종료 시 반영).
- **저장된 파일에서**: `venv_ml\Scripts\python.exe delete_pose_recordings.py --last 1` (마지막 1회 삭제). `--last 5`면 5회. `--dry-run`이면 저장 없이 확인만.

**마우스로 글러브 테스트:**
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe udp_send_mouse.py
```
(venv 없이 테스트만 할 때는 `python udp_send_mouse.py` 도 가능.)

## 배포(보내기) — 최종 사용자에게 `pip`/CMD 없이 쓰게 하려면

1. Godot **프로젝트 → 보내기**에서 Windows Desktop 등 프리셋을 추가하고 실행 파일을 보냅니다.
2. 보낸 **폴더 안**에 이 저장소의 **`tools` 디렉터리 전체**를 복사합니다(미리 만든 `venv_ml`, `*.py`, 학습된 `*.keras` 포함). 실행 파일과 나란히 `tools\venv_ml\…` 구조가 되어야 자동 실행이 동작합니다.
3. (선택) PowerShell에서 export 출력 경로를 넘겨 `tools`만 복사합니다:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_release.ps1 -ExportDir "C:\경로\Godot보내기폴더"
```

용량은 TensorFlow/MediaPipe 때문에 **수백 MB~1GB 이상**일 수 있습니다. Windows x64용으로 묶은 `venv_ml`은 같은 종류의 PC에서만 기대할 수 있습니다.

## 빠른 실행

1. **Godot 4.6**으로 `project.godot` 열기
2. **F5** 또는 재생 버튼으로 실행
3. **키보드**: **A** 왼손 펀치, **D** 오른손 펀치 / **Q** 왼쪽 어퍼컷, **E** 오른쪽 어퍼컷 / **Z**·**C** 보조 펀치(왼·오) / **스페이스** 가드(누르고 있는 동안)

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
