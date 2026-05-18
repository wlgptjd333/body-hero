# Controlled Ablation: Dense vs Conv1D vs LSTM (2026-05-18)

동일 params(20K)로 architecture effect 분리. 녹화 단위 holdout 20%.

## 참가 모델

| # | 모델 | Input | Params |
|---|------|-------|--------|
| A | Dense 96→96→7 | 99 (1frame) | 20K |
| B | Dense concat 198→97→7 | 198 (2frame) | 20K |
| C | Conv64(k3)→GAP→Dense64→7 | (2,99) | 20K |
| D | Conv64(k3)→LSTM32→Dense64→7 | (2,99) | 32K |
| E | Conv64(k3)→GAP→Dense64→7 | (4,99) | 20K |
| F | Conv64(k3)→LSTM32→Dense64→7 | (4,99) | 32K |
| G | Dense concat 396→97→7 | 396 (4frame) | 40K |

## 전체 결과

| # | 모델 | 정확도 | none rec | punch_r rec | guard prec |
|---|------|--------|---------|-------------|------------|
| A | Dense (1frame) | 95.20% | 92.6% | 83.8% | 91.0% |
| B | Dense concat (2frame) | 96.01% | 92.2% | 85.0% | 99.3% |
| C | Conv→GAP (2frame) | 96.47% | 92.2% | **92.7%** | 99.2% |
| D | Conv→LSTM (2frame) | 95.81% | 91.1% | 90.8% | 90.4% |
| **E** | **Conv→GAP (4frame)** | **97.53%** | **97.9%** | 85.2% | 97.1% |
| F | Conv→LSTM (4frame) | 96.55% | 96.1% | 88.7% | 96.8% |
| G | Dense concat (4frame) | 96.76% | 92.0% | **94.0%** | 90.5% |

## 핵심 발견

1. **Temporal smoothing이 핵심**: 4프레임(132ms)에서 none recall이 92%→97.9%로 급등.
   transition frame 오인식이 4프레임 버퍼로 필터링됨.

2. **Conv1D > Dense**: Conv1D의 local connectivity가 landmark spatial structure 보존.
   같은 params로 Dense concat을 항상 이김.

3. **LSTM 불필요**: 모든 seq_len에서 LSTM이 GAP을 이기지 못함.
   Conv1D(k=3)의 temporal blending으로 충분. LSTM gate는 over-parameterization.

4. **seq_len=4 최적**: 2frame 대비 +1.06%, 1frame 대비 +2.33%. 4frame(132ms) latency OK.

## 최종 결정 구성

| 항목 | 값 |
|------|-----|
| seq_len | 4 |
| Architecture | Conv1D(64, k=3) → BN → Drop(0.25) → GAP → Drop(0.3) → Dense(7) |
| Params | ~20K |
| Augmentation | Gaussian noise(σ=0.03) + scale(±20%) + horizontal flip + L/R swap |
| Training | Adam(1e-3), patience=15, ReduceLROnPlateau(factor=0.5, patience=6) |
