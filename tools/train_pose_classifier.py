"""
포즈 분류 모델 학습: pose_data.json(정규화된 랜드마크) → Dense 네트워크 → none, guard, punch_l, punch_r, upper_l, upper_r.
졸업작품용: 클래스 불균형 보정(class_weight), EarlyStopping, 회전/스케일/좌우반전 증강으로 다양한 사람·각도·거리 견고성 확보.

좌우반전(flip-augment): 라벨만 L↔R 바꿔 추가. 반대편 정확도 떨어뜨리지 않음.
반대편 유지하면서 약한 쪽만 보강: --extra-augment-weak punch_r,upper_l (해당 클래스만 노이즈·회전 추가 증강, 가중치 변경 없음).
학습 횟수(녹화 횟수) 늘리기: punch_r, upper_l을 더 많이 녹화한 뒤 재학습해도 L/R 균형에 도움.

저장: pose_classifier.keras, training_history.json (학습 곡선), classification_report.txt (클래스별 정확도)

실행: cd tools → python train_pose_classifier.py
옵션: --extra-augment-weak punch_r,upper_l  (약한 쪽만 추가 증강, 반대편 유지)
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
from pose_class_names import POSE_CLASS_NAMES

ALL_CLASS_NAMES = list(POSE_CLASS_NAMES)
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


def subsample_consecutive_blocks(X_list, y_list, max_per_block, rng):
    """
    같은 라벨이 연속된 구간(블록)마다 최대 max_per_block개만 랜덤 샘플링.
    한 녹화에서 나온 40프레임 punch_l → 5프레임만 쓰는 식으로 중복·과적합 완화.
    max_per_block <= 0 이면 샘플링 안 함.
    """
    if max_per_block <= 0 or len(y_list) == 0:
        return X_list, y_list
    # 연속 동일 라벨 구간 찾기
    runs = []
    i = 0
    while i < len(y_list):
        j = i
        while j < len(y_list) and y_list[j] == y_list[i]:
            j += 1
        runs.append((i, j))
        i = j
    indices = []
    for start, end in runs:
        n = end - start
        if n > max_per_block:
            chosen = rng.choice(n, size=max_per_block, replace=False)
            indices.extend((start + chosen).tolist())
        else:
            indices.extend(range(start, end))
    return [X_list[i] for i in indices], [y_list[i] for i in indices]


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


def apply_translation(X, rng, max_shift=0.04):
    """x, y에 작은 평행이동 추가. 카메라/몸 위치 오프셋 시뮬레이션."""
    out = np.empty_like(X)
    for i in range(len(X)):
        row = X[i].reshape(NUM_LANDMARKS, 3).copy()
        tx = rng.uniform(-max_shift, max_shift)
        ty = rng.uniform(-max_shift, max_shift)
        row[:, 0] += tx
        row[:, 1] += ty
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
    """좌우 반전 시 라벨 스왑 맵: lr_pose_utils.LR_PAIRS 기준. none/guard 유지."""
    from lr_pose_utils import LR_PAIRS

    label_to_idx = {c: i for i, c in enumerate(class_names)}
    idx_to_new = list(range(len(class_names)))
    for left, right in LR_PAIRS:
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
    parser.add_argument("--augment", type=float, default=0.03, help="Gaussian noise std for augmentation (0=off)")
    parser.add_argument("--patience", type=int, default=22, help="EarlyStopping patience (epochs)")
    parser.add_argument("--classes", type=str, default=None,
                        help="Comma-separated classes only (e.g. none,punch_l). Load and train only those (sanity check).")
    parser.add_argument("--balance-ratio", type=float, default=4.0,
                        help="Downsample majority class so it has at most (smallest_class * this). 0 = no balancing. Default 4.")
    parser.add_argument("--view-augment", action="store_true", default=True,
                        help="Apply rotation+scale augmentation (diverse angles/distances). Default on.")
    parser.add_argument("--no-view-augment", action="store_false", dest="view_augment",
                        help="Disable rotation+scale augmentation.")
    parser.add_argument("--flip-augment", action="store_true", default=True,
                        help="Add horizontally flipped samples with L/R labels swapped. Default on.")
    parser.add_argument("--no-flip-augment", action="store_false", dest="flip_augment",
                        help="Disable flip augmentation.")
    parser.add_argument("--balance-lr-pairs", action="store_true", default=True,
                        help="After augment, oversample minority side of punch/upper L:R pairs (default on).")
    parser.add_argument("--no-balance-lr-pairs", action="store_false", dest="balance_lr_pairs",
                        help="Disable L/R pair oversampling.")
    parser.add_argument("--lr-oversample-max-ratio", type=float, default=6.0,
                        help="Max factor to grow minority class per L/R pair toward majority count.")
    parser.add_argument("--translate-augment", action="store_true", default=True,
                        help="Add small x/y translation (camera offset). Default on.")
    parser.add_argument("--no-translate-augment", action="store_false", dest="translate_augment",
                        help="Disable translation augmentation.")
    parser.add_argument("--max-frames-per-block", type=int, default=8,
                        help="같은 라벨 연속 구간당 최대 N프레임만 랜덤 사용 (중복·과적합 완화). 0=제한 없음. 기본 8.")
    parser.add_argument("--boost-classes", type=str, default=None,
                        help="[트레이드오프 있음] recall 낮은 클래스만 복제+가중치. 반대편이 약해질 수 있음.")
    parser.add_argument("--boost-weight", type=float, default=1.5,
                        help="--boost-classes 사용 시 해당 클래스 class_weight 배수.")
    parser.add_argument("--extra-augment-weak", type=str, default=None,
                        help="recall 낮은 클래스만 노이즈·회전 추가 증강 (반대편 유지). 쉼표 구분 (예: punch_r,upper_l).")
    parser.add_argument("--units", type=str, default="128,64",
                        help="Dense 레이어 뉴런 수 쉼표 구분 (예: 256,128). 기본 128,64.")
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

    # 연속 동일 라벨 구간당 최대 N프레임만 사용 (랜덤 프레임 샘플링)
    rng_load = np.random.RandomState(42)
    X, y = subsample_consecutive_blocks(X, y, args.max_frames_per_block, rng_load)
    if args.max_frames_per_block > 0:
        print(f"블록당 최대 {args.max_frames_per_block}프레임 샘플링 후: {len(X)}개")

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

    # 다수 클래스 다운샘플링: none 5700 vs punch_l 300 같은 경우, none을 (소수클래스*ratio) 이하로 줄임 → punch_l precision 개선
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

    try:
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=args.val, stratify=y, random_state=42
        )
    except ValueError as e:
        if "stratify" in str(e).lower() or "least" in str(e).lower():
            print("경고: 클래스별 샘플이 너무 적어 stratify 불가. 무작위 분할로 진행합니다.")
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=args.val, random_state=42
            )
        else:
            raise
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
        rng_view2 = np.random.RandomState(44)
        X_view2 = apply_rotation_scale(X_train_orig, rng_view2, angle_deg_range=20.0, scale_range=(0.85, 1.15))
        X_train = np.concatenate([X_train, X_view2], axis=0)
        y_train = np.concatenate([y_train, y_train_orig], axis=0)
        print(f"증강(회전±20°/스케일 0.85~1.15): 학습 샘플 {len(X_train)}")
    if args.translate_augment:
        rng_trans = np.random.RandomState(45)
        X_trans = apply_translation(X_train_orig, rng_trans, max_shift=0.04)
        X_train = np.concatenate([X_train, X_trans], axis=0)
        y_train = np.concatenate([y_train, y_train_orig], axis=0)
        print(f"증강(x/y 평행이동 ±0.04): 학습 샘플 {len(X_train)}")
    if args.flip_augment:
        X_flip = apply_horizontal_flip(X_train_orig)
        flip_swap = build_flip_label_swap(class_names)
        y_flip = flip_swap[y_train_orig]
        X_train = np.concatenate([X_train, X_flip], axis=0)
        y_train = np.concatenate([y_train, y_flip], axis=0)
        print(f"증강(좌우반전+L/R라벨스왑): 학습 샘플 {len(X_train)}")

    if args.balance_lr_pairs:
        from lr_pose_utils import oversample_lr_minorities

        rng_lr = np.random.RandomState(46)
        n_before = len(X_train)
        X_train, y_train = oversample_lr_minorities(
            X_train,
            y_train,
            class_names,
            rng_lr,
            max_ratio=float(args.lr_oversample_max_ratio),
        )
        print(
            f"L/R 쌍 소수 오버샘플(max_ratio={args.lr_oversample_max_ratio}): "
            f"{n_before} → {len(X_train)} (train)"
        )

    # (1) 약한 클래스만 추가 증강: 노이즈+회전으로 샘플 수만 늘림. class_weight 안 건드림 → 반대편 유지
    weak_class_indices = None
    if args.extra_augment_weak:
        names_weak = [s.strip() for s in args.extra_augment_weak.split(",") if s.strip()]
        weak_class_indices = set()
        for name in names_weak:
            if name in label_to_idx:
                weak_class_indices.add(label_to_idx[name])
        if weak_class_indices:
            mask = np.isin(y_train, list(weak_class_indices))
            X_weak = X_train[mask].copy()
            y_weak = y_train[mask].copy()
            rng_weak = np.random.RandomState(99)
            X_weak_noise = X_weak + rng_weak.normal(0, args.augment if args.augment > 0 else 0.02, X_weak.shape).astype(np.float32)
            X_weak_rot = apply_rotation_scale(X_weak, rng_weak, angle_deg_range=12.0, scale_range=(0.92, 1.08))
            X_train = np.concatenate([X_train, X_weak_noise, X_weak_rot], axis=0)
            y_train = np.concatenate([y_train, y_weak, y_weak], axis=0)
            print(f"약한 클래스만 추가 증강(노이즈+회전): {names_weak} → 학습 샘플 {len(X_train)} (반대편 유지)")

    # (2) [선택] boost-classes: 복제 + class_weight 배수 (트레이드오프 있음)
    boost_class_indices = None
    if args.boost_classes:
        names_boost = [s.strip() for s in args.boost_classes.split(",") if s.strip()]
        boost_class_indices = set()
        for name in names_boost:
            if name in label_to_idx:
                boost_class_indices.add(label_to_idx[name])
        if boost_class_indices:
            mask = np.isin(y_train, list(boost_class_indices))
            X_extra = X_train[mask]
            y_extra = y_train[mask]
            X_train = np.concatenate([X_train, X_extra], axis=0)
            y_train = np.concatenate([y_train, y_extra], axis=0)
            print(f"보강(복제+가중치): {names_boost} → 학습 샘플 {len(X_train)} [반대편 약해질 수 있음]")

    # 클래스 가중치 (balanced. --boost-classes 쓸 때만 해당 클래스에 배수 적용)
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))
    if boost_class_indices and args.boost_weight != 1.0:
        for c in boost_class_indices:
            if c in class_weight:
                class_weight[c] = float(class_weight[c]) * args.boost_weight
        print("class_weight (balanced + 보강클래스 배수):", {class_names[i]: round(float(class_weight.get(i, 0)), 3) for i in range(num_classes) if i in class_weight})
    else:
        print("class_weight (balanced):", {class_names[i]: round(float(w), 3) for i, w in zip(classes, weights)})

    units = [int(u.strip()) for u in args.units.split(",") if u.strip()]
    if not units:
        units = [128, 64]
    layers = [tf.keras.layers.Dense(units[0], activation="relu", input_shape=(FEATURE_DIM,))]
    layers.append(tf.keras.layers.BatchNormalization())
    layers.append(tf.keras.layers.Dropout(0.3))
    for u in units[1:]:
        layers.append(tf.keras.layers.Dense(u, activation="relu"))
        layers.append(tf.keras.layers.Dropout(0.25))
    layers.append(tf.keras.layers.Dense(num_classes, activation="softmax"))
    model = tf.keras.Sequential(layers)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    # val_accuracy 는 1.0 같은 값에서 동률이 자주 발생해 best 갱신이 막히고
    # 첫 100% 도달 가중치만 복원되는 문제가 있어서 val_loss 기준으로 모니터링.
    # ReduceLROnPlateau 도 val_loss 를 보므로 콜백 일관성도 유지된다.
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        mode="min",
        patience=args.patience,
        restore_best_weights=True,
        verbose=1,
    )
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=7,
        min_lr=1e-6,
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
        callbacks=[early, reduce_lr],
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
    cm_val = confusion_matrix(y_val, y_val_pred, labels=list(range(num_classes)))
    print("혼동 행렬 (validation):")
    print(cm_val)

    from lr_pose_utils import lr_confusion_hints

    lr_hints = lr_confusion_hints(class_names, cm_val)
    print("\n[L/R 쌍 상호 오분류 힌트]\n" + lr_hints)

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
        f.write(str(cm_val))
        f.write("\n\n[L/R 쌍 상호 오분류 힌트]\n")
        f.write(lr_hints + "\n")
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
