"""
저장된 pose_classifier.keras / pose_classifier_seq.keras 검증.
train_pose_classifier.py / train_pose_classifier_seq.py 와 동일한
데이터 경로·balance_ratio·val 분할로 X_val을 재구성한 뒤 예측.

실행 (tools 폴더, pose_data.json 필요):
  python eval_trained_models.py
  python eval_trained_models.py --data path/to/pose_data.json --only-seq
  python eval_trained_models.py --seq-model pose_classifier_seq.keras --counts-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np
import tensorflow as tf
from collections import Counter
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from train_pose_classifier import (
    ALL_CLASS_NAMES,
    load_data,
    subsample_consecutive_blocks,
)
from train_pose_classifier_seq import load_sequences_by_recordings

DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
MAX_FRAMES_PER_BLOCK = 8


def infer_seq_len_from_model(model: tf.keras.Model) -> int:
    inp = model.input_shape
    if isinstance(inp, (list, tuple)) and len(inp) >= 2 and inp[1] is not None:
        return int(inp[1])
    return 8


def print_frame_label_counts(data_path: str) -> None:
    """pose_data.json 원본 프레임 단위 라벨 개수 (학습 데이터 균형 점검용)."""
    if not os.path.isfile(data_path):
        print(f"데이터 없음: {data_path}")
        return
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    ctr: Counter[str] = Counter()
    for item in raw:
        lab = item.get("label")
        if isinstance(lab, str):
            ctr[lab] += 1
    print("=== pose_data.json 프레임 수(라벨별) ===")
    for name in ALL_CLASS_NAMES:
        print(f"  {name}: {ctr.get(name, 0)}")
    ul, ur = ctr.get("upper_l", 0), ctr.get("upper_r", 0)
    if ul + ur > 0:
        ratio = ul / max(1, ur)
        print(f"  upper_l / upper_r 비율 ≈ {ratio:.2f} (1.0에 가까울수록 L/R 균형)")


def _single_frame_val(
    data_path: str,
    balance_ratio: float,
    val_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    class_names = ALL_CLASS_NAMES.copy()
    X_list, y_list = load_data(data_path, class_names, skip_labels=["drop"])
    rng_load = np.random.RandomState(42)
    X_list, y_list = subsample_consecutive_blocks(
        X_list, y_list, MAX_FRAMES_PER_BLOCK, rng_load
    )
    X = np.array(X_list, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)
    counts = Counter(y)
    min_count = min(counts.values())
    max_per_class = int(min_count * balance_ratio)
    rng = np.random.RandomState(42)
    idx_keep: list[int] = []
    for cls in range(len(class_names)):
        inds = np.where(y == cls)[0]
        if len(inds) > max_per_class:
            inds = rng.choice(inds, size=max_per_class, replace=False)
        idx_keep.extend(inds.tolist())
    idx_keep = list(rng.permutation(idx_keep))
    X, y = X[idx_keep], y[idx_keep]
    _, X_val, _, y_val = train_test_split(
        X, y, test_size=val_size, stratify=y, random_state=42
    )
    return X_val, y_val


def _sequence_val(
    data_path: str,
    meta_path: str,
    seq_len: int,
    balance_ratio: float,
    val_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    class_names = ALL_CLASS_NAMES.copy()
    X_seqs, y_list = load_sequences_by_recordings(
        data_path, meta_path, class_names, seq_len, skip_labels=["drop"]
    )
    X = np.array(X_seqs, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)
    counts = Counter(y)
    min_count = min(counts.values())
    max_per_class = int(min_count * balance_ratio)
    rng = np.random.RandomState(42)
    idx_keep: list[int] = []
    for cls in range(len(class_names)):
        inds = np.where(y == cls)[0]
        if len(inds) > max_per_class:
            inds = rng.choice(inds, size=max_per_class, replace=False)
        idx_keep.extend(inds.tolist())
    idx_keep = list(rng.permutation(idx_keep))
    X, y = X[idx_keep], y[idx_keep]
    try:
        _, X_val, _, y_val = train_test_split(
            X, y, test_size=val_size, stratify=y, random_state=42
        )
    except ValueError:
        _, X_val, _, y_val = train_test_split(
            X, y, test_size=val_size, random_state=42
        )
    return X_val, y_val


def main() -> None:
    p = argparse.ArgumentParser(description="저장 모델 검증 (학습과 동일 val 분할)")
    p.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json")
    p.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json")
    p.add_argument("--balance-ratio", type=float, default=4.0)
    p.add_argument("--val", type=float, default=0.2, dest="val_size")
    p.add_argument(
        "--single-model",
        default=os.path.join(SCRIPT_DIR, "pose_classifier.keras"),
        help="단일 프레임 모델 경로",
    )
    p.add_argument(
        "--seq-model",
        default=os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras"),
        help="시퀀스 모델 경로",
    )
    p.add_argument("--only-seq", action="store_true", help="시퀀스 모델만 검증")
    p.add_argument(
        "--counts-only",
        action="store_true",
        help="pose_data.json 라벨 개수만 출력하고 종료",
    )
    p.add_argument(
        "--seq-len",
        type=int,
        default=None,
        help="시퀀스 길이(미지정 시 --seq-model 입력 차원에서 자동)",
    )
    args = p.parse_args()

    if args.counts_only:
        print_frame_label_counts(args.data)
        return

    if not os.path.isfile(args.data):
        print(
            "pose_data.json 을 찾을 수 없습니다:\n",
            f"  {args.data}\n",
            "데이터가 있는 PC에서:\n",
            "  cd tools\n",
            "  python eval_trained_models.py\n",
            "또는 라벨 균형만 보려면 collect 후:\n",
            "  python eval_trained_models.py --counts-only --data <경로>",
            sep="",
        )
        sys.exit(2)

    print_frame_label_counts(args.data)
    print()

    class_names = ALL_CLASS_NAMES.copy()
    labels = list(range(len(class_names)))
    i_ul = class_names.index("upper_l")
    i_ur = class_names.index("upper_r")

    if not args.only_seq:
        if not os.path.isfile(args.single_model):
            print(f"단일 프레임 모델 없음(건너뜀): {args.single_model}\n")
        else:
            Xv, yv = _single_frame_val(args.data, args.balance_ratio, args.val_size)
            m = tf.keras.models.load_model(args.single_model, compile=False)
            pred = np.argmax(m.predict(Xv, batch_size=64, verbose=0), axis=1)
            acc = accuracy_score(yv, pred)
            cm = confusion_matrix(yv, pred, labels=labels)
            print(f"=== {os.path.basename(args.single_model)} (단일 프레임) ===")
            print(f"검증 샘플 수: {len(yv)}")
            print(f"정확도(accuracy): {acc * 100:.2f}%")
            print(
                classification_report(
                    yv, pred, target_names=class_names, digits=4, zero_division=0
                )
            )
            print(
                f"어퍼 L/R 혼동: upper_l→upper_r {cm[i_ul, i_ur]}건, "
                f"upper_r→upper_l {cm[i_ur, i_ul]}건"
            )
            print()

    if not os.path.isfile(args.seq_model):
        print(f"시퀀스 모델 없음: {args.seq_model}")
        sys.exit(1)

    ms = tf.keras.models.load_model(args.seq_model, compile=False)
    seq_len = args.seq_len if args.seq_len is not None else infer_seq_len_from_model(ms)
    Xv2, yv2 = _sequence_val(
        args.data, args.meta, seq_len, args.balance_ratio, args.val_size
    )
    pred2 = np.argmax(ms.predict(Xv2, batch_size=64, verbose=0), axis=1)
    acc2 = accuracy_score(yv2, pred2)
    cm2 = confusion_matrix(yv2, pred2, labels=labels)
    print(f"=== {os.path.basename(args.seq_model)} (시퀀스, seq_len={seq_len}) ===")
    print(f"검증 샘플 수: {len(yv2)}")
    print(f"정확도(accuracy): {acc2 * 100:.2f}%")
    print(
        classification_report(
            yv2, pred2, target_names=class_names, digits=4, zero_division=0
        )
    )
    print(
        f"어퍼 L/R 혼동: upper_l→upper_r {cm2[i_ul, i_ur]}건, "
        f"upper_r→upper_l {cm2[i_ur, i_ul]}건"
    )
    # upper_l 이 다른 클래스로 새는 비중
    ul_mask = yv2 == i_ul
    if np.any(ul_mask):
        wrong = int(np.sum(pred2[ul_mask] != i_ul))
        print(
            f"upper_l 정답 중 오답 비율: {wrong}/{int(np.sum(ul_mask))} "
            f"({100.0 * wrong / np.sum(ul_mask):.1f}%)"
        )


if __name__ == "__main__":
    main()
