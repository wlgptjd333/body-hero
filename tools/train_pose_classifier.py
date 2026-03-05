"""
포즈 분류 모델 학습: pose_data.json(정규화된 랜드마크) → Dense 네트워크 → none, guard, jab_l, jab_r, upper_l, upper_r, hook_l, hook_r.
졸업작품용: 클래스 불균형 보정(class_weight), EarlyStopping, 회전/스케일/좌우반전 증강으로 다양한 사람·각도·거리 견고성 확보.

저장: pose_classifier.keras, training_history.json (학습 곡선), classification_report.txt (클래스별 정확도)

실행: cd tools → python train_pose_classifier.py
옵션: --data pose_data.json --model pose_classifier.keras --epochs 120 --augment 0.02 --view-augment --flip-augment
"""
import os
import json
import argparse
import math

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "pose_classifier.keras")

# 전체 클래스 (--classes 미지정 시 사용)
ALL_CLASS_NAMES = ["none", "guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
FEATURE_DIM = 33 * 3  # 99
NUM_LANDMARKS = 33

# MediaPipe Pose: left/right 쌍 (좌우 반전 시 스왑). 0=nose는 x만 반전.
LEFT_RIGHT_PAIRS = [
    (1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16),
    (17, 18), (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32),
]


def load_data(path, class_names, skip_labels=None):
    """class_names에 있는 라벨만 로드. skip_labels(예: ['drop'])에 있으면 학습에서 제외."""
    skip_labels = skip_labels or []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    X = []
    y = []
    for item in raw:
        lm = item.get("landmarks")
        label = item.get("label")
        if not lm or label not in class_names or label in skip_labels:
            continue
        if len(lm) != FEATURE_DIM:
            continue
        X.append(lm)
        y.append(label)
    return X, y


def apply_rotation_scale(X, rng, angle_deg_range=15.0, scale_range=(0.9, 1.1)):
    """2D 회전(±angle_deg) + 균일 스케일(scale_range) 적용. 정규화된 (x,y)에 대해 다양한 각도·거리 시뮬레이션."""
    out = np.empty_like(X)
    angle_rad_range = math.radians(angle_deg_range)
    for i in range(len(X)):
        row = X[i].reshape(NUM_LANDMARKS, 3).copy()
        angle = rng.uniform(-angle_rad_range, angle_rad_range)
        scale = rng.uniform(scale_range[0], scale_range[1])
        c, s = math.cos(angle), math.sin(angle)
        for j in range(NUM_LANDMARKS):
            x, y, z = row[j, 0], row[j, 1], row[j, 2]
            row[j, 0] = (x * c - y * s) * scale
            row[j, 1] = (x * s + y * c) * scale
            row[j, 2] = z * scale
        out[i] = row.flatten()
    return out.astype(np.float32)


def apply_horizontal_flip(X):
    """좌우 반전: x → -x, left/right 랜드마크 쌍 스왑. 라벨은 호출측에서 left↔right 스왑 필요."""
    out = np.empty_like(X)
    for i in range(len(X)):
        row = X[i].reshape(NUM_LANDMARKS, 3).copy()
        # nose(0): x만 반전
        row[0, 0] = -row[0, 0]
        for left_idx, right_idx in LEFT_RIGHT_PAIRS:
            lx, ly, lz = row[left_idx, 0], row[left_idx, 1], row[left_idx, 2]
            rx, ry, rz = row[right_idx, 0], row[right_idx, 1], row[right_idx, 2]
            row[left_idx, 0], row[left_idx, 1], row[left_idx, 2] = -rx, ry, rz
            row[right_idx, 0], row[right_idx, 1], row[right_idx, 2] = -lx, ly, lz
        out[i] = row.flatten()
    return out.astype(np.float32)


def build_flip_label_swap(class_names):
    """좌우 반전 시 라벨 스왑 맵: jab_l↔jab_r, upper_l↔upper_r, hook_l↔hook_r. none/guard 유지."""
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    idx_to_new = list(range(len(class_names)))
    for left, right in [("jab_l", "jab_r"), ("upper_l", "upper_r"), ("hook_l", "hook_r")]:
        if left in label_to_idx and right in label_to_idx:
            i, j = label_to_idx[left], label_to_idx[right]
            idx_to_new[i], idx_to_new[j] = j, i
    return np.array(idx_to_new, dtype=np.int32)


def main():
    parser = argparse.ArgumentParser(description="Train pose classifier (normalized landmarks)")
    parser.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Output model path (.keras or .h5)")
    parser.add_argument("--epochs", type=int, default=120, help="Max training epochs (EarlyStopping으로 조기 종료)")
    parser.add_argument("--val", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument("--augment", type=float, default=0.02, help="Gaussian noise std for augmentation (0=off)")
    parser.add_argument("--patience", type=int, default=18, help="EarlyStopping patience (epochs)")
    parser.add_argument("--classes", type=str, default=None,
                        help="Comma-separated classes only (e.g. none,jab_l). Load and train only those (sanity check).")
    parser.add_argument("--balance-ratio", type=float, default=5.0,
                        help="Downsample majority class so it has at most (smallest_class * this). 0 = no balancing. Default 5.")
    parser.add_argument("--view-augment", action="store_true", default=True,
                        help="Apply rotation+scale augmentation (diverse angles/distances). Default on.")
    parser.add_argument("--no-view-augment", action="store_false", dest="view_augment",
                        help="Disable rotation+scale augmentation.")
    parser.add_argument("--flip-augment", action="store_true", default=True,
                        help="Add horizontally flipped samples with L/R labels swapped. Default on.")
    parser.add_argument("--no-flip-augment", action="store_false", dest="flip_augment",
                        help="Disable flip augmentation.")
    args = parser.parse_args()

    class_names = [c.strip() for c in args.classes.split(",")] if args.classes else ALL_CLASS_NAMES.copy()
    num_classes = len(class_names)

    try:
        import numpy as np
        import tensorflow as tf
        from sklearn.model_selection import train_test_split
        from sklearn.utils.class_weight import compute_class_weight
        from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
    except ImportError as e:
        print("pip install tensorflow scikit-learn numpy")
        raise SystemExit(1) from e

    if not os.path.isfile(args.data):
        print(f"데이터 파일 없음: {args.data}")
        print("  먼저 python collect_pose_data.py 로 데이터를 수집하세요.")
        raise SystemExit(1)

    X, y = load_data(args.data, class_names, skip_labels=["drop"])
    if len(X) < 30:
        print(f"샘플이 너무 적습니다 ({len(X)}개). 최소 30개 이상 수집 후 다시 실행하세요.")
        raise SystemExit(1)

    X = np.array(X, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y], dtype=np.int32)

    if args.classes:
        print(f"[검증 모드] 학습 클래스만 사용: {class_names}")
    # 클래스별 샘플 수 출력 (불균형 확인)
    from collections import Counter
    counts = Counter(y)
    print("클래스별 샘플 수:")
    for i, name in enumerate(class_names):
        print(f"  {name}: {counts.get(i, 0)}")

    # 다수 클래스 다운샘플링: none 5700 vs jab_l 300 같은 경우, none을 (소수클래스*ratio) 이하로 줄임 → jab_l precision 개선
    if args.balance_ratio > 0:
        min_count = min(counts.values())
        max_per_class = int(min_count * args.balance_ratio)
        rng = np.random.RandomState(42)
        idx_keep = []
        for cls in range(len(class_names)):
            mask = (y == cls)
            inds = np.where(mask)[0]
            if len(inds) > max_per_class:
                inds = rng.choice(inds, size=max_per_class, replace=False)
            idx_keep.extend(inds.tolist())
        idx_keep = rng.permutation(idx_keep)
        X = X[idx_keep]
        y = y[idx_keep]
        counts_after = Counter(y)
        print(f"균형 조정 후 (ratio={args.balance_ratio}, 최대 다수 클래스={max_per_class}):", {class_names[i]: counts_after.get(i, 0) for i in range(len(class_names))})

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=args.val, stratify=y, random_state=42)
    X_train_orig, y_train_orig = X_train.copy(), y_train.copy()
    rng_aug = np.random.RandomState(43)

    # 데이터 증강: 노이즈 (소수 클래스 강화) + 회전/스케일 (각도·거리 다양성) + 좌우반전 (L/R 균형)
    if args.augment > 0:
        X_noise = X_train_orig + np.random.RandomState(42).normal(0, args.augment, X_train_orig.shape).astype(np.float32)
        X_train = np.concatenate([X_train, X_noise], axis=0)
        y_train = np.concatenate([y_train, y_train_orig], axis=0)
        print(f"증강(노이즈 std={args.augment}): 학습 샘플 {len(X_train)}")
    if args.view_augment:
        X_view = apply_rotation_scale(X_train_orig, rng_aug, angle_deg_range=15.0, scale_range=(0.9, 1.1))
        X_train = np.concatenate([X_train, X_view], axis=0)
        y_train = np.concatenate([y_train, y_train_orig], axis=0)
        print(f"증강(회전±15°/스케일 0.9~1.1): 학습 샘플 {len(X_train)}")
    if args.flip_augment:
        X_flip = apply_horizontal_flip(X_train_orig)
        flip_swap = build_flip_label_swap(class_names)
        y_flip = flip_swap[y_train_orig]
        X_train = np.concatenate([X_train, X_flip], axis=0)
        y_train = np.concatenate([y_train, y_flip], axis=0)
        print(f"증강(좌우반전+L/R라벨스왑): 학습 샘플 {len(X_train)}")

    # 클래스 가중치 (소수 클래스에 더 높은 가중치 → 학습 안정)
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))
    print("class_weight (balanced):", {class_names[i]: round(float(w), 3) for i, w in zip(classes, weights)})

    model = tf.keras.Sequential([
        tf.keras.layers.Dense(128, activation="relu", input_shape=(FEATURE_DIM,)),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_accuracy",
        patience=args.patience,
        restore_best_weights=True,
        verbose=1,
    )

    print(f"\n학습 데이터: {len(X_train)} / 검증: {len(X_val)}")
    print("클래스:", class_names)
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=32,
        class_weight=class_weight,
        callbacks=[early],
        verbose=1,
    )

    # 학습 곡선 저장 (졸업작품 보고서/발표용)
    hist = {k: [float(x) for x in v] for k, v in history.history.items()}
    history_path = os.path.join(SCRIPT_DIR, "training_history.json")
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2)
    print(f"\n학습 곡선 저장: {history_path}")

    # 검증 세트 최종 평가 및 클래스별 리포트 (검증에 없는 클래스도 포함하도록 labels 지정)
    y_val_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_val, y_val_pred, labels=list(range(num_classes)), zero_division=0
    )
    print("\n[동작별 정확도 (검증 세트)]")
    print("  동작      recall  precision  (해당 동작 샘플 수)")
    for i in range(num_classes):
        r = recall[i] * 100
        p = precision[i] * 100
        s = int(support[i])
        print(f"  {class_names[i]:8s}  {r:5.1f}%   {p:5.1f}%     ({s})")
    print("  (recall: 그 동작을 얼마나 맞게 찾았는지, precision: 그렇게 예측했을 때 맞는 비율)\n")
    report = classification_report(
        y_val, y_val_pred, labels=list(range(num_classes)), target_names=class_names, digits=4, zero_division=0
    )
    print("[검증 세트 분류 리포트]\n" + report)
    print("혼동 행렬 (validation):")
    print(confusion_matrix(y_val, y_val_pred, labels=list(range(num_classes))))

    report_path = os.path.join(SCRIPT_DIR, "classification_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("[동작별 정확도 (검증 세트)]\n")
        f.write("  동작      recall  precision  (해당 동작 샘플 수)\n")
        for i in range(num_classes):
            r, p, s = recall[i] * 100, precision[i] * 100, int(support[i])
            f.write(f"  {class_names[i]:8s}  {r:5.1f}%   {p:5.1f}%     ({s})\n")
        f.write("\n")
        f.write(report)
        f.write("\n\nConfusion matrix:\n")
        f.write(str(confusion_matrix(y_val, y_val_pred, labels=list(range(num_classes)))))
    print(f"분류 리포트 저장: {report_path}")

    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"\n최종 검증 정확도: {val_acc * 100:.1f}%")

    out = args.model
    if out.endswith(".h5"):
        model.save(out)
    else:
        if not out.endswith(".keras"):
            out = out + ".keras" if not os.path.splitext(out)[1] else out
        model.save(out)
    print(f"모델 저장: {out}")


if __name__ == "__main__":
    main()
