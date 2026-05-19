# -*- coding: utf-8 -*-
"""
seq_len=2 최종: 최고 증강 조합 + flip + baseline 재현.
"""
import os, sys, json, time
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
sys.path.insert(0, SCRIPT_DIR)
from pose_class_names import POSE_CLASS_NAMES

ALL_CLASSES = list(POSE_CLASS_NAMES)
NUM_CLASSES = len(ALL_CLASSES)
FEATURE_DIM = 33 * 3
LR_PAIRS = [("punch_l", "punch_r"), ("upper_l", "upper_r")]

LEFT_RIGHT_PAIRS = [
    (1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16),
    (17, 18), (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32),
]


def load_recordings(meta_path):
    with open(meta_path) as f:
        return json.load(f).get("recordings", [])


def group_recordings_by_label(recordings):
    groups = {}
    for rec in recordings:
        lbl = rec.get("label", "")
        if lbl in ALL_CLASSES:
            groups.setdefault(lbl, []).append(rec)
    return groups


def build_split(groups, test_ratio=0.2, seed=42):
    rng = np.random.RandomState(seed)
    train_recs, test_recs = [], []
    for lbl, recs in groups.items():
        idx = list(range(len(recs)))
        rng.shuffle(idx)
        n_test = max(1, int(len(recs) * test_ratio))
        test_idx = set(idx[:n_test])
        for i, rec in enumerate(recs):
            (test_recs if i in test_idx else train_recs).append(rec)
    return train_recs, test_recs


def build_sequences(data, recs, seq_len=2):
    X_list, y_list = [], []
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    for rec in recs:
        start = rec.get("start_index", 0)
        end = min(start + rec.get("frame_count", 0), len(data))
        if end - start < seq_len:
            continue
        for i in range(start, end - seq_len + 1):
            ok = True
            seq = []
            for j in range(i, i + seq_len):
                item = data[j]
                lm = item.get("landmarks")
                if not lm or len(lm) != FEATURE_DIM:
                    ok = False
                    break
                seq.append(lm)
            if not ok:
                continue
            center = data[i + seq_len // 2].get("label")
            if center not in ALL_CLASSES:
                continue
            X_list.append(np.array(seq, dtype=np.float32))
            y_list.append(label_to_idx[center])
    if not X_list:
        return np.empty((0, seq_len, FEATURE_DIM), dtype=np.float32), np.empty((0,), dtype=np.int32)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def apply_horizontal_flip_single(flat):
    row = flat.reshape(33, 3).copy()
    row[0, 0] = -row[0, 0]
    for li, ri in LEFT_RIGHT_PAIRS:
        lx, ly, lz = row[li]
        rx, ry, rz = row[ri]
        row[li] = [-rx, ry, rz]
        row[ri] = [-lx, ly, lz]
    return row.flatten().astype(np.float32)


def augment_flip(X, y):
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    swap = {}
    for left, right in LR_PAIRS:
        li, ri = label_to_idx.get(left), label_to_idx.get(right)
        if li is not None and ri is not None:
            swap[li] = ri; swap[ri] = li
    X_flip = np.empty_like(X)
    for i in range(len(X)):
        seq = X[i]
        X_flip[i] = np.array([apply_horizontal_flip_single(seq[t]) for t in range(seq.shape[0])])
    y_flip = np.array([swap.get(int(yi), int(yi)) for yi in y], dtype=np.int32)
    return X_flip, y_flip


def make_model():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


EXPERIMENTS = [
    {
        "name": "A. Baseline (noise.03+scale20%)",
        "augment": lambda X, y: (
            np.concatenate([X, _aug_ns(X, 0.03, 0.8, 1.2)], axis=0),
            np.concatenate([y, y], axis=0)),
    },
    {
        "name": "B. Scale30% (noise.03+scale±30%)",
        "augment": lambda X, y: (
            np.concatenate([X, _aug_ns(X, 0.03, 0.7, 1.3)], axis=0),
            np.concatenate([y, y], axis=0)),
    },
    {
        "name": "C. Flip only (noise+scale20%+flip)",
        "augment": lambda X, y: _aug_flip_combo(X, y, 0.03, 0.8, 1.2),
    },
    {
        "name": "D. Scale30%+Flip (noise+scale30%+flip)",
        "augment": lambda X, y: _aug_flip_combo(X, y, 0.03, 0.7, 1.3),
    },
    {
        "name": "E. Scale30%+Flip+Noise05",
        "augment": lambda X, y: _aug_flip_combo(X, y, 0.05, 0.7, 1.3),
    },
]


def _aug_ns(X, ns, smin, smax):
    rng = np.random.RandomState(43)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, ns, X_aug.shape).astype(np.float32)
    scales = rng.uniform(smin, smax, (n, 1, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    return X_aug


def _aug_flip_combo(X, y, ns, smin, smax):
    Xn = _aug_ns(X, ns, smin, smax)
    Xf, yf = augment_flip(X, y)
    return (
        np.concatenate([X, Xn, Xf], axis=0),
        np.concatenate([y, y, yf], axis=0),
    )


def main():
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")
    from sklearn.utils.class_weight import compute_class_weight
    from sklearn.metrics import precision_recall_fscore_support

    print("=" * 65)
    print("  seq_len=2 최적 증강 조합")
    print("=" * 65)

    with open(DATA_PATH) as f:
        data = json.load(f)
    groups = group_recordings_by_label(load_recordings(META_PATH))
    train_recs, test_recs = build_split(groups, 0.2, 42)
    X_train, y_train = build_sequences(data, train_recs, 2)
    X_test, y_test = build_sequences(data, test_recs, 2)
    print(f"\nTrain: {len(X_train)} seqs, Test: {len(X_test)} seqs\n")

    results = []
    for exp in EXPERIMENTS:
        name = exp["name"]
        print(f"\n  --- {name} ---", flush=True)
        X_aug, y_aug = exp["augment"](X_train, y_train)

        classes = np.unique(y_aug)
        cw = compute_class_weight("balanced", classes=classes, y=y_aug)
        class_weight = dict(zip(classes, cw))

        model = make_model()
        early = tf.keras.callbacks.EarlyStopping(
            monitor="loss", mode="min", patience=15, restore_best_weights=True, verbose=0)
        reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
            monitor="loss", factor=0.5, patience=6, min_lr=1e-6, verbose=0)

        t0 = time.time()
        model.fit(X_aug, y_aug, epochs=80, batch_size=32,
                  class_weight=class_weight, callbacks=[early, reduce_lr], verbose=0)
        elapsed = time.time() - t0

        y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
        acc = float(np.mean(y_pred == y_test))

        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, labels=list(range(NUM_CLASSES)), zero_division=0)

        print(f"    정확도: {acc*100:.2f}%  ({elapsed:.0f}s)  train={len(X_aug)}", flush=True)
        for i in range(NUM_CLASSES):
            if support[i] > 0:
                print(f"    {ALL_CLASSES[i]:8s}  recall={recall[i]*100:5.1f}%  precision={precision[i]*100:5.1f}%", flush=True)

        results.append({
            "name": name,
            "accuracy": acc,
            "recall": {ALL_CLASSES[i]: float(recall[i]) for i in range(NUM_CLASSES)},
            "precision": {ALL_CLASSES[i]: float(precision[i]) for i in range(NUM_CLASSES)},
            "support": {ALL_CLASSES[i]: int(support[i]) for i in range(NUM_CLASSES)},
            "train_samples": len(X_aug),
            "time_s": round(elapsed, 1),
        })
        tf.keras.backend.clear_session()

    print(f"\n{'='*65}")
    print("  최종 비교")
    print(f"{'='*65}")
    print(f"{'실험':30s} {'정확도':>8s} {'시간':>6s}")
    print("-" * 48)
    for r in results:
        print(f"  {r['name']:28s}  {r['accuracy']*100:6.2f}%  {r['time_s']:5.1f}s")

    print(f"\n--- Recall ---")
    print(f"{'동작':8s}", end="")
    for r in results:
        print(f"  {r['name'][:16]:>16s}", end="")
    print()
    for lbl in ALL_CLASSES:
        print(f"{lbl:8s}", end="")
        for r in results:
            sup = r['support'].get(lbl, 0)
            if sup > 0:
                print(f"  {r['recall'][lbl]*100:14.1f}%", end="")
            else:
                print(f"  {'N/A':>14s}", end="")
        print()


if __name__ == "__main__":
    main()
