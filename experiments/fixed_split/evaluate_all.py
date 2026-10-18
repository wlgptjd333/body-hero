# -*- coding: utf-8 -*-
"""재실험 모델(증강 수정) 전체 평가: 정확도, 유지 구간 안정성(EMA 포함), 후처리 시뮬레이션,
동작 전환 응답, 파라미터 수, CPU 추론 시간. 학습은 하지 않는다."""
import os, json, glob, time, math
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf
tf.config.threading.set_intra_op_parallelism_threads(8)

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.environ.get("BH_RESULTS", os.path.join(HERE, "results"))
OUT_DIR = os.environ.get("BH_OUT", HERE)
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
ATT = {2, 3, 4, 5}
THR = {0: .95, 1: .95, 2: .88, 3: .88, 4: .90, 5: .90, 6: .95}
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}

pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X_all = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
va = json.load(open(os.path.join(R, "recording_split.json")))["validation_record_ids"]
assert all("impact_idx" not in meta[r] or meta[r]["impact_idx"] is None for r in va)


def frames(rid):
    r = meta[rid]
    return X_all[r["start_index"]:r["start_index"] + r["frame_count"]]


def windows(seq, L):
    return np.stack([seq[t - L + 1:t + 1] for t in range(L - 1, len(seq))])


def sim(P, L):
    act = None; ema = None; cand = None; cnt = 0; ev = []; st = []
    for k, p in enumerate(P):
        t = k + L - 1
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= THR[c] and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= THR[c]:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= CONF[c]:
                    act = c; ev.append((t, c))
            else:
                cand = None; cnt = 0
        st.append(0 if act is None else act)
    return np.array(st), ev


none_ids = [r for r in va if meta[r]["label"] == "none"]
act_ids = [r for r in va if meta[r]["label"] != "none"]
H = 30
pairs = [(none_ids[i % len(none_ids)], a) for i, a in enumerate(act_ids)]
out = {}
for f in sorted(glob.glob(os.path.join(R, "result_*.json"))):
    res = json.load(open(f))
    arch, L, seed = res["architecture"], int(res["seq_len"]), int(res["seed"])
    name = f"{arch}_seq{L}_seed{seed}"
    m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
    probs = np.load(os.path.join(R, f"probabilities_{name}.npy"))
    # ---- 유지 구간 분석
    i = 0; sw = []; hold = []; perfect = 0; ema_true = []; dips = 0; nfr = 0; ema_sw = 0
    raw_fa = 0; pp_fa = 0; raw_ev = []; pp_ev = []
    for r in va:
        n = meta[r]["frame_count"] - L + 1
        Q = probs[i:i + n]; i += n
        y = C.index(meta[r]["label"])
        a = Q.argmax(1)
        sw.append(int((a[1:] != a[:-1]).sum())); hold.append((a[n // 2:] == y).mean()); perfect += int((a == y).all())
        e = None; prev = None
        for p in Q:
            e = p.copy() if e is None else .7 * p + .3 * e
            ema_true.append(e[y]); nfr += 1; dips += e[y] < 0.60
            ae = int(e.argmax())
            if prev is not None and ae != prev: ema_sw += 1
            prev = ae
        ron = [a[t] for t in range(len(a)) if a[t] in ATT and (t == 0 or a[t - 1] != a[t])]
        _, ev = sim(Q, L); pev = [c for _, c in ev if c in ATT]
        if y == 0: raw_fa += len(ron); pp_fa += len(pev)
        if y in ATT: raw_ev.append(len(ron)); pp_ev.append(len(pev))
    assert i == len(probs), (name, i, len(probs))
    # ---- 전환 응답
    on_pp, rel_pp, on_raw = [], [], []
    Won = np.concatenate([windows(np.concatenate([frames(n)[-H:], frames(a)[:H]]), L) for n, a in pairs])
    Woff = np.concatenate([windows(np.concatenate([frames(a)[-H:], frames(n)[:H]]), L) for n, a in pairs])
    Pon = m.predict(Won, batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
    Poff = m.predict(Woff, batch_size=4096, verbose=0).reshape(len(pairs), -1, 7)
    ts = np.arange(L - 1, 2 * H)
    for (n, a), P1, P2 in zip(pairs, Pon, Poff):
        y = C.index(meta[a]["label"])
        hit = [t for t, c in zip(ts, P1.argmax(1)) if t >= H and c == y]
        on_raw.append(hit[0] - H if hit else np.nan)
        _, ev = sim(P1, L)
        e2 = [t for t, c in ev if t >= H and c == y]
        on_pp.append(e2[0] - H if e2 else np.nan)
        st2, _ = sim(P2, L)
        r2 = [t for t, s in zip(ts, st2) if t >= H and s == 0]
        rel_pp.append(r2[0] - H if r2 else np.nan)
    # ---- 추론 시간
    x1 = np.random.rand(1, L, 99).astype("float32")
    fn = tf.function(lambda z: m(z, training=False)); fn(x1)
    tt = []
    for _ in range(300):
        t0 = time.perf_counter(); fn(x1); tt.append((time.perf_counter() - t0) * 1000)
    out[name] = dict(arch=arch, L=L, seed=seed, params=int(m.count_params()),
                     accuracy=res["accuracy"], macro_f1=res["macro_f1"], f1_none=res["f1_none"],
                     epochs=res.get("epochs_trained"), train_sec=res.get("training_seconds"),
                     true_prob=float(res["mean_true_class_probability"]),
                     switches=float(np.mean(sw)), hold_acc=float(np.mean(hold)), perfect=perfect / len(va),
                     ema_true=float(np.mean(ema_true)), ema_dip=float(dips / nfr), ema_switch=ema_sw / len(va),
                     raw_fa=raw_fa, pp_fa=pp_fa, raw_ev=float(np.mean(raw_ev)), pp_ev=float(np.mean(pp_ev)),
                     pp_one=float(np.mean(np.array(pp_ev) == 1)), raw_one=float(np.mean(np.array(raw_ev) == 1)),
                     pp_miss=float(np.mean(np.array(pp_ev) == 0)),
                     onset_raw=float(np.nanmean(on_raw)), onset_pp=float(np.nanmean(on_pp)),
                     onset_miss=float(np.mean(np.isnan(on_pp))), release_pp=float(np.nanmean(rel_pp)),
                     latency_ms=float(np.median(tt)))
    print(name, round(out[name]["accuracy"] * 100, 2), flush=True)
    tf.keras.backend.clear_session()
json.dump(out, open(os.path.join(OUT_DIR, "evaluation_all.json"), "w"), indent=1)

# ---- 집계
groups = {}
for k, v in out.items():
    groups.setdefault((v["arch"], v["L"]), []).append(v)
summary = {}
for g, vs in sorted(groups.items()):
    s = {"n": len(vs), "params": vs[0]["params"]}
    for key in ["accuracy", "macro_f1", "f1_none", "true_prob", "switches", "hold_acc", "perfect", "ema_true", "ema_dip",
                "ema_switch", "raw_fa", "pp_fa", "raw_ev", "pp_ev", "pp_one", "raw_one", "pp_miss", "onset_raw",
                "onset_pp", "onset_miss", "release_pp", "latency_ms", "epochs", "train_sec"]:
        arr = np.array([v[key] for v in vs], float)
        s[key] = [float(arr.mean()), float(arr.std(ddof=1)) if len(arr) > 1 else 0.0]
    s["acc_by_seed"] = {v["seed"]: v["accuracy"] for v in vs}
    summary[f"{g[0]}_seq{g[1]}"] = s
json.dump(summary, open(os.path.join(OUT_DIR, "evaluation_summary.json"), "w"), indent=1)
for k, s in summary.items():
    print(k, "acc %.2f±%.2f" % (s["accuracy"][0] * 100, s["accuracy"][1] * 100), "params", s["params"],
          "ema_dip %.3f" % s["ema_dip"][0], "onset_pp %.2f" % s["onset_pp"][0], "release %.2f" % s["release_pp"][0],
          "pp_fa %.1f" % s["pp_fa"][0], "lat %.2f" % s["latency_ms"][0])
