"""
논문/보고서용 실험 자동화: seq_len=1/2/4 비교 + 최적 구성 기록 저장.

용법:
  python run_experiment.py                                  # 전부 실행
  python run_experiment.py --only-best                      # 최종 구성만 학습+저장
  python run_experiment.py --seq-lens 1,2,4 --aug-flip      # 특정 조합만

저장 경로:
  docs/experiments/<날짜>-<실험명>.json  (정형 결과)
  docs/experiments/<날짜>-<실험명>.md    (markdown 요약)
  tools/pose_classifier_seq_len2.keras   (최종 모델)
"""
import os, sys, json, time, argparse
from datetime import date
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
EXPERIMENTS_DIR = os.path.join(PROJECT_DIR, "docs", "experiments")
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

# ── 데이터 ────────────────────────────────────────────────

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


def build_data(data, recs, seq_len):
    X_list, y_list = [], []
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    if seq_len == 1:
        for rec in recs:
            start = rec.get("start_index", 0)
            end = min(start + rec.get("frame_count", 0), len(data))
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
    else:
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


# ── 증강 ──────────────────────────────────────────────────

def apply_horizontal_flip_single(flat):
    row = flat.reshape(33, 3).copy()
    row[0, 0] = -row[0, 0]
    for li, ri in LEFT_RIGHT_PAIRS:
        lx, ly, lz = row[li]
        rx, ry, rz = row[ri]
        row[li] = [-rx, ry, rz]
        row[ri] = [-lx, ly, lz]
    return row.flatten().astype(np.float32)


def augment_noise_scale(X, noise_std=0.03, scale_min=0.8, scale_max=1.2):
    rng = np.random.RandomState(43)
    n = len(X)
    X_aug = X.copy()
    X_aug += rng.normal(0, noise_std, X_aug.shape).astype(np.float32)
    if X.ndim == 3:
        scales = rng.uniform(scale_min, scale_max, (n, 1, 1)).astype(np.float32)
    else:
        scales = rng.uniform(scale_min, scale_max, (n, 1)).astype(np.float32)
    X_aug[..., :2] *= scales
    return X_aug


def augment_flip(X, y):
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    swap = {}
    for left, right in LR_PAIRS:
        li, ri = label_to_idx.get(left), label_to_idx.get(right)
        if li is not None and ri is not None:
            swap[li] = ri; swap[ri] = li
    if X.ndim == 3:
        X_flip = np.empty_like(X)
        for i in range(len(X)):
            X_flip[i] = np.array([apply_horizontal_flip_single(X[i][t]) for t in range(X.shape[1])])
    else:
        X_flip = np.array([apply_horizontal_flip_single(x) for x in X])
    y_flip = np.array([swap.get(int(yi), int(yi)) for yi in y], dtype=np.int32)
    return X_flip, y_flip


def apply_augmentation(X, y, use_flip, noise_std=0.03, scale_min=0.8, scale_max=1.2):
    X_aug = augment_noise_scale(X, noise_std, scale_min, scale_max)
    X_out, y_out = np.concatenate([X, X_aug], axis=0), np.concatenate([y, y], axis=0)
    if use_flip:
        X_f, y_f = augment_flip(X, y)
        X_out = np.concatenate([X_out, X_f], axis=0)
        y_out = np.concatenate([y_out, y_f], axis=0)
    return X_out, y_out


# ── 모델 ──────────────────────────────────────────────────

def make_seq_model(seq_len):
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(seq_len, FEATURE_DIM)),
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


def make_single_model():
    import tensorflow as tf
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(FEATURE_DIM,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return m


# ── 학습+평가 ────────────────────────────────────────────

def train_eval(name, X_train, y_train, X_test, y_test, seq_len, augment_fn):
    import tensorflow as tf
    from sklearn.utils.class_weight import compute_class_weight
    from sklearn.metrics import precision_recall_fscore_support

    print(f"\n  {name}", flush=True)
    X_aug, y_aug = augment_fn(X_train, y_train)

    classes = np.unique(y_aug)
    cw = compute_class_weight("balanced", classes=classes, y=y_aug)
    class_weight = dict(zip(classes, cw))

    model = make_seq_model(seq_len) if seq_len > 1 else make_single_model()
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

    print(f"    acc={acc*100:.2f}%  ({elapsed:.0f}s)  train={len(X_aug)}  test={len(X_test)}", flush=True)
    for i in range(NUM_CLASSES):
        if support[i] > 0:
            print(f"    {ALL_CLASSES[i]:8s}  recall={recall[i]*100:5.1f}%  precision={precision[i]*100:5.1f}%", flush=True)

    return {
        "name": name,
        "seq_len": seq_len,
        "accuracy": acc,
        "recall": {ALL_CLASSES[i]: float(recall[i]) for i in range(NUM_CLASSES)},
        "precision": {ALL_CLASSES[i]: float(precision[i]) for i in range(NUM_CLASSES)},
        "support": {ALL_CLASSES[i]: int(support[i]) for i in range(NUM_CLASSES)},
        "train_samples": len(X_aug),
        "test_samples": len(X_test),
        "time_s": round(elapsed, 1),
    }


def save_results(results, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n저장: {path}")


def save_markdown(results, path, title):
    lines = [
        f"# {title}",
        f"",
        f"날짜: {date.today().isoformat()}",
        f"데이터: {DATA_PATH}",
        f"분할: 녹화 단위 holdout 20%",
        f"",
        f"## 결과 요약",
        f"",
        f"| 실험 | 정확도 | 시간 | Train | Test |",
        f"|------|--------|------|-------|------|",
    ]
    for r in results:
        lines.append(f"| {r['name']} | {r['accuracy']*100:.2f}% | {r['time_s']}s | {r['train_samples']} | {r['test_samples']} |")

    lines.extend(["", "## Recall 비교", "", f"| 동작 | " + " | ".join([r['name'][:20] for r in results]) + " |"])
    lines.append("|------|" + "|".join(["---" for _ in results]) + "|")
    for lbl in ALL_CLASSES:
        row = f"| {lbl} "
        for r in results:
            sup = r['support'].get(lbl, 0)
            if sup > 0:
                row += f"| {r['recall'][lbl]*100:.1f}% "
            else:
                row += "| N/A "
        lines.append(row + "|")

    lines.extend(["", "## Precision 비교", "", f"| 동작 | " + " | ".join([r['name'][:20] for r in results]) + " |"])
    lines.append("|------|" + "|".join(["---" for _ in results]) + "|")
    for lbl in ALL_CLASSES:
        row = f"| {lbl} "
        for r in results:
            sup = r['support'].get(lbl, 0)
            if sup > 0:
                row += f"| {r['precision'][lbl]*100:.1f}% "
            else:
                row += "| N/A "
        lines.append(row + "|")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"저장: {path}")


# ── 메인 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Body Hero ML 실험 자동화")
    parser.add_argument("--seq-lens", default="1,2,4", help="쉼표 구분 seq_len 목록")
    parser.add_argument("--aug-flip", action="store_true", default=True)
    parser.add_argument("--no-aug-flip", action="store_false", dest="aug_flip")
    parser.add_argument("--tag", default="", help="실험 태그 (파일명 접미사)")
    parser.add_argument("--save-model", default="", help="최종 모델 저장 경로 (best 구성만)")
    args = parser.parse_args()

    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    seq_lens = [int(s.strip()) for s in args.seq_lens.split(",")]
    tag = f"_{args.tag}" if args.tag else ""
    today = date.today().isoformat()
    title = f"seq_len 비교 실험 ({today})"

    print("=" * 65)
    print(f"  {title}")
    print(f"  seq_lens={seq_lens}  flip={args.aug_flip}")
    print("=" * 65)

    with open(DATA_PATH) as f:
        data = json.load(f)
    groups = group_recordings_by_label(load_recordings(META_PATH))
    train_recs, test_recs = build_split(groups, 0.2, 42)

    results = []
    for seq_len in seq_lens:
        X_train, y_train = build_data(data, train_recs, seq_len)
        X_test, y_test = build_data(data, test_recs, seq_len)
        if len(X_train) == 0 or len(X_test) == 0:
            print(f"  seq_len={seq_len}: 데이터 부족, 스킵")
            continue

        def augment(X, y):
            return apply_augmentation(X, y, use_flip=args.aug_flip)

        name = f"seq_len={seq_len}"
        if args.aug_flip:
            name += " +flip"
        r = train_eval(name, X_train, y_train, X_test, y_test, seq_len, augment)
        results.append(r)
        tf.keras.backend.clear_session()

        # 최종 모델 저장
        if args.save_model and seq_len == 2:
            aug_fn = lambda X, y: apply_augmentation(X, y, use_flip=True)
            X_aug, y_aug = aug_fn(X_train, y_train)
            from sklearn.utils.class_weight import compute_class_weight
            classes = np.unique(y_aug)
            cw = compute_class_weight("balanced", classes=classes, y=y_aug)
            model = make_seq_model(2)
            model.fit(X_aug, y_aug, epochs=80, batch_size=32,
                      class_weight=dict(zip(classes, cw)),
                      callbacks=[
                          tf.keras.callbacks.EarlyStopping(monitor="loss", mode="min", patience=15, restore_best_weights=True, verbose=0),
                          tf.keras.callbacks.ReduceLROnPlateau(monitor="loss", factor=0.5, patience=6, min_lr=1e-6, verbose=0),
                      ], verbose=0)
            model.save(args.save_model)
            print(f"  최종 모델 저장: {args.save_model}")

    json_path = os.path.join(EXPERIMENTS_DIR, f"{today}_experiment{tag}.json")
    save_results(results, json_path)
    md_path = os.path.join(EXPERIMENTS_DIR, f"{today}_experiment{tag}.md")
    save_markdown(results, md_path, title)

    # 요약
    print(f"\n{'='*65}")
    print("  요약")
    print(f"{'='*65}")
    for r in results:
        print(f"  {r['name']:20s}  {r['accuracy']*100:6.2f}%  ({r['time_s']}s)")


if __name__ == "__main__":
    main()
