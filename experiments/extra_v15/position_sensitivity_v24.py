# -*- coding: utf-8 -*-
"""v24: 창 안의 위치별 민감도. 대기 녹화본의 창에서 한 위치의 프레임만 공격 자세 프레임으로 바꿨을 때
공격 클래스 확률(정답 공격 클래스)이 얼마나 오르는지를 위치별로 잰다. 고정 분할 검증 녹화본, 5개 시드 평균. 학습 없음."""
import os, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np, tensorflow as tf
HERE = os.path.dirname(os.path.abspath(__file__))
R0 = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results"); R1 = os.path.join(HERE, "results")
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
VA = json.load(open(os.path.join(R1, "recording_split.json")))["validation_record_ids"]
fr = lambda r: X[meta[r]["start_index"]:meta[r]["start_index"] + meta[r]["frame_count"]]
none_ids = [r for r in VA if meta[r]["label"] == "none"]
att_ids = [r for r in VA if meta[r]["label"] in ("punch_l", "punch_r", "upper_l", "upper_r")]
out = {}
for label, arch, L in [("GAP 4프레임", "gap", 4), ("LSTM 3프레임", "lstm", 3), ("LSTM 4프레임", "lstm", 4), ("GAP 3프레임", "gap", 3)]:
    per = []; base = []
    for s in range(42, 47):
        m = tf.keras.models.load_model(os.path.join(R1 if L == 3 else R0, f"model_{arch}_seq{L}_seed{s}.keras"), compile=False)
        Ws = []; ys = []
        for i, a in enumerate(att_ids):
            n = fr(none_ids[i % len(none_ids)]); A = fr(a)
            for t in range(10, 50, 8):
                Ws.append((n[t:t + L], A[t], C.index(meta[a]["label"])))
        W0 = np.stack([w for w, _, _ in Ws]); y = np.array([c for _, _, c in Ws])
        p0 = m.predict(W0, batch_size=4096, verbose=0)[np.arange(len(y)), y]
        row = []
        for j in range(L):
            W = W0.copy(); W[:, j] = np.stack([f for _, f, _ in Ws])
            row.append(float(m.predict(W, batch_size=4096, verbose=0)[np.arange(len(y)), y].mean()))
        per.append(row); base.append(float(p0.mean())); tf.keras.backend.clear_session()
    out[label] = {"base": round(float(np.mean(base)), 4), "by_position_oldest_to_newest": [round(float(v), 4) for v in np.mean(per, 0)]}
    print(label, out[label], flush=True)
json.dump(out, open(os.path.join(HERE, "stress_v24", "position_sensitivity_v24.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
