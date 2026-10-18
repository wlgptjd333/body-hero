# -*- coding: utf-8 -*-
"""묶음 단위 교차검증 결과 평가: 정확도, 판정 변화, 후처리(Precise) 오발동, 동작 전환 응답.
evaluate_all.py와 같은 정의를 쓰되, 각 겹의 시험 녹화본만 사용한다. 학습 없음."""
import os, json, glob
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf
tf.config.threading.set_intra_op_parallelism_threads(2)
from sklearn.metrics import f1_score, confusion_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results_groupcv")
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
ATT = {2, 3, 4, 5}
THR = {0: .95, 1: .95, 2: .88, 3: .88, 4: .90, 5: .90, 6: .95}
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}
H = 30
pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X_all = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]


def frames(rid):
    r = meta[rid]; return X_all[r["start_index"]:r["start_index"] + r["frame_count"]]


def windows(seq, L):
    return np.stack([seq[t - L + 1:t + 1] for t in range(L - 1, len(seq))])


def sim(P, L, thr=THR):
    act = None; ema = None; cand = None; cnt = 0; ev = []; st = []
    for k, p in enumerate(P):
        t = k + L - 1
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= thr[c] and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= thr[c]:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= CONF[c]:
                    act = c; ev.append((t, c))
            else:
                cand = None; cnt = 0
        st.append(0 if act is None else act)
    return np.array(st), ev


out = {}
for f in sorted(glob.glob(os.path.join(R, "result_*.json"))):
    res = json.load(open(f)); arch, L, fold = res["arch"], res["L"], res["fold"]
    name = f"{arch}_seq{L}_fold{fold}"
    P = np.load(os.path.join(R, f"probabilities_{name}.npy"))
    te = res["test_record_ids"]
    i = 0; sw = []; raw_fa = 0; pp_fa = 0; pp_ev = []; ytrue = []; ypred = []; rec_acc = {}
    for r in te:
        n = meta[r]["frame_count"] - L + 1
        Q = P[i:i + n]; i += n
        y = C.index(meta[r]["label"]); a = Q.argmax(1)
        ytrue += [y] * n; ypred += a.tolist(); rec_acc[r] = float((a == y).mean())
        sw.append(int((a[1:] != a[:-1]).sum()))
        ron = [a[t] for t in range(len(a)) if a[t] in ATT and (t == 0 or a[t - 1] != a[t])]
        _, ev = sim(Q, L); pev = [c for _, c in ev if c in ATT]
        if y == 0: raw_fa += len(ron); pp_fa += len(pev)
        if y in ATT: pp_ev.append(len(pev))
    assert i == len(P), name
    none_ids = [r for r in te if meta[r]["label"] == "none"]
    act_ids = [r for r in te if meta[r]["label"] != "none"]
    pairs = [(none_ids[k % len(none_ids)], a) for k, a in enumerate(act_ids)]
    m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
    Pon = m.predict(np.concatenate([windows(np.concatenate([frames(n)[-H:], frames(a)[:H]]), L) for n, a in pairs]),
                    batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
    Poff = m.predict(np.concatenate([windows(np.concatenate([frames(a)[-H:], frames(n)[:H]]), L) for n, a in pairs]),
                     batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
    tf.keras.backend.clear_session()
    on_pp, rel_pp, on_miss = [], [], []
    for (n, a), P1, P2 in zip(pairs, Pon, Poff):
        y = C.index(meta[a]["label"])
        _, ev = sim(P1, L)
        e2 = [t for t, c in ev if t >= H and c == y]
        on_pp.append(e2[0] - H if e2 else np.nan)
        st2, _ = sim(P2, L)
        ts = np.arange(L - 1, 2 * H)
        r2 = [t for t, s in zip(ts, st2) if t >= H and s == 0]
        rel_pp.append(r2[0] - H if r2 else np.nan)
    ytrue = np.array(ytrue); ypred = np.array(ypred)
    out[name] = dict(arch=arch, L=L, fold=fold, params=res["params"], accuracy=float((ytrue == ypred).mean()),
                     macro_f1=float(f1_score(ytrue, ypred, average="macro")), n_test_rec=len(te),
                     n_none=len(none_ids), switches=float(np.mean(sw)), raw_fa=raw_fa, pp_fa=pp_fa,
                     pp_one=float(np.mean(np.array(pp_ev) == 1)), pp_miss=float(np.mean(np.array(pp_ev) == 0)),
                     onset_pp=float(np.nanmean(on_pp)), onset_miss=float(np.mean(np.isnan(on_pp))),
                     release_pp=float(np.nanmean(rel_pp)), rec_acc=rec_acc,
                     cm=confusion_matrix(ytrue, ypred, labels=range(7)).tolist())
    print(name, "acc %.2f" % (out[name]["accuracy"] * 100), "fa", raw_fa, "->", pp_fa, flush=True)
json.dump(out, open(os.path.join(HERE, "groupcv_eval_all.json"), "w"), indent=1)

groups = {}
for k, v in out.items(): groups.setdefault(f"{v['arch']}_seq{v['L']}", []).append(v)
summ = {}
for g, vs in sorted(groups.items()):
    s = {"n_folds": len(vs), "params": vs[0]["params"]}
    for key in ["accuracy", "macro_f1", "switches", "pp_one", "pp_miss", "onset_pp", "onset_miss", "release_pp"]:
        a = np.array([v[key] for v in vs], float)
        s[key] = [float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else 0.0]
    s["raw_fa_total"] = int(sum(v["raw_fa"] for v in vs)); s["pp_fa_total"] = int(sum(v["pp_fa"] for v in vs))
    s["none_total"] = int(sum(v["n_none"] for v in vs))
    s["acc_by_fold"] = {v["fold"]: round(v["accuracy"] * 100, 2) for v in vs}
    cm = np.sum([np.array(v["cm"]) for v in vs], axis=0); s["cm_total"] = cm.tolist()
    s["recall_by_class"] = {C[c]: round(float(cm[c, c] / cm[c].sum()) * 100, 2) for c in range(7)}
    summ[g] = s
    print(g, "acc %.2f±%.2f" % (s["accuracy"][0] * 100, s["accuracy"][1] * 100), "pp_fa", s["pp_fa_total"], "/", s["none_total"],
          "onset %.2f release %.2f" % (s["onset_pp"][0], s["release_pp"][0]), s["acc_by_fold"])
json.dump(summ, open(os.path.join(HERE, "groupcv_summary.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
