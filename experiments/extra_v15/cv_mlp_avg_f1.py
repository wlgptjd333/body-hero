# -*- coding: utf-8 -*-
"""묶음 교차검증: MLP + 4프레임 확률 평균의 Macro F1과 클래스별 재현율 (저장 예측 사용)."""
import json, numpy as np, os
from sklearn.metrics import f1_score
T = r"C:\Users\User\Documents\body-hero\tools"
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
def mavg(P, k):
    c = np.cumsum(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0); return (c[k:] - c[:-k]) / k
yt = []; yp = []; f1s = []
for f in range(5):
    r = json.load(open(f"results_groupcv/result_mlp_seq1_fold{f}.json")); P = np.load(f"results_groupcv/probabilities_mlp_seq1_fold{f}.npy"); i = 0; a = []; b = []
    for rid in r["test_record_ids"]:
        n = meta[rid]["frame_count"]; Q = mavg(P[i:i + n], 4); i += n; a += [C.index(meta[rid]["label"])] * len(Q); b += Q.argmax(1).tolist()
    f1s.append(f1_score(a, b, average="macro")); yt += a; yp += b
yt = np.array(yt); yp = np.array(yp)
print("F1 %.1f" % (np.mean(f1s) * 100), {C[c]: round(float((yp[yt == c] == c).mean() * 100), 1) for c in range(7)})
