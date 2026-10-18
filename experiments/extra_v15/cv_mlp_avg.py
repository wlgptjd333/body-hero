# -*- coding: utf-8 -*-
"""묶음 단위 교차검증: 1프레임 MLP 확률을 최근 4프레임 평균한 기준선의 정확도·오발동·지연. 학습 없음."""
import os, json, numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_groupcv.py"), encoding="utf8").read()
g = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_groupcv.py")}
exec(src[:src.index("out = {}")], g)
tf, np_, R, C, ATT, H, meta, frames, windows, sim = g["tf"], g["np"], g["R"], g["C"], g["ATT"], g["H"], g["meta"], g["frames"], g["windows"], g["sim"]
def mavg(P, k):
    c = np.cumsum(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0); return (c[k:] - c[:-k]) / k
res = []
for f in range(5):
    r = json.load(open(os.path.join(R, f"result_mlp_seq1_fold{f}.json"))); te = r["test_record_ids"]
    P = np.load(os.path.join(R, f"probabilities_mlp_seq1_fold{f}.npy"))
    i = 0; yt = []; yp = []; fa = 0
    for rid in te:
        n = meta[rid]["frame_count"]; Q = mavg(P[i:i + n], 4); i += n
        y = C.index(meta[rid]["label"]); yt += [y] * len(Q); yp += Q.argmax(1).tolist()
        if y == 0: fa += sum(1 for _, c in sim(Q, 4)[1] if c in ATT)
    m = tf.keras.models.load_model(os.path.join(R, f"model_mlp_seq1_fold{f}.keras"), compile=False)
    none_ids = [x for x in te if meta[x]["label"] == "none"]; act = [x for x in te if meta[x]["label"] != "none"]
    pairs = [(none_ids[k % len(none_ids)], a) for k, a in enumerate(act)]
    Pon = m.predict(np.concatenate([windows(np.concatenate([frames(n)[-H:], frames(a)[:H]]), 1) for n, a in pairs]), batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
    on = []
    for (n, a), P1 in zip(pairs, Pon):
        y = C.index(meta[a]["label"]); e = [t for t, c in sim(mavg(P1, 4), 4)[1] if t >= H and c == y]; on.append(e[0] - H if e else np.nan)
    res.append(((np.array(yt) == np.array(yp)).mean(), fa, np.nanmean(on)))
    tf.keras.backend.clear_session()
a = np.array(res)
out = dict(acc_mean=float(a[:, 0].mean()), acc_sd=float(a[:, 0].std(ddof=1)), pp_fa_total=int(a[:, 1].sum()), onset_ms=float(a[:, 2].mean() * 1000 / 30), by_fold=a.tolist())
print(out); json.dump(out, open("groupcv_mlp_avg4.json", "w"), indent=1)
