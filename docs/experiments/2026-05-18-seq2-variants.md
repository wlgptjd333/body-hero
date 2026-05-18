# seq_len=2 변형 실험 (2026-05-18)

Conv1D(64)+LSTM(64) baseline, 녹화 단위 holdout(20%), 동일 split.

## 실험 1: seq_len 비교 (baseline 증강)

| 모델 | 정확도 | punch_r recall | squat precision |
|------|--------|---------------|----------------|
| seq_len=1 (Dense) | 95.31% | 87.1% | 92.6% |
| **seq_len=2 (Conv1D+LSTM)** | **96.24%** | **92.7%** | **97.0%** |
| seq_len=4 (Conv1D+LSTM) | 95.75% | 87.7% | 98.6% |

코드: `tools/compare_seq_len_realistic.py`

## 실험 2: 증강 변형 (seq_len=2)

| # | 실험 | 정확도 | baseline 대비 |
|---|------|--------|---------------|
| 1 | Baseline (noise.03+scale20%) | 96.12% | — |
| 2 | +Flip augmentation | **96.81%** | **+0.69%** |
| 3 | Higher noise (0.05) | 96.21% | +0.09% |
| 4 | Scale ±30% | 95.60% | -0.52% |
| 5 | Landmark dropout (0.05) | 95.89% | -0.23% |

## 실험 3: 아키텍처 변형 (seq_len=2, baseline 증강)

| # | 실험 | 정확도 | baseline 대비 |
|---|------|--------|---------------|
| 1 | Baseline (Conv64+LSTM64) | 96.12% | — |
| 6 | Conv1D 128 + LSTM 64 | 95.23% | -0.89% |
| 7 | Conv1D 64 + LSTM 128 | 95.49% | -0.63% |
| 8 | Conv128 + LSTM128 | 95.60% | -0.52% |
| 9 | Kernel 5 + 2xConv | 95.78% | -0.34% |

## 최종 확정 구성

| 항목 | 값 |
|------|-----|
| seq_len | 2 |
| Architecture | Conv1D(64, k=3) + BN + Drop(0.25) + LSTM(64) + Drop(0.3) |
| Augmentation | Gaussian noise(σ=0.03) + scale(±20%) + horizontal flip + L/R swap |
| 학습 | Adam(1e-3), EarlyStopping(val_loss, patience=15), ReduceLROnPlateau |
| 균형 | class_weight balanced + L/R pair oversample(max_ratio=6) |

근거: ADR-0002
