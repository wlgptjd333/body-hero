# Webcam ML: Seq 학습 증강 · seq_len · Architecture

## Motivation

게임에 쓸 ML 모델을 학습할 때 어떤 증강, seq_len, architecture를 쓸지 반복 실험.
이 문서는 최종 확정 결정을 기록한다.

## 결정 요약

| 항목 | 최종 결정 | 근거 |
|------|-----------|------|
| seq_len | **4** | 2대비 +1.06%, 1대비 +2.33%. 특히 none recall 92%→97.9% (transition 오인 필터링) |
| Architecture | **Conv1D(64,k=3)→GAP→Dense(7)** | LSTM 불필요. Conv→GAP이 더 적은 params(20K)로 LSTM(32K)를 항상 이김 |
| Aug: noise | σ=0.03 사용 | |
| Aug: scale | ±20% 사용 | 거리 변동 robustness |
| Aug: flip | 사용 | 좌우반전 + L/R 라벨스왑, L/R 균형에 효과적 |
| Aug: rotation | 사용 안 함 | landmark 상대좌표, 오히려 왜곡 |
| Aug: translation | 사용 안 함 | landmark 상대좌표 |
| Aug: temporal | 사용 안 함 | 녹화가 이미 단일동작 |
| L/R oversample | 사용 | 소수 클래스 복제 |

## 상세 근거

### 1. Temporal smoothing 효과 (seq_len=4)

4프레임(132ms) 버퍼로 transition frame(준비→동작 사이)의 오인식을 필터링.
가장 큰受益: none recall 92%→97.9%. 가드/펀치/어퍼 사이의 애매한 프레임을
4프레임 평균으로 안정화.

### 2. Conv1D → GAP이 LSTM보다 우월

같은 Conv1D front-end에서:
- LSTM(32K params): 더 느리고, 더 많은 params, 더 낮은 accuracy
- GAP(20K params): 더 빠르고, 더 적은 params, 더 높은 accuracy

이유: Conv1D(k=3,padding="same")의 temporal blending으로 temporal feature 추출이 이미 충분.
LSTM의 gating mechanism은 4 time step에서는 over-parameterization.

### 3. 증강

- Noise + scale: 필수. 카메라 노이즈 + 거리 변동 대응.
- Flip: L/R 데이터 불균형 해소. 실험 결과 +0.69% 향상.
- Rotation/translation/temporal masking: 불필요 (landmark 상대좌표, 단일동작 데이터 특성).

## 검증 실험

Full ablation 결과: `docs/experiments/2026-05-18-ablation-controlled.md`

### 최종 선정 모델 성능

| 모델 | 정확도 | none recall | guard precision | 학습시간 |
|------|--------|-------------|----------------|---------|
| Conv1D(64)→GAP, seq_len=4 | **97.53%** | **97.9%** | 97.1% | 247s |

### 로드 우선순위

```
pose_classifier_seq_len4.keras  →  SEQ_LEN=4 (우선, ADR-0002)
pose_classifier_seq.keras       →  SEQ_LEN=8 (폴백)
pose_classifier.keras           →  가드 보조 (단일 프레임 폴백)
```

## Inference-time 안정화 기법

| 기법 | 적용 | 설명 |
|------|------|------|
| EMA logit smoothing (α=0.7) | ✅ | softmax frame-by-frame EMA. flicker 제거, latency 거의 0 |
| Confidence hysteresis | ✅ | enter threshold(0.80) > exit threshold(0.35). 몸 흔들림에도 상태 유지 |
| Upper velocity gate | ✅ | 어퍼만 실제 landmark 움직임 감지 후 인식. 정지자세 오인 방지 |
| Per-side cooldown | ✅ | 같은 손 120ms 간격, 반대손은 100ms. L→R→L 콤보 허용 |
| Attack rearm | ✅ | 1프레임 비공격 후 재장전. 더블트리거 방지 |
| Action-specific thresholds | 3티어 | none/guard(0.90) > upper(0.85) > punch(0.80) |

자세한 전체 적용 기술 목록: `docs/experiments/2026-05-18-paper-design-decisions.md`
