"""
Recording-based holdout 검증 스크립트
동일 녹화 내 시퀀스가 train/val에 섞이지 않도록 녹화 단위로 분할 후 평가
"""
import os
import json
import argparse

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

from pose_class_names import POSE_CLASS_NAMES

ALL_CLASS_NAMES = list(POSE_CLASS_NAMES)
FEATURE_DIM = 33 * 3


def load_data(data_path):
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_meta(meta_path):
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_sequences(data, recordings, class_names, seq_len):
    """녹화 목록에서 시퀀스를 추출"""
    X_seqs = []
    y_list = []
    n_data = len(data)
    half = seq_len // 2
    for rec in recordings:
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        impact_idx = rec.get("impact_idx")
        if impact_idx is not None and impact_idx >= 0:
            if impact_idx >= count:
                continue
            start = start + impact_idx
            count = count - impact_idx
        if count < seq_len:
            continue
        abs_end = min(start + count, n_data)
        for win_start in range(start, abs_end - seq_len + 1):
            ok = True
            seq_list = []
            for j in range(win_start, win_start + seq_len):
                item = data[j]
                lm = item.get("landmarks")
                if not lm or len(lm) != FEATURE_DIM:
                    ok = False
                    break
                seq_list.append(lm)
            if not ok:
                continue
            center = win_start + half
            clab = data[center].get("label")
            if clab not in class_names:
                continue
            X_seqs.append(np.array(seq_list, dtype=np.float32))
            y_list.append(clab)
    return X_seqs, y_list


def recording_based_holdout(data_path, meta_path, class_names, seq_len, val_ratio=0.2):
    """녹화 단위로 train/val 분할"""
    data = load_data(data_path)
    meta = load_meta(meta_path)
    recordings = meta.get("recordings", [])

    if not recordings:
        print("경고: 녹화 메타 없음. _sequences_from_runs 대체 불가.")
        return None, None, None, None

    # 녹화별 레이블 결정 (가장 빈도 높은 레이블)
    rec_labels = []
    for rec in recordings:
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        labels = []
        for i in range(start, min(start + count, len(data))):
            lab = data[i].get("label")
            if lab in class_names:
                labels.append(lab)
        if labels:
            from collections import Counter
            most_common = Counter(labels).most_common(1)[0][0]
            rec_labels.append(most_common)
        else:
            rec_labels.append(None)

    # 레이블별 녹화 그룹화
    from collections import defaultdict
    label_recs = defaultdict(list)
    for i, lab in enumerate(rec_labels):
        if lab is not None:
            label_recs[lab].append(i)

    # 각 레이블별로 stratify: val_ratio만큼 val로
    rng = np.random.RandomState(42)
    train_indices = []
    val_indices = []
    for lab, indices in label_recs.items():
        indices = list(indices)
        rng.shuffle(indices)
        n_val = max(1, int(len(indices) * val_ratio))
        val_indices.extend(indices[:n_val])
        train_indices.extend(indices[n_val:])

    train_recordings = [recordings[i] for i in train_indices]
    val_recordings = [recordings[i] for i in val_indices]

    print(f"총 녹화 수: {len(recordings)}")
    print(f"Train 녹화: {len(train_recordings)} / Val 녹화: {len(val_recordings)}")

    X_train, y_train = extract_sequences(data, train_recordings, class_names, seq_len)
    X_val, y_val = extract_sequences(data, val_recordings, class_names, seq_len)

    return X_train, y_train, X_val, y_val


def main():
    parser = argparse.ArgumentParser(description="Recording-based holdout validation")
    parser.add_argument("--data", default=os.path.join(SCRIPT_DIR, "pose_data.json"))
    parser.add_argument("--meta", default=os.path.join(SCRIPT_DIR, "pose_recordings_meta.json"))
    parser.add_argument("--seq-len", type=int, default=4)
    parser.add_argument("--val", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--patience", type=int, default=22)
    parser.add_argument("--augment", type=float, default=0.03)
    parser.add_argument("--augment-jitter", type=float, default=0.0)
    parser.add_argument("--balance-ratio", type=float, default=4.0)
    args = parser.parse_args()

    try:
        import tensorflow as tf
        from sklearn.utils.class_weight import compute_class_weight
        from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
    except ImportError as e:
        print("pip install tensorflow scikit-learn numpy")
        raise SystemExit(1) from e

    X_train_raw, y_train_raw, X_val_raw, y_val_raw = recording_based_holdout(
        args.data, args.meta, ALL_CLASS_NAMES, args.seq_len, args.val
    )

    if X_train_raw is None:
        print("데이터 로드 실패")
        return

    label_to_idx = {c: i for i, c in enumerate(ALL_CLASS_NAMES)}
    X_train = np.array(X_train_raw, dtype=np.float32)
    y_train = np.array([label_to_idx[l] for l in y_train_raw], dtype=np.int32)
    X_val = np.array(X_val_raw, dtype=np.float32)
    y_val = np.array([label_to_idx[l] for l in y_val_raw], dtype=np.int32)

    print(f"Train 시퀀스: {len(X_train)} / Val 시퀀스: {len(X_val)}")

    # 균형 조정
    from collections import Counter
    counts = Counter(y_train)
    if args.balance_ratio > 0:
        min_count = min(counts.values())
        max_per_class = int(min_count * args.balance_ratio)
        rng = np.random.RandomState(42)
        idx_keep = []
        for cls in range(len(ALL_CLASS_NAMES)):
            mask = (y_train == cls)
            inds = np.where(mask)[0]
            if len(inds) > max_per_class:
                inds = rng.choice(inds, size=max_per_class, replace=False)
            idx_keep.extend(inds.tolist())
        idx_keep = rng.permutation(idx_keep)
        X_train = X_train[idx_keep]
        y_train = y_train[idx_keep]
        print(f"균형 조정 후 train: {len(X_train)}")

    # 증강 (간단: noise + scale)
    if args.augment > 0:
        rng = np.random.RandomState(43)
        n = len(X_train)
        X_aug = X_train.copy()
        X_aug += rng.normal(0, args.augment, X_aug.shape).astype(np.float32)
        scales = rng.uniform(0.8, 1.2, (n, 1, 1)).astype(np.float32)
        for i in range(0, FEATURE_DIM, 3):
            X_aug[..., i:i+2] *= scales
        X_train = np.concatenate([X_train, X_aug], axis=0)
        y_train = np.concatenate([y_train, y_train], axis=0)
        print(f"증강 후 train: {len(X_train)}")

    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(args.seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.GlobalAveragePooling1D(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(len(ALL_CLASS_NAMES), activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", mode="min", patience=args.patience,
        restore_best_weights=True, verbose=1,
    )
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=7, min_lr=1e-6, verbose=1
    )

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=32,
        class_weight=class_weight,
        callbacks=[early, reduce_lr],
        verbose=1,
    )

    y_val_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_val, y_val_pred, labels=list(range(len(ALL_CLASS_NAMES))), zero_division=0
    )

    print("\n[동작별 정확도 (Recording-based holdout 20%)]")
    print("  동작      recall  precision  (샘플 수)")
    for i in range(len(ALL_CLASS_NAMES)):
        print(f"  {ALL_CLASS_NAMES[i]:8s}  {recall[i]*100:5.1f}%   {precision[i]*100:5.1f}%     ({int(support[i])})")

    report = classification_report(
        y_val, y_val_pred, labels=list(range(len(ALL_CLASS_NAMES))),
        target_names=ALL_CLASS_NAMES, digits=4, zero_division=0
    )
    print("\n[검증 세트 분류 리포트]\n" + report)
    cm_val = confusion_matrix(y_val, y_val_pred, labels=list(range(len(ALL_CLASS_NAMES))))
    print("혼동 행렬:")
    print(cm_val)

    # 결과 저장
    report_path = os.path.join(SCRIPT_DIR, "classification_report_seq_holdout.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Recording-based holdout 20% (녹화 단위 분할)\n\n")
        f.write(report)
        f.write("\n\nConfusion matrix:\n")
        f.write(str(cm_val))
    print(f"\n결과 저장: {report_path}")

    val_acc = model.evaluate(X_val, y_val, verbose=0)[1]
    print(f"\n최종 검증 정확도 (recording-based): {val_acc*100:.2f}%")


if __name__ == "__main__":
    main()
