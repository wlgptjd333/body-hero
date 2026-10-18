# -*- coding: utf-8 -*-
"""1프레임 MLP의 출력 확률을 최근 k프레임 평균한 경우(k=2,4)를 GAP·LSTM과 같은 기준으로 평가한다. 학습 없음."""
import os, json, glob
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf
import importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ev", os.path.join(HERE, "evaluate_all.py"))
src = open(os.path.join(HERE, "evaluate_all.py"), encoding="utf8").read()
src = src[:src.index("none_ids = [")]  # 공통 정의만 사용
g = {"__file__": os.path.join(HERE, "evaluate_all.py")}
exec(src, g)
C, ATT, meta, va, frames, sim = g["C"], g["ATT"], g["meta"], g["va"], g["frames"], g["sim"]
R = g["R"]
H = 30
none_ids = [r for r in va if meta[r]["label"] == "none"]
act_ids = [r for r in va if meta[r]["label"] != "none"]
pairs = [(none_ids[i % len(none_ids)], a) for i, a in enumerate(act_ids)]


def mavg(P, k):
    c = np.cumsum(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0)
    return (c[k:] - c[:-k]) / k  # 길이 len-k+1, window end = k-1 ...


out = {}
for k in (2, 4):
    rows = []
    for seed in range(42, 47):
        name = f"mlp_seq1_seed{seed}"
        m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
        probs = np.load(os.path.join(R, f"probabilities_{name}.npy"))
        i = 0; acc_n = 0; tot = 0; sw = []; ema_true = []; dips = 0; nfr = 0; raw_fa = 0; pp_fa = 0; pp_ev = []
        for r in va:
            n = meta[r]["frame_count"]
            Q1 = probs[i:i + n]; i += n
            Q = mavg(Q1, k)
            y = C.index(meta[r]["label"])
            a = Q.argmax(1)
            acc_n += int((a == y).sum()); tot += len(a)
            sw.append(int((a[1:] != a[:-1]).sum()))
            e = None
            for p in Q:
                e = p.copy() if e is None else .7 * p + .3 * e
                ema_true.append(e[y]); nfr += 1; dips += e[y] < 0.6
            ron = [a[t] for t in range(len(a)) if a[t] in ATT and (t == 0 or a[t - 1] != a[t])]
            _, ev = sim(Q, k); pev = [c for _, c in ev if c in ATT]
            if y == 0: raw_fa += len(ron); pp_fa += len(pev)
            if y in ATT: pp_ev.append(len(pev))
        assert i == len(probs)
        on_pp, rel_pp = [], []
        seqs_on = [np.concatenate([frames(n)[-H:], frames(a)[:H]]) for n, a in pairs]
        seqs_off = [np.concatenate([frames(a)[-H:], frames(n)[:H]]) for n, a in pairs]
        Pon = m.predict(np.concatenate(seqs_on)[:, None, :], batch_size=4096, verbose=0).reshape(len(pairs), 2 * H, 7)
        Poff = m.predict(np.concatenate(seqs_off)[:, None, :], batch_size=4096, verbose=0).reshape(len(pairs), 2 * H, 7)
        ts = np.arange(k - 1, 2 * H)
        for (n, a), P1, P2 in zip(pairs, Pon, Poff):
            y = C.index(meta[a]["label"])
            _, ev = sim(mavg(P1, k), k)
            e2 = [t for t, c in ev if t >= H and c == y]
            on_pp.append(e2[0] - H if e2 else np.nan)
            st2, _ = sim(mavg(P2, k), k)
            r2 = [t for t, s in zip(ts, st2) if t >= H and s == 0]
            rel_pp.append(r2[0] - H if r2 else np.nan)
        rows.append(dict(acc=acc_n / tot, switches=np.mean(sw), ema_true=np.mean(ema_true), ema_dip=dips / nfr,
                         raw_fa=raw_fa, pp_fa=pp_fa, pp_one=np.mean(np.array(pp_ev) == 1),
                         onset_pp=np.nanmean(on_pp), release_pp=np.nanmean(rel_pp)))
        tf.keras.backend.clear_session()
    agg = {key: [float(np.mean([r[key] for r in rows])), float(np.std([r[key] for r in rows], ddof=1))] for key in rows[0]}
    out[f"mlp1_avg{k}"] = agg
    print(k, {kk: round(v[0], 4) for kk, v in agg.items()})
json.dump(out, open(os.path.join(HERE, "evaluation_mlp_avg.json"), "w"), indent=1)
