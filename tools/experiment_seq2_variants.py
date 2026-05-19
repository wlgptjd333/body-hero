# -*- coding: utf-8 -*-
"""
seq_len=2 변형 실험: 증강 · 아키텍처 · 하이퍼파라미터.
동일 녹화 단위 holdout split으로 공정 비교.
"""
import os, sys, json, time, math
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


# ── 데이터 로드 · 분할 ─────────────────────────────────────────

def load_recordings(meta_path):
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return meta.get("recordings", [])


def group_recordings_by_label(recordings):
    groups = {}
    for rec in recordings:
        lbl = rec.get("label", "")
        if lbl not in ALL_CLASSES:
            continue
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
            if i in test_idx:
                test_recs.append(rec)
            else:
                train_recs.append(rec)
    return train_recs, test_recs


def build_sequences_from_recs(data, recs, seq_len):
    X_list, y_list = [], []
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    for rec in recs:
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        if count < seq_len:
            continue
        end = min(start + count, len(data))
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


# ── 증강 ───────────────────────────────────────────────────────

LEFT_RIGHT_PAIRS = [
    (1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16),
    (17, 18), (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32),
]


def apply_horizontal_flip_single(flat):
    row = flat.reshape(33, 3).copy()
    row[0, 0] = -row[0, 0]
    for li, ri in LEFT_RIGHT_PAIRS:
        lx, ly, lz = row[li]
        rx, ry, rz = row[ri]
        row[li] = [-rx, ry, rz]
        row[ri] = [-lx, ly, lz]
    return row.flatten().astype(np.float32)


def augment_baseline(X, noise_std=0.03):
    """noise + scale ±20% (현재 baseline)"""
    rng = np.random.RandomState(43)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, noise_std, X_aug.shape).astype(np.float32)
    scales = rng.uniform(0.8, 1.2, (n, 1, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    return X_aug


def augment_noise_scale(X, noise_std=0.03, scale_min=0.8, scale_max=1.2):
    rng = np.random.RandomState(43)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, noise_std, X_aug.shape).astype(np.float32)
    scales = rng.uniform(scale_min, scale_max, (n, 1, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    return X_aug


def augment_flip(X, y):
    """좌우반전 + L/R 라벨 스왑"""
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    swap = {}
    for left, right in LR_PAIRS:
        li, ri = label_to_idx.get(left), label_to_idx.get(right)
        if li is not None and ri is not None:
            swap[li] = ri
            swap[ri] = li
    X_flip = np.empty_like(X)
    for i in range(len(X)):
        seq = X[i]
        flipped = np.array([apply_horizontal_flip_single(seq[t]) for t in range(seq.shape[0])])
        X_flip[i] = flipped
    y_flip = np.array([swap.get(int(yi), int(yi)) for yi in y], dtype=np.int32)
    return X_flip, y_flip


def augment_landmark_dropout(X, drop_prob=0.1):
    """랜드마크 단위 드롭아웃: 일부 랜드마크를 0으로"""
    rng = np.random.RandomState(44)
    mask = rng.binomial(1, 1 - drop_prob, size=(X.shape[0], 33, 1)).astype(np.float32)
    mask = np.repeat(mask, 3, axis=2)
    X_aug = X.copy()
    X_aug *= mask[np.newaxis, :, :, :].transpose(0, 1, 3, 2)  # (N, seq_len, 99)
    # Wait, this is getting complex. Let me do it simpler.
    return X_aug  # placeholder

def augment_best_combo(X, y):
    """noise(0.03) + scale(±20%) + flip + landmark_dropout(0.05)"""
    rng = np.random.RandomState(45)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, 0.03, X_aug.shape).astype(np.float32)
    scales = rng.uniform(0.8, 1.2, (n, 1, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    ld_rng = np.random.RandomState(46)
    ld_mask = ld_rng.binomial(1, 0.95, size=(n, 33)).astype(np.float32)
    ld_mask = np.repeat(ld_mask[:, :, np.newaxis], 3, axis=2)  # (N, 33, 3)
    for t in range(X_aug.shape[1]):
        X_aug[:, t] *= ld_mask.reshape(n, -1)
    X_flip, y_flip = augment_flip(X, y)
    X_aug = np.concatenate([X_aug, X_flip], axis=0)
    y_aug = np.concatenate([y, y_flip], axis=0)
    return X_aug, y_aug


# ── 모델 빌더 ──────────────────────────────────────────────────

def model_baseline():
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


def model_conv_wider():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(128, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


def model_lstm_wider():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(128, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


def model_conv_both_wider():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(128, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(128, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


def model_kernel5():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 5, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
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

def model_deeper():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(2, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
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


# ── 실험 정의 ──────────────────────────────────────────────────

EXPERIMENTS = [
    {
        "name": "1. Baseline (noise.03+scale20%)",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_baseline,
    },
    {
        "name": "2. +Flip augmentation",
        "augment_fn": lambda X, y: (
            np.concatenate([X, augment_baseline(X, 0.03), augment_flip(X, y)[0]], axis=0),
            np.concatenate([y, y, augment_flip(X, y)[1]], axis=0)
        ),
        "model_fn": model_baseline,
    },
    {
        "name": "3. Higher noise (0.05)",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_noise_scale(X, 0.05, 0.8, 1.2)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_baseline,
    },
    {
        "name": "4. Wider scale (±30%)",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_noise_scale(X, 0.03, 0.7, 1.3)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_baseline,
    },
    {
        "name": "5. Landmark dropout (0.05)",
        "augment_fn": lambda X, y: _aug_landmark_dropout(X, y, 0.05),
        "model_fn": model_baseline,
    },
    {
        "name": "6. Conv1D 128 + LSTM 64",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_conv_wider,
    },
    {
        "name": "7. Conv1D 64 + LSTM 128",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_lstm_wider,
    },
    {
        "name": "8. Conv128 + LSTM128",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_conv_both_wider,
    },
    {
        "name": "9. Kernel 5 + 2xConv",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_kernel5,
    },
    {
        "name": "10. Deeper (2xConv+LSTM)",
        "augment_fn": lambda X, y: (np.concatenate([X, augment_baseline(X, 0.03)], axis=0),
                                     np.concatenate([y, y], axis=0)),
        "model_fn": model_deeper,
    },
    {
        "name": "11. Best combo (noise+scale+flip+ldrop)",
        "augment_fn": augment_best_combo,
        "model_fn": model_baseline,
    },
]


def _aug_landmark_dropout(X, y, drop_prob):
    rng = np.random.RandomState(47)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, 0.03, X_aug.shape).astype(np.float32)
    scales = rng.uniform(0.8, 1.2, (n, 1, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    ld_mask = rng.binomial(1, 1 - drop_prob, size=(n, 33)).astype(np.float32)
    ld_mask = np.repeat(ld_mask[:, :, np.newaxis], 3, axis=2)
    for t in range(X_aug.shape[1]):
        X_aug[:, t] *= ld_mask.reshape(n, -1)
    return np.concatenate([X, X_aug], axis=0), np.concatenate([y, y], axis=0)


def train_and_eval(name, X_train, y_train, X_test, y_test, model_fn, augment_fn):
    import tensorflow as tf
    from sklearn.utils.class_weight import compute_class_weight

    print(f"\n  --- {name} ---", flush=True)
    X_aug, y_aug = augment_fn(X_train, y_train)

    classes = np.unique(y_aug)
    cw = compute_class_weight("balanced", classes=classes, y=y_aug)
    class_weight = dict(zip(classes, cw))

    model = model_fn()
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

    from sklearn.metrics import precision_recall_fscore_support
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=list(range(NUM_CLASSES)), zero_division=0)

    print(f"    정확도: {acc*100:.2f}%  ({elapsed:.0f}s)  train={len(X_aug)} test={len(X_test)}", flush=True)
    for i in range(NUM_CLASSES):
        if support[i] > 0:
            print(f"    {ALL_CLASSES[i]:8s}  recall={recall[i]*100:5.1f}%  precision={precision[i]*100:5.1f}%", flush=True)

    return {
        "name": name,
        "accuracy": acc,
        "recall": {ALL_CLASSES[i]: float(recall[i]) for i in range(NUM_CLASSES)},
        "precision": {ALL_CLASSES[i]: float(precision[i]) for i in range(NUM_CLASSES)},
        "support": {ALL_CLASSES[i]: int(support[i]) for i in range(NUM_CLASSES)},
        "train_samples": len(X_aug),
        "test_samples": len(X_test),
        "time_s": round(elapsed, 1),
    }


def main():
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    print("=" * 70)
    print("  seq_len=2 변형 실험")
    print("=" * 70)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    recordings = load_recordings(META_PATH)
    groups = group_recordings_by_label(recordings)
    train_recs, test_recs = build_split(groups, 0.2, 42)

    X_train, y_train = build_sequences_from_recs(data, train_recs, 2)
    X_test, y_test = build_sequences_from_recs(data, test_recs, 2)

    print(f"\nTrain: {len(X_train)} seqs, Test: {len(X_test)} seqs\n")

    results = []
    for exp in EXPERIMENTS:
        result = train_and_eval(exp["name"], X_train, y_train, X_test, y_test, exp["model_fn"], exp["augment_fn"])
        results.append(result)
        tf.keras.backend.clear_session()

    # ── 요약 ──
    print(f"\n{'='*70}")
    print("  최종 비교 요약")
    print(f"{'='*70}")
    header = f"{'실험':35s} {'정확도':>8s} {'시간':>6s} {'Train':>7s}"
    print(header)
    print("-" * 60)
    for r in results:
        print(f"  {r['name']:33s}  {r['accuracy']*100:6.2f}%  {r['time_s']:5.1f}s  {r['train_samples']:6d}")

    print(f"\n--- Recall 비교 ---")
    print(f"{'동작':8s}", end="")
    for r in results:
        short = r['name'][:18]
        print(f"  {short:>18s}", end="")
    print()
    for lbl in ALL_CLASSES:
        print(f"{lbl:8s}", end="")
        for r in results:
            sup = r['support'].get(lbl, 0)
            rec = r['recall'].get(lbl, 0) * 100
            if sup > 0:
                print(f"  {rec:16.1f}%", end="")
            else:
                print(f"  {'N/A':>16s}", end="")
        print()

    print(f"\n--- Precision 비교 ---")
    print(f"{'동작':8s}", end="")
    for r in results:
        short = r['name'][:18]
        print(f"  {short:>18s}", end="")
    print()
    for lbl in ALL_CLASSES:
        print(f"{lbl:8s}", end="")
        for r in results:
            sup = r['support'].get(lbl, 0)
            prec = r['precision'].get(lbl, 0) * 100
            if sup > 0:
                print(f"  {prec:16.1f}%", end="")
            else:
                print(f"  {'N/A':>16s}", end="")
        print()


if __name__ == "__main__":
    main()
