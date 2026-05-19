# -*- coding: utf-8 -*-
"""
5-fold 교차검증: 녹화 단위로 분할하여 데이터 누수 방지.
현재 기본 모델(Conv1D64+LSTM64, seq_len=4)의 실제 일반화 성능 측정.

실행:
  python cross_validate.py
  python cross_validate.py --seq-len 4 --folds 5
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


def build_model(seq_len, num_classes):
    import tensorflow as tf
    return tf.keras.Sequential([
        tf.keras.layers.Input(shape=(seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.GlobalAveragePooling1D(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])


def get_recording_groups(meta_path, data_len, class_names):
    """녹화별로 {label: [recording_indices_list]} 반환.
    각 녹화는 (start_index, frame_count, label) 튜플의 리스트.
    """
    if not os.path.isfile(meta_path):
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    recordings = meta.get("recordings", [])
    if not recordings:
        return None

    groups = {name: [] for name in class_names}
    for rec in recordings:
        label = rec.get("label", "")
        if label not in class_names:
            continue
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        end = min(start + count, data_len)
        if end - start < 4:  # seq_len=4 minimum
            continue
        groups[label].append((start, end - start))
    return groups


def build_sequences_from_data(data, class_names, seq_len):
    """전체 data로부터 시퀀스와 라벨 배열 생성. 녹화 구간 무관하게 슬라이딩 윈도우."""
    import numpy as np
    X_list = []
    y_list = []
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    n = len(data)
    for i in range(0, n - seq_len + 1):
        seq_items = data[i : i + seq_len]
        ok = True
        seq_flat = []
        for item in seq_items:
            lm = item.get("landmarks")
            if not lm or len(lm) != FEATURE_DIM:
                ok = False
                break
            seq_flat.append(lm)
        if not ok:
            continue
        center_label = data[i + seq_len // 2].get("label")
        if center_label not in class_names or center_label == "drop":
            continue
        X_list.append(np.array(seq_flat, dtype=np.float32))
        y_list.append(label_to_idx[center_label])
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def recording_based_cv(data, groups, class_names, seq_len, n_folds, build_model_fn):
    """녹화 단위 Stratified K-Fold 교차검증.
    각 fold:
      - train: 4 folds의 녹화에서 만든 시퀀스
      - val: 1 fold의 녹화에서 만든 시퀀스
    """
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")
    from sklearn.utils.class_weight import compute_class_weight

    num_classes = len(class_names)
    label_to_idx = {c: i for i, c in enumerate(class_names)}

    # 녹화 플랫 리스트 + 라벨
    rec_list = []
    for label, recs in groups.items():
        for rec in recs:
            rec_list.append((label, rec))

    # Stratified: 클래스별로 fold 분배
    rng = np.random.RandomState(42)
    by_label = {name: [] for name in class_names}
    for label, rec in rec_list:
        by_label[label].append(rec)

    folds = [[] for _ in range(n_folds)]
    for label in class_names:
        recs = by_label[label]
        # 셔플 후 round-robin
        rng.shuffle(recs)
        for i, rec in enumerate(recs):
            folds[i % n_folds].append((label, rec))

    # 각 fold별로 시퀀스 빌드
    fold_sequences = []
    for fold_idx in range(n_folds):
        val_recs = set(folds[fold_idx])
        train_recs = []
        for i in range(n_folds):
            if i != fold_idx:
                train_recs.extend(folds[i])

        # train 시퀀스
        X_train, y_train = _build_fold_sequences(data, class_names, seq_len, train_recs)
        X_val, y_val = _build_fold_sequences(data, class_names, seq_len, folds[fold_idx])

        if len(X_train) == 0 or len(X_val) == 0:
            print(f"  Fold {fold_idx + 1}: train={len(X_train)} val={len(X_val)} → 스킵")
            continue

        # 증강
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

        rng_noise = np.random.RandomState(43)
        X_noise = X_train + rng_noise.normal(0, 0.03, X_train.shape).astype(np.float32)
        X_train = np.concatenate([X_train, X_noise], axis=0)
        y_train = np.concatenate([y_train, y_train], axis=0)

        classes = np.unique(y_train)
        weights = compute_class_weight("balanced", classes=classes, y=y_train)
        class_weight = dict(zip(classes, weights))

        model = build_model_fn(seq_len, num_classes)
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
        model.fit(
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

        print(f"  Fold {fold_idx + 1}: acc={val_acc*100:.1f}% loss={val_loss:.4f} "
              f"train={len(X_train)} val={len(X_val)} time={elapsed:.0f}s")

        fold_sequences.append({
            "fold": fold_idx + 1,
            "val_accuracy": float(val_acc),
            "val_loss": float(val_loss),
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "time_s": round(elapsed, 1),
            "per_class_recall": {class_names[i]: float(recall[i]) for i in range(num_classes)},
            "per_class_precision": {class_names[i]: float(precision[i]) for i in range(num_classes)},
        })

        tf.keras.backend.clear_session()

    return fold_sequences


def _build_fold_sequences(data, class_names, seq_len, fold_recs):
    """주어진 녹화 리스트에서 시퀀스 빌드."""
    X_list = []
    y_list = []
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    used_ranges = set()

    for label, (start, count) in fold_recs:
        end = min(start + count, len(data))
        for i in range(start, end - seq_len + 1):
            # 중복 방지 (이론상 녹화 구간이 겹치지 않음)
            key = i
            if key in used_ranges:
                continue
            used_ranges.add(key)
            seq_items = data[i : i + seq_len]
            ok = True
            seq_flat = []
            for item in seq_items:
                lm = item.get("landmarks")
                if not lm or len(lm) != FEATURE_DIM:
                    ok = False
                    break
                seq_flat.append(lm)
            if not ok:
                continue
            center_label = data[i + seq_len // 2].get("label")
            if center_label not in class_names or center_label == "drop":
                continue
            X_list.append(np.array(seq_flat, dtype=np.float32))
            y_list.append(label_to_idx[center_label])
    if not X_list:
        return np.empty((0, seq_len, FEATURE_DIM), dtype=np.float32), np.empty((0,), dtype=np.int32)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def main():
    parser = argparse.ArgumentParser(description="5-fold CV for pose classifier")
    parser.add_argument("--seq-len", type=int, default=4)
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    print(f"\n{'='*70}")
    print(f"{args.folds}-fold 교차검증 (Conv1D64+LSTM64, seq_len={args.seq_len})")
    print(f"{'='*70}\n")

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    class_names = list(POSE_CLASS_NAMES)

    groups = get_recording_groups(META_PATH, len(data), class_names)
    if not groups:
        print("녹화 메타 정보가 없어 교차검증을 진행할 수 없습니다.")
        return

    # 녹화 통계
    total_recs = sum(len(v) for v in groups.values())
    print(f"전체 녹화: {total_recs}회")
    for name in class_names:
        print(f"  {name}: {len(groups[name])}회")

    t_start = time.time()
    results = recording_based_cv(data, groups, class_names, args.seq_len, args.folds, build_model)
    total_time = time.time() - t_start

    if not results:
        print("\n교차검증 결과가 없습니다.")
        return

    print(f"\n{'='*70}")
    print("교차검증 결과 요약")
    print(f"{'='*70}")

    accs = [r["val_accuracy"] for r in results]
    losses = [r["val_loss"] for r in results]
    times = [r["time_s"] for r in results]

    print(f"\n전체 정확도: {np.mean(accs)*100:.2f}% ± {np.std(accs)*100:.2f}%")
    print(f"  개별: {[f'{a*100:.1f}%' for a in accs]}")
    print(f"전체 Loss:   {np.mean(losses):.4f} ± {np.std(losses):.4f}")
    print(f"총 소요시간: {total_time:.0f}s ({np.mean(times):.0f}s/fold)")

    print(f"\n--- 동작별 평균 Recall (검증 폴드) ---")
    print(f"{'동작':10s} {'Recall':>8s} {'±':>6s}")
    for name in class_names:
        recalls = [r["per_class_recall"][name] for r in results]
        print(f"{name:10s} {np.mean(recalls)*100:7.1f}% {np.std(recalls)*100:6.1f}%")

    print(f"\n--- 동작별 평균 Precision ---")
    print(f"{'동작':10s} {'Precision':>8s} {'±':>6s}")
    for name in class_names:
        precs = [r["per_class_precision"][name] for r in results]
        print(f"{name:10s} {np.mean(precs)*100:7.1f}% {np.std(precs)*100:6.1f}%")

    min_acc = min(accs)
    print(f"\n결론:")
    print(f"  5-fold CV 평균 정확도: {np.mean(accs)*100:.2f}%")
    print(f"  최저 fold 정확도: {min_acc*100:.2f}% (worst-case 일반화)")
    if np.mean(accs) >= 0.99:
        print(f"  → 매우 높은 일반화 성능. 데이터 품질이 우수하고 과적합 위험 낮음.")
    elif np.mean(accs) >= 0.95:
        print(f"  → 우수한 일반화 성능. 일부 오분류 가능성 있음 (동작별 recall 확인).")
    else:
        print(f"  → 추가 데이터 수집 또는 모델 튜닝 권장.")


if __name__ == "__main__":
    main()
