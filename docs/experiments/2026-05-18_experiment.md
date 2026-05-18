# seq_len 비교 실험 (2026-05-18)

날짜: 2026-05-18
데이터: C:\Users\user\Documents\body-hero\tools\pose_data.json
분할: 녹화 단위 holdout 20%

## 결과 요약

| 실험 | 정확도 | 시간 | Train | Test |
|------|--------|------|-------|------|
| seq_len=2 +flip | 95.37% | 231.4s | 43542 | 3481 |

## Recall 비교

| 동작 | seq_len=2 +flip |
|------|---|
| none | 92.1% |
| guard | 100.0% |
| punch_l | 94.3% |
| punch_r | 87.7% |
| upper_l | 99.3% |
| upper_r | 97.6% |
| squat | 100.0% |

## Precision 비교

| 동작 | seq_len=2 +flip |
|------|---|
| none | 99.8% |
| guard | 91.5% |
| punch_l | 94.7% |
| punch_r | 99.2% |
| upper_l | 93.8% |
| upper_r | 91.4% |
| squat | 96.4% |
