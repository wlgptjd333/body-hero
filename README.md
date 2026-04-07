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
venv_ml\Scripts\python.exe collect_pose_data.py
venv_ml\Scripts\python.exe train_pose_classifier_seq.py
venv_ml\Scripts\python.exe pose_server.py
```
`collect_pose_data.py`는 **기본으로 매 녹화·백스페이스 직후** `pose_data.json`과 `pose_recordings_meta.json`을 디스크에 저장합니다(Q 전 크래시 대비). 끄려면 `--no-autosave`.

`train_pose_classifier_seq.py`는 기본 **좌우 반전 증강**(L/R 라벨 스왑) + **잽/어퍼/훅 L:R 쌍 소수 오버샘플**을 켭니다. 예전 모델은 `upper_l`/`upper_r` 혼동이 나기 쉬우니 **재학습**을 권장합니다.

**L/R 헷갈림 점검·일괄 학습 (잽·어퍼·훅 공통):**
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe report_pose_lr_balance.py
venv_ml\Scripts\python.exe train_pose_lr_focused.py
```
- `report_pose_lr_balance.py`: 프레임·시퀀스 기준으로 `jab_l`/`jab_r`, `upper_l`/`upper_r`, `hook_l`/`hook_r` 개수 비율 출력.
- **메타와 `pose_data.json` 라벨이 어긋남** (콘솔 녹화 횟수는 정상인데 프레임에 어퍼/훅이 없음 등): `venv_ml\Scripts\python.exe relabel_pose_with_collect.py` → 메타 구간·누른 키 기준으로 랜드마크는 유지하고 라벨만 `collect` 로직으로 재생성. 먼저 `venv_ml\Scripts\python.exe relabel_pose_with_collect.py --dry-run` 권장. `start_index` 유지는 `--in-place`.
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

**ML 없이 테스트만 (휴리스틱 판정):** `venv_ml` 없이도 되면 시스템 `python`으로 `udp_send_webcam.py` 실행 가능. 가상환경을 쓰려면 `venv_ml\Scripts\python.exe udp_send_webcam.py` — 서버·학습 없이 동작 확인용.

**녹화 데이터 삭제:**
- **녹화 중**: **Backspace** → 방금 녹화한 1회만 취소 (Q로 종료 시 반영).
- **저장된 파일에서**: `venv_ml\Scripts\python.exe delete_pose_recordings.py --last 1` (마지막 1회 삭제). `--last 5`면 5회. `--dry-run`이면 저장 없이 확인만.

**마우스로 글러브 테스트:**
```cmd
cd c:\Users\User\Documents\body-hero\tools
venv_ml\Scripts\python.exe udp_send_mouse.py
```
(venv 없이 테스트만 할 때는 `python udp_send_mouse.py` 도 가능.)

## 빠른 실행

1. **Godot 4.6**으로 `project.godot` 열기
2. **F5** 또는 재생 버튼으로 실행
3. **키보드**: **A** 왼손 잽, **D** 오른손 잽 / **Q** 왼쪽 어퍼컷, **E** 오른쪽 어퍼컷 / **Z** 왼손 훅, **C** 오른손 훅 / **스페이스** 가드(누르고 있는 동안)

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
