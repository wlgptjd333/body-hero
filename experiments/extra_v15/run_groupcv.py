# -*- coding: utf-8 -*-
"""v15 추가 실험: 연속 녹화 묶음 단위 5겹 교차검증 (시험 데이터 분리).

- 묶음(group): pose_recordings_meta.json에서 같은 라벨이 연속으로 녹화된 구간 (70개).
  같은 자리에서 연달아 찍은 거의 같은 녹화본이 학습과 시험에 나뉘어 들어가지 않게 한다.
- 각 겹(fold): 시험 묶음은 학습과 조기 종료에 전혀 쓰지 않는다.
  남은 묶음 중 클래스별 약 20%(녹화본 수 기준)를 조기 종료용 검증 묶음으로 따로 뗀다.
- 학습 설정, 균형, 증강, 모델은 재실험_2x2_증강수정/run_experiment.py와 같다.
환경변수: BH_ARCH(mlp,gap,gapwide,lstm,gru), BH_SEQ, BH_FOLDS(0,1,2,3,4), BH_THREADS
"""
import os, json, time, random, gc
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf

TH = int(os.environ.get("BH_THREADS", "0"))
if TH > 0:
    tf.config.threading.set_intra_op_parallelism_threads(TH)
    tf.config.threading.set_inter_op_parallelism_threads(2)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results_groupcv")
os.makedirs(OUT, exist_ok=True)
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
EPOCHS, BATCH, LR = 120, 32, 1e-3
ES_PAT, LR_PAT, BAL, NOISE, SMIN, SMAX = 22, 7, 4.0, 0.03, 0.8, 1.2
K = 5

pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X_all = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]

# ---------------- 묶음과 겹 만들기 (결정적) ----------------
groups = []
for i, r in enumerate(meta):
    if not groups or meta[groups[-1][-1]]["label"] != r["label"]:
        groups.append([])
    groups[-1].append(i)
glabel = [meta[g[0]]["label"] for g in groups]


def assign(gids, k):
    """클래스별로 큰 묶음부터 녹화본 수가 가장 적은 칸에 넣는다."""
    out = [[] for _ in range(k)]
    for c in C:
        gs = sorted([g for g in gids if glabel[g] == c], key=lambda g: (-len(groups[g]), g))
        load = [0] * k
        for g in gs:
            j = int(np.argmin(load)); out[j].append(g); load[j] += len(groups[g])
    return out


folds = assign(list(range(len(groups))), K)
split_info = {"groups": groups, "group_label": glabel, "folds": folds, "inner": {}}
for f in range(K):
    rest = [g for j in range(K) if j != f for g in folds[j]]
    # 남은 묶음을 다시 5칸으로 나눠 그중 한 칸을 조기 종료용으로 쓴다 (클래스별 약 20%)
    inner = assign(rest, 5)
    es = list(inner[f % 5])
    for c in C:  # 조기 종료 칸에 없는 클래스는 남은 묶음 중 가장 작은 것을 하나 넣는다
        if not any(glabel[g] == c for g in es):
            cand = sorted([g for g in rest if glabel[g] == c], key=lambda g: (len(groups[g]), g))
            if len(cand) >= 2: es.append(cand[0])
    split_info["inner"][f] = {"early_stop_groups": sorted(es), "train_groups": sorted(set(rest) - set(es))}
json.dump(split_info, open(os.path.join(OUT, "groupcv_split.json"), "w"), indent=1)


def rec_ids(gs):
    return sorted(i for g in gs for i in groups[g])


def seqs(rids, L):
    X, y, rr = [], [], []
    for rid in rids:
        r = meta[rid]; F = X_all[r["start_index"]:r["start_index"] + r["frame_count"]]
        for t in range(L - 1, len(F)):
            X.append(F[t - L + 1:t + 1]); y.append(C.index(r["label"])); rr.append(rid)
    return np.asarray(X, np.float32), np.asarray(y, np.int64), np.asarray(rr)


LR_PAIRS = [(1, 4), (2, 5), (3, 6), (7, 8), (11, 12), (13, 14), (15, 16), (17, 18), (19, 20), (21, 22),
            (23, 24), (25, 26), (27, 28), (29, 30), (31, 32)]
FLIP = {2: 3, 3: 2, 4: 5, 5: 4}


def balance(X, y, seed):
    rng = np.random.default_rng(seed)
    cnt = {c: int((y == c).sum()) for c in range(7) if (y == c).sum()}
    mx = int(min(cnt.values()) * BAL); sel = []
    for c in range(7):
        idx = np.where(y == c)[0]
        if len(idx) > mx: idx = rng.choice(idx, size=mx, replace=False)
        sel.extend(idx.tolist())
    sel = np.asarray(sel); rng.shuffle(sel)
    return X[sel], y[sel]


def augment(X, y, seed):
    rng = np.random.default_rng(seed)
    A = X.copy() + rng.normal(0, NOISE, size=X.shape).astype(np.float32)
    s = rng.uniform(SMIN, SMAX, size=(len(A), 1, 1)).astype(np.float32)
    A[:, :, 0::3] *= s; A[:, :, 1::3] *= s
    Fp = A.copy(); Fp[:, :, 0::3] *= -1
    for a, b in LR_PAIRS:
        t = Fp[:, :, a * 3:a * 3 + 3].copy(); Fp[:, :, a * 3:a * 3 + 3] = Fp[:, :, b * 3:b * 3 + 3]; Fp[:, :, b * 3:b * 3 + 3] = t
    yf = y.copy()
    for s_, t_ in FLIP.items(): yf[y == s_] = t_
    return np.concatenate([A, Fp]), np.concatenate([y, yf])


def build(L, arch):
    i = tf.keras.Input(shape=(L, 99))
    if arch == "mlp":
        x = tf.keras.layers.Flatten()(i)
        x = tf.keras.layers.Dense(96, activation="relu")(x); x = tf.keras.layers.Dropout(.25)(x)
        x = tf.keras.layers.Dense(96, activation="relu")(x); x = tf.keras.layers.Dropout(.30)(x)
    else:
        x = tf.keras.layers.Conv1D(171 if arch == "gapwide" else 64, 3, padding="same", activation="relu")(i)
        x = tf.keras.layers.BatchNormalization()(x); x = tf.keras.layers.Dropout(.25)(x)
        if arch == "lstm": x = tf.keras.layers.LSTM(64)(x)
        elif arch == "gru": x = tf.keras.layers.GRU(64)(x)
        else: x = tf.keras.layers.GlobalAveragePooling1D()(x)
        x = tf.keras.layers.Dropout(.30)(x)
    o = tf.keras.layers.Dense(7, activation="softmax")(x)
    m = tf.keras.Model(i, o)
    m.compile(tf.keras.optimizers.Adam(LR), "sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


ARCH = os.environ.get("BH_ARCH", "gap").split(",")
SEQ = [int(v) for v in os.environ.get("BH_SEQ", "4").split(",")]
FOLDS = [int(v) for v in os.environ.get("BH_FOLDS", "0,1,2,3,4").split(",")]
for L in SEQ:
    for arch in ARCH:
        for f in FOLDS:
            name = f"{arch}_seq{L}_fold{f}"
            if os.path.exists(os.path.join(OUT, f"result_{name}.json")):
                print("SKIP", name); continue
            seed = 42 + f
            os.environ["PYTHONHASHSEED"] = str(seed); random.seed(seed); np.random.seed(seed)
            tf.keras.utils.set_random_seed(seed)
            try: tf.config.experimental.enable_op_determinism()
            except Exception: pass
            tf.keras.backend.clear_session(); gc.collect()
            inn = split_info["inner"][f]
            Xtr, ytr, _ = seqs(rec_ids(inn["train_groups"]), L)
            Xes, yes, _ = seqs(rec_ids(inn["early_stop_groups"]), L)
            te_ids = rec_ids(folds[f])
            Xte, yte, rte = seqs(te_ids, L)
            Xtr, ytr = balance(Xtr, ytr, seed); Xtr, ytr = augment(Xtr, ytr, seed)
            m = build(L, arch)
            cb = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=ES_PAT, restore_best_weights=True),
                  tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=.5, patience=LR_PAT, min_lr=1e-6)]
            t0 = time.time()
            h = m.fit(Xtr, ytr, validation_data=(Xes, yes), epochs=EPOCHS, batch_size=BATCH, shuffle=True,
                      callbacks=cb, verbose=2)
            sec = time.time() - t0
            P = m.predict(Xte, batch_size=4096, verbose=0)
            np.save(os.path.join(OUT, f"probabilities_{name}.npy"), P.astype(np.float32))
            m.save(os.path.join(OUT, f"model_{name}.keras"))
            pred = P.argmax(1)
            from sklearn.metrics import f1_score
            res = dict(arch=arch, L=L, fold=f, seed=seed, params=int(m.count_params()),
                       accuracy=float((pred == yte).mean()), macro_f1=float(f1_score(yte, pred, average="macro")),
                       f1_none=float(f1_score(yte == 0, pred == 0)), n_test=int(len(yte)),
                       test_record_ids=te_ids, epochs=len(h.history["loss"]), train_sec=sec,
                       es_acc=float(max(h.history["val_accuracy"])))
            json.dump(res, open(os.path.join(OUT, f"result_{name}.json"), "w"), indent=1)
            print("DONE", name, round(res["accuracy"] * 100, 2), flush=True)
