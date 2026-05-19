# -*- coding: utf-8 -*-
"""
제한된 데이터(동작당 N회)로 모델 크기(64 vs 128) 일반화 성능 비교.

실행:
  python compare_model_sizes.py                  # 기본: 동작당 15회
  python compare_model_sizes.py --samples 20     # 동작당 20회
  python compare_model_sizes.py --samples 10 --runs 5  # 10회씩 5번 반복
"""
import os
import json
import argparse
import numpy as np
import time

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")

from pose_class_names import POSE_CLASS_NAMES

FEATURE_DIM = 33 * 3
SEQ_LEN = 4


def load_data(data_path, meta_path, seq_len):
    from train_pose_classifier_seq import load_sequences_by_recordings

    class_names = list(POSE_CLASS_NAMES)
    X_seqs, y_list = load_sequences_by_recordings(
        data_path, meta_path, class_names, seq_len, skip_labels=["drop"]
    )
    X = np.array(X_seqs, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)
    return X, y, class_names


def subset_by_recordings(X, y, class_names, meta_path, max_recordings_per_class):
    """동작당 최대 max_recordings_per_class개 녹화 분량만 남기고 나머지 제거.
    녹화 1회 = 최대 57개 시퀀스 (60프레임 - SEQ_LEN + 1).
    각 클래스에서 랜덤하게 TARGET_SEQ_PER_CLASS개 시퀀스 선택.
    """
    rng = np.random.RandomState(42)
    target_per_class = max_recordings_per_class * 57

    keep_mask = np.zeros(len(X), dtype=bool)
    for i, lbl_name in enumerate(class_names):
        idxs = np.where(y == i)[0]
        target = min(len(idxs), target_per_class)
        if len(idxs) > target:
            chosen = rng.choice(idxs, size=target, replace=False)
        else:
            chosen = idxs
        keep_mask[chosen] = True

    X_sub = X[keep_mask]
    y_sub = y[keep_mask]
    print(f"  [subset] 동작당 최대 {max_recordings_per_class}회 → {len(X)} → {len(X_sub)} 시퀀스")
    return X_sub, y_sub


def build_model_64_64(seq_len, num_classes):
    import tensorflow as tf
    return tf.keras.Sequential([
        tf.keras.layers.Input(shape=(seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])


def build_model_128_128(seq_len, num_classes):
    import tensorflow as tf
    return tf.keras.Sequential([
        tf.keras.layers.Input(shape=(seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(128, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(128, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])


def train_and_eval(X, y, class_names, build_model_fn, model_name, rng_seed):
    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    from sklearn.utils.class_weight import compute_class_weight
    from sklearn.metrics import classification_report, confusion_matrix

    num_classes = len(class_names)

    # train/val split
    try:
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=rng_seed
        )
    except ValueError:
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=rng_seed
        )

    # flip augmentation
    try:
        from train_pose_classifier import apply_horizontal_flip, build_flip_label_swap
    except ImportError:
        apply_horizontal_flip = None
        build_flip_label_swap = None

    if apply_horizontal_flip is not None and build_flip_label_swap is not None:
        swap = build_flip_label_swap(class_names)
        X_flip = np.empty_like(X_train)
        for i in range(len(X_train)):
            seq = X_train[i]
            for t in range(seq.shape[0]):
                X_flip[i, t] = apply_horizontal_flip(seq[t: t + 1])[0]
        y_flip = swap[y_train]
        X_train = np.concatenate([X_train, X_flip], axis=0)
        y_train = np.concatenate([y_train, y_flip], axis=0)

    # noise augment
    rng = np.random.RandomState(rng_seed + 100)
    X_noise = X_train + rng.normal(0, 0.03, X_train.shape).astype(np.float32)
    X_train = np.concatenate([X_train, X_noise], axis=0)
    y_train = np.concatenate([y_train, y_train], axis=0)

    # class weights
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))

    model = build_model_fn(SEQ_LEN, num_classes)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", mode="min", patience=22,
        restore_best_weights=True, verbose=0,
    )
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=7, min_lr=1e-6, verbose=0,
    )

    t0 = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=120,
        batch_size=32,
        class_weight=class_weight,
        callbacks=[early, reduce_lr],
        verbose=0,
    )
    elapsed = time.time() - t0

    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)

    y_val_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
    from sklearn.metrics import precision_recall_fscore_support
    precision, recall, f1, support = precision_recall_fscore_support(
        y_val, y_val_pred, labels=list(range(num_classes)), zero_division=0
    )

    epochs_run = len(history.history["val_loss"])

    return {
        "model": model_name,
        "seed": rng_seed,
        "val_accuracy": float(val_acc),
        "val_loss": float(val_loss),
        "epochs": epochs_run,
        "train_time_s": round(elapsed, 1),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "per_class_recall": {class_names[i]: float(recall[i]) for i in range(num_classes)},
        "per_class_precision": {class_names[i]: float(precision[i]) for i in range(num_classes)},
    }


def main():
    parser = argparse.ArgumentParser(description="Compare model sizes with limited data")
    parser.add_argument("--samples", type=int, default=15, help="동작당 최대 녹화 횟수 (기본 15)")
    parser.add_argument("--runs", type=int, default=3, help="반복 횟수 (다른 랜덤 시드, 기본 3)")
    args = parser.parse_args()

    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    print(f"\n{'='*70}")
    print(f"모델 크기 비교: Conv1D+LSTM (64/64) vs (128/128)")
    print(f"데이터: 동작당 최대 {args.samples}회 녹화, {args.runs}회 반복")
    print(f"{'='*70}\n")

    X, y, class_names = load_data(DATA_PATH, META_PATH, SEQ_LEN)
    print(f"전체 데이터: {len(X)} 시퀀스, {len(class_names)} 클래스")
    for i, name in enumerate(class_names):
        print(f"  {name}: {np.sum(y == i)} 시퀀스")

    X_sub, y_sub = subset_by_recordings(X, y, class_names, META_PATH, args.samples)
    print(f"서브셋 데이터: {len(X_sub)} 시퀀스\n")

    results = []

    for run in range(args.runs):
        seed = 42 + run * 10
        print(f"--- Run {run + 1}/{args.runs} (seed={seed}) ---")

        r1 = train_and_eval(X_sub, y_sub, class_names, build_model_64_64, "Conv1D64+LSTM64", seed)
        print(f"  {r1['model']}: acc={r1['val_accuracy']*100:.1f}% loss={r1['val_loss']:.4f} epochs={r1['epochs']} time={r1['train_time_s']}s")
        results.append(r1)

        r2 = train_and_eval(X_sub, y_sub, class_names, build_model_128_128, "Conv1D128+LSTM128", seed)
        print(f"  {r2['model']}: acc={r2['val_accuracy']*100:.1f}% loss={r2['val_loss']:.4f} epochs={r2['epochs']} time={r2['train_time_s']}s")
        results.append(r2)

    # Summary
    print(f"\n{'='*70}")
    print("결과 요약")
    print(f"{'='*70}")

    from collections import defaultdict
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    for model_name, entries in by_model.items():
        accs = [e["val_accuracy"] for e in entries]
        losses = [e["val_loss"] for e in entries]
        times = [e["train_time_s"] for e in entries]
        epochs = [e["epochs"] for e in entries]
        print(f"\n[{model_name}]")
        print(f"  정확도: {np.mean(accs)*100:.1f}% ± {np.std(accs)*100:.1f}% (개별: {[f'{a*100:.1f}%' for a in accs]})")
        print(f"  Loss:   {np.mean(losses):.4f} ± {np.std(losses):.4f}")
        print(f"  Epochs: {np.mean(epochs):.0f} ± {np.std(epochs):.0f}")
        print(f"  학습시간: {np.mean(times):.1f}s ± {np.std(times):.1f}s")

    # Per-class comparison (average across runs)
    print(f"\n--- 동작별 평균 Recall ---")
    print(f"{'동작':10s} {'64/64':>8s} {'128/128':>8s} {'차이':>8s}")
    for name in class_names:
        r64 = np.mean([np.mean([e["per_class_recall"][name] for e in by_model["Conv1D64+LSTM64"]])])
        r128 = np.mean([np.mean([e["per_class_recall"][name] for e in by_model["Conv1D128+LSTM128"]])])
        diff = r128 - r64
        sign = "+" if diff > 0 else ""
        print(f"{name:10s} {r64*100:7.1f}% {r128*100:7.1f}% {sign}{diff*100:7.1f}%")

    print(f"\n결론: ")

    acc64 = np.mean([e["val_accuracy"] for e in by_model["Conv1D64+LSTM64"]])
    acc128 = np.mean([e["val_accuracy"] for e in by_model["Conv1D128+LSTM128"]])
    time64 = np.mean([e["train_time_s"] for e in by_model["Conv1D64+LSTM64"]])
    time128 = np.mean([e["train_time_s"] for e in by_model["Conv1D128+LSTM128"]])

    if abs(acc128 - acc64) < 0.01:
        print(f"  두 모델의 정확도가 거의 동일함 (차이 {abs(acc128-acc64)*100:.1f}%).")
        print(f"  128 모델이 파라미터는 3.6배 많지만, 이 데이터에서는 효과 없음.")
        print(f"  64/64 모델이 더 가볍고 빠르므로 추천.")
    elif acc128 > acc64:
        print(f"  128 모델이 {acc128-acc64:.1%} 더 높음. 데이터가 충분히 복잡하면 큰 모델이 유리.")
    else:
        print(f"  64 모델이 오히려 {acc64-acc128:.1%} 더 높음. 128은 과적합.")

    print(f"  학습시간: 64={time64:.1f}s, 128={time128:.1f}s (128이 {time128/time64:.1f}x 느림)")


if __name__ == "__main__":
    main()
