# -*- coding: utf-8 -*-
"""
녹화 단위 holdout: seq_len=1(Dense) vs 2(Conv1D+LSTM) vs 4(Conv1D+LSTM) 비교.

동일 데이터·동일 증강(noise + scale ±20%) 조건에서 녹화 단위 분할로 현실적 평가.
"""
import os, sys, json, time, argparse, math
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")

sys.path.insert(0, SCRIPT_DIR)
from pose_class_names import POSE_CLASS_NAMES
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.utils.class_weight import compute_class_weight

ALL_CLASSES = list(POSE_CLASS_NAMES)
NUM_CLASSES = len(ALL_CLASSES)
FEATURE_DIM = 33 * 3


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
    train_recs = []
    test_recs = []
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


def build_frames_from_recs(data, recs):
    X_list, y_list = [], []
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    for rec in recs:
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        end = min(start + count, len(data))
        for i in range(start, end):
            item = data[i]
            lm = item.get("landmarks")
            label = item.get("label")
            if not lm or len(lm) != FEATURE_DIM or label not in ALL_CLASSES:
                continue
            X_list.append(lm)
            y_list.append(label_to_idx[label])
    if not X_list:
        return np.empty((0, FEATURE_DIM), dtype=np.float32), np.empty((0,), dtype=np.int32)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def augment_noise_scale(X_seq, noise_std=0.03):
    rng = np.random.RandomState(43)
    n = len(X_seq)
    X_aug = X_seq.copy()
    X_aug += rng.normal(0, noise_std, X_aug.shape).astype(np.float32)
    if X_seq.ndim == 3:
        scales = rng.uniform(0.8, 1.2, (n, 1, 1)).astype(np.float32)
        X_aug[..., :2] *= scales
    else:
        scales = rng.uniform(0.8, 1.2, (n, 1)).astype(np.float32)
        X_aug[..., :2] *= scales
    return X_aug


def build_single_model():
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(FEATURE_DIM,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def build_seq_model(seq_len):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def train_and_eval(name, X_train, y_train, X_test, y_test, build_fn, seq_len=None):
    print(f"\n--- {name} ---")
    X_aug = augment_noise_scale(X_train)
    X_train_aug = np.concatenate([X_train, X_aug], axis=0)
    y_train_aug = np.concatenate([y_train, y_train], axis=0)

    classes = np.unique(y_train_aug)
    cw = compute_class_weight("balanced", classes=classes, y=y_train_aug)
    class_weight = dict(zip(classes, cw))

    model = build_fn() if seq_len is None else build_fn(seq_len)
    early = tf.keras.callbacks.EarlyStopping(
        monitor="loss", mode="min", patience=15, restore_best_weights=True, verbose=0)
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="loss", factor=0.5, patience=6, min_lr=1e-6, verbose=0)

    t0 = time.time()
    model.fit(X_train_aug, y_train_aug, epochs=80, batch_size=32,
              class_weight=class_weight, callbacks=[early, reduce_lr], verbose=0)
    elapsed = time.time() - t0

    y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
    acc = np.mean(y_pred == y_test)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=list(range(NUM_CLASSES)), zero_division=0)

    print(f"  정확도: {acc*100:.2f}%  ({elapsed:.0f}s 학습)")
    print(f"  {'동작':8s}  {'recall':>8s}  {'precision':>8s}  {'샘플':>6s}")
    for i in range(NUM_CLASSES):
        r = recall[i]*100 if support[i] > 0 else 0
        p = precision[i]*100 if support[i] > 0 else 0
        print(f"  {ALL_CLASSES[i]:8s}  {r:7.1f}%  {p:7.1f}%  {int(support[i]):6d}")

    return {
        "name": name,
        "accuracy": float(acc),
        "recall": {ALL_CLASSES[i]: float(recall[i]) for i in range(NUM_CLASSES)},
        "precision": {ALL_CLASSES[i]: float(precision[i]) for i in range(NUM_CLASSES)},
        "support": {ALL_CLASSES[i]: int(support[i]) for i in range(NUM_CLASSES)},
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "time_s": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("=" * 65)
    print("  Realistic comparison: seq_len=1 (Dense) vs 2 vs 4 (Conv1D+LSTM)")
    print(f"  Holdout: {args.test_ratio*100:.0f}% recordings per class as test")
    print("=" * 65)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    recordings = load_recordings(META_PATH)
    groups = group_recordings_by_label(recordings)

    print(f"\n녹화 수: {len(recordings)}")
    for lbl in ALL_CLASSES:
        print(f"  {lbl:8s}: {len(groups.get(lbl, []))}회")

    train_recs, test_recs = build_split(groups, args.test_ratio, args.seed)
    print(f"\nTrain: {len(train_recs)} recordings, Test: {len(test_recs)} recordings")

    results = []

    # --- seq_len=1: Dense (단일프레임) ---
    X_train_f, y_train_f = build_frames_from_recs(data, train_recs)
    X_test_f, y_test_f = build_frames_from_recs(data, test_recs)
    if len(X_train_f) > 0 and len(X_test_f) > 0:
        r = train_and_eval("seq_len=1 (Dense)", X_train_f, y_train_f, X_test_f, y_test_f, build_single_model)
        results.append(r)

    # --- seq_len=2: Conv1D+LSTM ---
    X_train_s2, y_train_s2 = build_sequences_from_recs(data, train_recs, 2)
    X_test_s2, y_test_s2 = build_sequences_from_recs(data, test_recs, 2)
    if len(X_train_s2) > 0 and len(X_test_s2) > 0:
        r = train_and_eval("seq_len=2 (Conv1D+LSTM)", X_train_s2, y_train_s2, X_test_s2, y_test_s2, build_seq_model, seq_len=2)
        results.append(r)

    # --- seq_len=4: Conv1D+LSTM ---
    X_train_s4, y_train_s4 = build_sequences_from_recs(data, train_recs, 4)
    X_test_s4, y_test_s4 = build_sequences_from_recs(data, test_recs, 4)
    if len(X_train_s4) > 0 and len(X_test_s4) > 0:
        r = train_and_eval("seq_len=4 (Conv1D+LSTM)", X_train_s4, y_train_s4, X_test_s4, y_test_s4, build_seq_model, seq_len=4)
        results.append(r)

    # --- 요약 ---
    print(f"\n{'='*65}")
    print("  최종 비교 요약")
    print(f"{'='*65}")
    print(f"{'모델':25s} {'정확도':>8s} {'Train':>8s} {'Test':>8s} {'시간':>6s}")
    print("-" * 55)
    for r in results:
        print(f"  {r['name']:23s}  {r['accuracy']*100:6.2f}%  {r['train_samples']:6d}  {r['test_samples']:6d}  {r['time_s']:5.1f}s")

    print(f"\n--- 동작별 Recall 비교 ---")
    print(f"{'동작':8s}", end="")
    for r in results:
        print(f"  {r['name'][:18]:>18s}", end="")
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

    print(f"\n--- 동작별 Precision 비교 ---")
    print(f"{'동작':8s}", end="")
    for r in results:
        print(f"  {r['name'][:18]:>18s}", end="")
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
