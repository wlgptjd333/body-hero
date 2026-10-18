# -*- coding: utf-8 -*-
# v23: 재실험_2x2_증강수정/threshold_sweep.py 복사본. 3프레임 모델(재실험_추가_v15/results)에 같은 절차 적용. BH_RESULTS로 결과 폴더 지정.
"""진입 임계값을 바꿔 가며 모델별 운영점(오발동 대 반응 지연)을 비교한다. 학습 없음."""
import os, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "재실험_2x2_증강수정")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_v23")
src = open(os.path.join(HERE, "evaluate_all.py"), encoding="utf8").read()
src = src[:src.index("none_ids = [")]
g = {"__file__": os.path.join(HERE, "evaluate_all.py")}
exec(src, g)
C, ATT, meta, va, frames, R = g["C"], g["ATT"], g["meta"], g["va"], g["frames"], g["R"]
H = 30
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}
none_ids = [r for r in va if meta[r]["label"] == "none"]
act_ids = [r for r in va if meta[r]["label"] != "none"]
pairs = [(none_ids[i % len(none_ids)], a) for i, a in enumerate(act_ids)]
TS = [0.70, 0.80, 0.88, 0.95, 0.98]


def sim(P, L, T):
    act = None; ema = None; cand = None; cnt = 0; ev = []
    for k, p in enumerate(P):
        t = k + L - 1
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= T and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= T:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= CONF[c]:
                    act = c; ev.append((t, c))
            else:
                cand = None; cnt = 0
    return ev


def mavg(P, k):
    c = np.cumsum(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0)
    return (c[k:] - c[:-k]) / k


def windows(seq, L):
    return np.stack([seq[t - L + 1:t + 1] for t in range(L - 1, len(seq))])


variants = [("GAP 3프레임", "gap_seq3", 3, 1), ("LSTM 3프레임", "lstm_seq3", 3, 1)]
res = {}
for label, key, L, avg in variants:
    per = {T: [] for T in TS}
    for seed in range(42, 47):
        name = f"{key}_seed{seed}"
        m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
        probs = np.load(os.path.join(R, f"probabilities_{name}.npy"))
        Lw = L if avg == 1 else avg
        hold = []
        i = 0
        for r in va:
            n = meta[r]["frame_count"] - L + 1
            Q = probs[i:i + n]; i += n
            if avg > 1: Q = mavg(Q, avg)
            hold.append((C.index(meta[r]["label"]), Q))
        Pon = m.predict(np.concatenate([windows(np.concatenate([frames(n)[-H:], frames(a)[:H]]), L) for n, a in pairs]),
                        batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
        for T in TS:
            fa = 0; one = []; on = []
            for y, Q in hold:
                ev = [c for _, c in sim(Q, Lw, T) if c in ATT]
                if y == 0: fa += len(ev)
                elif y in ATT: one.append(len(ev) == 1)
            for (n, a), P1 in zip(pairs, Pon):
                y = C.index(meta[a]["label"])
                P = mavg(P1, avg) if avg > 1 else P1
                e = [t for t, c in sim(P, Lw, T) if t >= H and c == y]
                on.append(e[0] - H if e else np.nan)
            per[T].append((fa, np.mean(one), np.nanmean(on), np.mean(np.isnan(on))))
        tf.keras.backend.clear_session()
    res[label] = {str(T): [float(np.mean([x[j] for x in per[T]])) for j in range(4)] for T in TS}
    print(label, {T: [round(v, 3) for v in res[label][str(T)]] for T in map(str, TS)}, flush=True)
json.dump(res, open(os.path.join(OUT, "threshold_sweep_v23.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
