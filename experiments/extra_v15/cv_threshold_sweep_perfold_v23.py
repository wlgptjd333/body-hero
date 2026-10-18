# -*- coding: utf-8 -*-
# v23: cv_threshold_sweep.py와 같은 절차를 겹별로 저장 (겹별 일관성 확인용)
"""묶음 단위 교차검증 예측으로 진입 임계값별 운영점 비교 (GAP·LSTM 4프레임, MLP 1프레임과 4프레임 확률 평균).
Precise 값은 GAP으로 조정되었으므로, 모델마다 임계값을 따로 골랐을 때의 결과를 처음 보는 녹화 묶음에서 확인한다.
- 오발동: 시험 대기 녹화본 189개(5겹 합계)에서 발생한 공격 이벤트 수
- 지연·미발동: 각 겹의 시험 녹화본으로 만든 대기→동작 전환 시퀀스(후처리 후)
- 각 모델의 '맞춤 임계값': 공격 미발동이 5% 이하인 임계값 중 오발동이 가장 적은 값
학습 없음."""
import os, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "eval_groupcv.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "eval_groupcv.py")}
exec(src[:src.index("out = {}")], g)
tf, R, C, ATT, H, meta, frames, windows = g["tf"], g["R"], g["C"], g["ATT"], g["H"], g["meta"], g["frames"], g["windows"]
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}
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
    c = np.cumsum(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0); return (c[k:] - c[:-k]) / k


variants = [("GAP 4프레임", "gap", 4, 1), ("LSTM 4프레임", "lstm", 4, 1), ("LSTM 3프레임", "lstm", 3, 1), ("LSTM 2프레임", "lstm", 2, 1), ("GAP 2프레임", "gap", 2, 1), ("GAP 3프레임", "gap", 3, 1)]
res = {}
for label, arch, L, avg in variants:
    perfold = {}
    for f in range(5):
        acc = {T: [0, [], 0, 0] for T in TS}
        name = f"{arch}_seq{L}_fold{f}"
        r = json.load(open(os.path.join(R, f"result_{name}.json"))); te = r["test_record_ids"]
        P = np.load(os.path.join(R, f"probabilities_{name}.npy"))
        hold = []; i = 0
        for rid in te:
            n = meta[rid]["frame_count"] - L + 1
            Q = P[i:i + n]; i += n
            if avg > 1: Q = mavg(Q, avg)
            hold.append((C.index(meta[rid]["label"]), Q))
        none_ids = [x for x in te if meta[x]["label"] == "none"]; act = [x for x in te if meta[x]["label"] != "none"]
        pairs = [(none_ids[k % len(none_ids)], a) for k, a in enumerate(act)]
        m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
        Pon = m.predict(np.concatenate([windows(np.concatenate([frames(n)[-H:], frames(a)[:H]]), L) for n, a in pairs]),
                        batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
        tf.keras.backend.clear_session()
        Lw = L if avg == 1 else avg
        for T in TS:
            for y, Q in hold:
                if y == 0: acc[T][0] += sum(1 for _, c in sim(Q, Lw, T) if c in ATT)
            for (n, a), P1 in zip(pairs, Pon):
                y = C.index(meta[a]["label"])
                if y not in ATT: continue
                Pq = mavg(P1, avg) if avg > 1 else P1
                e = [t for t, c in sim(Pq, Lw, T) if t >= H and c == y]
                acc[T][3] += 1
                if e: acc[T][1].append(e[0] - H)
                else: acc[T][2] += 1
        perfold[f] = {str(T): {"false_attacks": acc[T][0], "onset_frames_sum": float(np.sum(acc[T][1])), "onset_n": len(acc[T][1]),
                           "miss": acc[T][2], "n": acc[T][3]} for T in TS}
    res[label] = perfold
    print(label, flush=True)
json.dump(res, open(os.path.join(HERE, "eval_v23", "cv_threshold_sweep_perfold_v23.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
