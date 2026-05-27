# 포즈 인식 정확도 개선 트레이닝 가이드

## 개요

웹캡 → MediaPipe Pose → Keras 분류 모델(Conv1D) → UDP로 Godot 전송.

문제: **스쿼트 오탐지**(서 있는데 스쿼트로 인식) + **복싱 자세 오른손 펀치 미인식**(대각선 자세)

---

## 1. 기존 데이터 백업 (선택)

현재 데이터를 날리지 않고 새로 수집하려면 백업부터:

```bash
cd tools
python backup_pose_ml_session.py
```

`pose_ml_backup/` 폴더에 타임스탬프로 보관됨. 복구는 그 폴더에서 `tools/`로 파일 복사.

---

## 2. 데이터 수집

### 수집 실행

```bash
python collect_pose_data.py --camera-index 0 --camera-backend dshow --autosave
```

카메라 인덱스가 다르면 `--camera-index 1` 등으로 조정.

### 키 매핑

| 키 | 동작 |
|----|------|
| `0` | none (가만히 / 펀치 흉내) |
| `1` | guard |
| `2` | punch_l (왼손 직선) |
| `3` | punch_r (오른손 직선) |
| `4` | upper_l (왼손 어퍼) |
| `5` | upper_r (오른손 어퍼) |
| `6` | squat |
| `Q` | 종료 및 저장 |
| `Backspace` | 마지막 녹화 1회 삭제 |
| `A` | 자동저장 토글 |
| `T` | 녹화 길이 전환 (2초 ↔ 원래설정) |

### 수집 방법

1. 동작 실행 → 해당 숫자 키 누름
2. 1초 대기 후 2초 녹화 시작
3. 각 키 누름 = 1회 녹화. 연속 같은 동작 반복 금지.

### 권장 수집량

| 순서 | 동작 | 자세 설명 | 추가 필요 샘플 | 우선순위 |
|------|------|-----------|---------------|---------|
| 1 | `none` (0) | 가만히 서서 펀치 흉내만, 상체 움직임 O | 30회 | ★★★ |
| 2 | `none` (0) | 복싱 자세(대각선)로 가만히 서있기 | 20회 | ★★★ |
| 3 | `punch_r` (3) | 복싱 자세(왼발 앞)에서 오른손 직선 | 40~50회 | ★★★ |
| 4 | `punch_l` (2) | 복싱 자세(오른발 앞)에서 왼손 직선 | 30회 | ★★ |
| 5 | `squat` (6) | 천천히 앉기 + 빠르게 앉기 다양하게 | 20회 | ★★ |
| 6 | `punch_r` (3) | 정면에서 오른손 직선 (기존 보강) | 20회 | ★ |
| 7 | `punch_l` (2) | 정면에서 왼손 직선 (기존 보강) | 20회 | ★ |

**총 약 180회, ~6분 소요.**

#### none 수집 팁

`none`은 단순히 가만히 있는 게 아니라 **펀치를 하려다 말거나, 몸을 움직였는데 펀치는 아닌 상황**을 담아야 오탐지 방지에 효과적:

- 팔을 살짝 움직이지만 펀치는 안 날리기
- 복싱 자세에서 살짝 웨이트 쉬프트
- 가드 올렸다 내리기
- 상체 숙였다 일어나기 (스쿼트 오탐지 방지)

---

## 3. 데이터 균형 확인

```bash
python report_pose_lr_balance.py --seq-len 4
```

출력에서 `punch_l : punch_r` 비율이 1:1에 가까운지 확인.
너무 치우쳤으면 적은 쪽 추가 수집.

---

## 4. 모델 재학습

```bash
python train_pose_lr_focused.py --seq-len 4
```

3단계 자동 실행:
1. `report_pose_lr_balance.py` — L:R 균형 리포트
2. `train_pose_classifier_seq.py --seq-len 4` — 시퀀스 모델 (Conv1D+GAP)
3. `train_pose_classifier.py` — 가드 단일 프레임 폴백

완료 후 `pose_classifier_seq_len4.keras` 가 생성됨.

---

## 5. 실시간 테스트

```bash
python test_pose_live.py --camera-index 0 --camera-backend dshow
```

초록색 = 액션 인식, 흰색 = none. 복싱 자세에서 오른손 펀치 잘 뜨는지, 가만히 있을 때 스쿼트 안 뜨는지 확인.

---

## 6. 런타임 파라미터 튜닝

게임 실행 시 `udp_send_webcam_ml.py`에 전달. Godot의 `webcam_bridge_internal.gd`에서 args 수정.

### 스쿼트 오탐지 줄이기

| 파라미터 | 기본값 | 추천값 | 효과 |
|----------|--------|--------|------|
| `--full-body-squat` | 꺼짐 | **ON** | 하체 visibility + 엉덩이 하강 체크 |
| `--squat-confidence` | 0.93 | **0.95** | 스쿼트 확률 문턱 상향 |

게임 설정에서 "전신 스쿼트" 옵션 켜면 `--full-body-squat` 활성화됨.

### 펀치 감도 조정

| 파라미터 | 기본값 | 추천값 | 효과 |
|----------|--------|--------|------|
| `--punch-confidence` | 0.88 | **0.75~0.80** | 낮출수록 펀치 잘 인식, 오탐지 증가 |
| `--profile` | balanced | **precise** | 정확도 우선 (confirm frames 증가) |

### 프로필 설명

| 프로필 | 특징 |
|--------|------|
| `precise` | 정확도 최우선, 느린 연타 |
| `balanced` | 기본, 적당한 균형 |
| `rapid` | 빠른 연타, 약간 오탐지 감수 |
| `max_speed` | 최대 속도, 오탐지 가장 쉬움 |

### 디버그 출력

```
--debug-topk 5
```

화면에 softmax 상위 5개 클래스 확률 표시. 어떤 동작으로 인식되는지 실시간 확인 가능.

---

## 7. 자주 쓰는 전체 명령어 요약

```bash
# 1. 백업
python backup_pose_ml_session.py

# 2. 데이터 수집 (자동저장 켜기)
python collect_pose_data.py --camera-index 0 --camera-backend dshow --autosave

# 3. 균형 확인
python report_pose_lr_balance.py --seq-len 4

# 4. 학습
python train_pose_lr_focused.py --seq-len 4

# 5. 실시간 테스트
python test_pose_live.py --camera-index 0 --camera-backend dshow
```

---

## 8. 문제별 진단법

### 스쿼트 오탐지

```
--debug-topk 5
```

none/guard 상태에서 squat가 softmax 상위에 뜨는지 확인.
- squat 확률이 0.5 이상인데 none보다 높으면 → **데이터 문제** (none 데이터에 상체 움직임 부족)
- squat 확률이 0.3 이하인데도 게임에서 스쿼트 발생 → **임계값 문제** (`--squat-confidence` 상향)

### 오른손 펀치 미인식

```
--debug-topk 5
```

대각선 자세에서 punch_r softmax 확률 확인.
- punch_r이 상위 5위 안에 없으면 → **데이터 문제** (대각선 punch_r 데이터 부족)
- punch_r이 0.7~0.8인데 none으로 처리되면 → **임계값 문제** (`--punch-confidence` 하향)

---

## 9. Python 환경

`tools\python_embed\python.exe` (Embedded Python)을 사용합니다. 첫 실행 시 자동 다운로드되며, `tools/python_embed/`가 없으면 `tools/build_python_embed.bat`로 직접 빌드할 수 있습니다.
