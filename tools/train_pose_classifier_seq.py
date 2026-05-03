"""
연속 프레임(시퀀스) 포즈 분류: pose_data.json + pose_recordings_meta.json 그대로 사용.
녹화 구간별로 슬라이딩 윈도우해 (seq_len 프레임, 기본 4) → LSTM/Conv1D → 동작 분류.
단일 프레임 학습과 동일한 데이터·라벨 형식, 메타로 구간만 구분해 시퀀스만 생성.

저장 경로:
  --seq-len 4 (기본) → pose_classifier_seq_len4.keras  (게임/추론 측 우선 로드 모델, 콤보 우선·저지연)
  --seq-len 8        → pose_classifier_seq.keras       (안정성 우선/비교용)
  그 외 길이는 --model 로 직접 지정.

실행:
  python train_pose_classifier_seq.py            # 기본 4프레임 학습
  python train_pose_classifier_seq.py --seq-len 8  # 8프레임 모델 별도 학습

기본: 좌우반전 증강 + 펀치/어퍼 L:R 소수 오버샘플(lr_pose_utils). 리포트: report_pose_lr_balance.py

게임/추론 측(udp_send_webcam_ml.py / pose_server.py / test_pose_live.py)은
pose_classifier_seq_len4.keras 가 있으면 그것을 우선 로드합니다. 학습 종료 시
저장 파일이 게임 우선 모델과 다르면 콘솔에 경고를 출력합니다.
"""
import os
import json
import argparse

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")
DEFAULT_MODEL_LEN8 = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")

from pose_class_names import POSE_CLASS_NAMES

ALL_CLASS_NAMES = list(POSE_CLASS_NAMES)
FEATURE_DIM = 33 * 3
NUM_LANDMARKS = 33


def load_sequences_by_recordings(data_path, meta_path, class_names, seq_len, skip_labels=None):
    """pose_data.json + pose_recordings_meta.json에서 녹화 구간별로 시퀀스 생성.

    라벨: **원본 타임라인**에서 연속 seq_len 프레임의 **가운데 인덱스** 프레임 라벨.
    impact_idx가 있으면(구 collect 임팩트 모드) 해당 녹화에서 임팩트 프레임부터 끝까지만 구간으로 사용.
    없거나 생략이면 녹화 전체(frame_count) 구간을 사용(전 프레임 단일 라벨 수집과 맞음).

    주의(이전 버전 버그): drop/none 등을 건너뛰며 랜드마크만 압축하면 시간축이 깨져
    어퍼처럼 짧은 동작 구간이 시퀀스에 거의 안 들어가는 문제가 생길 수 있음.
    지금은 **데이터 배열의 연속 인덱스**로만 윈도우를 잡음.
    """
    skip_labels = skip_labels or []
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not os.path.isfile(meta_path):
        return _sequences_from_runs(data, class_names, seq_len, skip_labels)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    recordings = meta.get("recordings", [])
    if not isinstance(recordings, list):
        return _sequences_from_runs(data, class_names, seq_len, skip_labels)
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
        # 연속 인덱스 [win_start, win_start+seq_len) — drop이 끼어 있어도 시간축 유지
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
            if clab not in class_names or clab in skip_labels:
                continue
            X_seqs.append(np.array(seq_list, dtype=np.float32))
            y_list.append(clab)
    return X_seqs, y_list


def _sequences_from_runs(data, class_names, seq_len, skip_labels):
    """메타 없을 때: 연속 동일 라벨 구간(run) 내에서만 시퀀스 생성."""
    X_list = []
    y_list = []
    i = 0
    while i < len(data):
        item = data[i]
        lm = item.get("landmarks")
        label = item.get("label")
        if not lm or label not in class_names or label in skip_labels:
            i += 1
            continue
        j = i
        run_frames = []
        run_labels = []
        while j < len(data):
            it = data[j]
            lm2 = it.get("landmarks")
            lb = it.get("label")
            if not lm2 or len(lm2) != FEATURE_DIM or lb not in class_names or lb in skip_labels:
                j += 1
                continue
            if lb != label:
                break
            run_frames.append(lm2)
            run_labels.append(lb)
            j += 1
        if len(run_frames) >= seq_len:
            run_frames = np.array(run_frames, dtype=np.float32)
            for k in range(0, len(run_frames) - seq_len + 1):
                seq = run_frames[k : k + seq_len]
                center = k + seq_len // 2
                X_list.append(seq)
                y_list.append(run_labels[center])
        i = j if j > i else i + 1
    return X_list, y_list


def main():
    parser = argparse.ArgumentParser(description="Train sequence pose classifier (same pose_data.json)")
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json (녹화 구간)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--seq-len",
        type=int,
        default=4,
        help=(
            "연속 프레임 수 (기본 4 — 게임/추론 측이 4프레임 모델을 우선 사용, 콤보 우선·저지연). "
            "8 등 다른 값을 지정하면 그에 맞는 모델 파일이 따로 만들어집니다."
        ),
    )
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--val", type=float, default=0.2)
    parser.add_argument("--balance-ratio", type=float, default=4.0)
    parser.add_argument("--patience", type=int, default=22)
    parser.add_argument("--augment", type=float, default=0.03)
    parser.add_argument(
        "--flip-augment",
        action="store_true",
        default=True,
        help="시퀀스 각 프레임 좌우반전 + L/R 라벨 스왑 샘플 추가 (train_pose_classifier와 동일, upper L/R 균형에 권장)",
    )
    parser.add_argument(
        "--no-flip-augment",
        action="store_false",
        dest="flip_augment",
        help="좌우 반전 증강 끔",
    )
    parser.add_argument(
        "--balance-lr-pairs",
        action="store_true",
        default=True,
        help="펀치/어퍼 각 L:R 쌍에서 적은 쪽 시퀀스를 복제해 오버샘플 (기본 켬)",
    )
    parser.add_argument(
        "--no-balance-lr-pairs",
        action="store_false",
        dest="balance_lr_pairs",
        help="L/R 쌍 오버샘플 끔",
    )
    parser.add_argument(
        "--lr-oversample-max-ratio",
        type=float,
        default=6.0,
        help="소수 클래스를 원본 대비 최대 몇 배까지 늘릴지(다수 쪽 개수 상한은 min(다수, 소수*이 값))",
    )
    args = parser.parse_args()

    # seq_len=8 은 별도 파일명(pose_classifier_seq.keras)으로 저장.
    # 기본 4는 pose_classifier_seq_len4.keras (게임 우선 로드 모델) 유지.
    if args.seq_len == 8 and os.path.abspath(args.model) == os.path.abspath(DEFAULT_MODEL):
        args.model = DEFAULT_MODEL_LEN8

    class_names = ALL_CLASS_NAMES.copy()
    num_classes = len(class_names)

    try:
        import tensorflow as tf
        from sklearn.model_selection import train_test_split
        from sklearn.utils.class_weight import compute_class_weight
        from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
    except ImportError as e:
        print("pip install tensorflow scikit-learn numpy")
        raise SystemExit(1) from e

    if not os.path.isfile(args.data):
        print(f"데이터 없음: {args.data}")
        raise SystemExit(1)

    X_seqs, y_list = load_sequences_by_recordings(
        args.data, args.meta, class_names, args.seq_len, skip_labels=["drop"]
    )
    if len(X_seqs) < 30:
        print(f"시퀀스가 너무 적습니다 ({len(X_seqs)}). seq_len을 줄이거나 데이터를 더 수집하세요.")
        raise SystemExit(1)

    X = np.array(X_seqs, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)

    from collections import Counter
    counts = Counter(y)
    print(f"시퀀스 수 (seq_len={args.seq_len}): {len(X)}")
    print("클래스별 시퀀스 수:")
    for i, name in enumerate(class_names):
        print(f"  {name}: {counts.get(i, 0)}")

    if args.balance_ratio > 0:
        min_count = min(counts.values())
        max_per_class = int(min_count * args.balance_ratio)
        rng = np.random.RandomState(42)
        idx_keep = []
        for cls in range(num_classes):
            mask = (y == cls)
            inds = np.where(mask)[0]
            if len(inds) > max_per_class:
                inds = rng.choice(inds, size=max_per_class, replace=False)
            idx_keep.extend(inds.tolist())
        idx_keep = rng.permutation(idx_keep)
        X = X[idx_keep]
        y = y[idx_keep]
        print(f"균형 조정 후 (ratio={args.balance_ratio}): {len(X)} 시퀀스")

    try:
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=args.val, stratify=y, random_state=42
        )
    except ValueError:
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=args.val, random_state=42)

    if args.flip_augment:
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
                    X_flip[i, t] = apply_horizontal_flip(seq[t : t + 1])[0]
            y_flip = swap[y_train]
            X_train = np.concatenate([X_train, X_flip], axis=0)
            y_train = np.concatenate([y_train, y_flip], axis=0)
            print(f"증강(좌우반전+L/R스왑): 시퀀스 {len(X_train)} (train)")

    if args.augment > 0:
        rng = np.random.RandomState(43)
        X_noise = X_train + rng.normal(0, args.augment, X_train.shape).astype(np.float32)
        X_train = np.concatenate([X_train, X_noise], axis=0)
        y_train = np.concatenate([y_train, y_train], axis=0)
        print(f"증강(노이즈 std={args.augment}): 학습 시퀀스 {len(X_train)}")

    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(args.seq_len, FEATURE_DIM)),
        tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    # val_accuracy 는 1.0 같은 값에서 동률이 자주 발생해 best 갱신이 막히고
    # 첫 100% 도달 가중치만 복원되는 문제가 있어서 val_loss 기준으로 모니터링.
    # ReduceLROnPlateau 도 val_loss 를 보므로 콜백 일관성도 유지된다.
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", mode="min", patience=args.patience,
        restore_best_weights=True, verbose=1,
    )
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=7, min_lr=1e-6, verbose=1
    )

    print(f"\n학습 시퀀스: {len(X_train)} / 검증: {len(X_val)}")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=32,
        class_weight=class_weight,
        callbacks=[early, reduce_lr],
        verbose=1,
    )

    hist = {k: [float(x) for x in v] for k, v in history.history.items()}
    with open(os.path.join(SCRIPT_DIR, "training_history_seq.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2)

    y_val_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_val, y_val_pred, labels=list(range(num_classes)), zero_division=0
    )
    print("\n[동작별 정확도 (검증 세트)]")
    print("  동작      recall  precision  (샘플 수)")
    for i in range(num_classes):
        print(f"  {class_names[i]:8s}  {recall[i]*100:5.1f}%   {precision[i]*100:5.1f}%     ({int(support[i])})")
    report = classification_report(
        y_val, y_val_pred, labels=list(range(num_classes)), target_names=class_names, digits=4, zero_division=0
    )
    print("\n[검증 세트 분류 리포트]\n" + report)
    cm_val = confusion_matrix(y_val, y_val_pred, labels=list(range(num_classes)))
    print("혼동 행렬 (validation):")
    print(cm_val)

    from lr_pose_utils import lr_confusion_hints

    lr_hints = lr_confusion_hints(class_names, cm_val)

    report_path = os.path.join(SCRIPT_DIR, "classification_report_seq.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        f.write("\n\nConfusion matrix:\n")
        f.write(str(cm_val))
        f.write("\n\n[L/R 쌍 상호 오분류 힌트]\n")
        f.write(lr_hints + "\n")
    print("\n[L/R 쌍 상호 오분류 힌트]\n" + lr_hints)

    val_acc = model.evaluate(X_val, y_val, verbose=0)[1]
    print(f"\n최종 검증 정확도: {val_acc*100:.1f}%")
    out = args.model
    if not out.endswith(".keras"):
        out = out + ".keras" if not os.path.splitext(out)[1] else out
    model.save(out)
    print(f"모델 저장: {out}")

    _warn_if_runtime_uses_other_model(out)


def _warn_if_runtime_uses_other_model(saved_path: str) -> None:
    """게임/추론 측이 실제로 로드할 모델과 방금 저장한 모델이 다르면 경고.

    udp_send_webcam_ml.py / pose_server.py / test_pose_live.py 는
    `pose_classifier_seq_len4.keras`(있으면)을 우선하고, 없을 때만
    `pose_classifier_seq.keras` 로 폴백한다. 다른 파일을 학습해 저장하면
    게임에는 이 학습 결과가 반영되지 않아 사용자가 "재학습했는데 체감이 그대로"
    라고 느낄 수 있어 명시적으로 알려준다.
    """
    try:
        saved_abs = os.path.abspath(saved_path)
        runtime_pref = (
            DEFAULT_MODEL
            if os.path.isfile(DEFAULT_MODEL)
            else DEFAULT_MODEL_LEN8
        )
        runtime_abs = os.path.abspath(runtime_pref)
        if saved_abs == runtime_abs:
            return
        print()
        print("⚠ 학습한 모델 파일이 게임 실행 시 우선 로드되는 파일과 다릅니다.")
        print(f"   - 방금 저장: {saved_abs}")
        print(f"   - 게임 우선 로드: {runtime_abs}")
        print("   현재 udp_send_webcam_ml.py / pose_server.py / test_pose_live.py 는")
        print("   pose_classifier_seq_len4.keras 가 있으면 그것을 먼저 사용합니다.")
        print("   이 학습 결과를 실제 게임에 반영하려면:")
        if os.path.basename(runtime_abs) == "pose_classifier_seq_len4.keras":
            print("     1) `python train_pose_classifier_seq.py --seq-len 4` 로 재학습하거나")
            print(f"     2) 방금 저장한 파일을 {runtime_abs} 로 교체하세요.")
        else:
            print(f"     방금 저장한 파일을 {runtime_abs} 로 교체하세요.")
    except Exception:
        pass


if __name__ == "__main__":
    main()
