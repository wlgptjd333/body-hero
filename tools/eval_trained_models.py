"""
저장된 pose_classifier.keras / pose_classifier_seq.keras 검증.
train_pose_classifier.py / train_pose_classifier_seq.py 와 동일한
데이터 경로·balance_ratio·val 분할·블록 샘플링으로 X_val을 재구성한 뒤 예측.
"""
from __future__ import annotations

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

DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
BALANCE_RATIO = 4.0
VAL_SIZE = 0.2
MAX_FRAMES_PER_BLOCK = 8
SEQ_LEN = 8


def _single_frame_val() -> tuple[np.ndarray, np.ndarray]:
    class_names = ALL_CLASS_NAMES.copy()
    X_list, y_list = load_data(DATA, class_names, skip_labels=["drop"])
    rng_load = np.random.RandomState(42)
    X_list, y_list = subsample_consecutive_blocks(
        X_list, y_list, MAX_FRAMES_PER_BLOCK, rng_load
    )
    X = np.array(X_list, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)
    counts = Counter(y)
    min_count = min(counts.values())
    max_per_class = int(min_count * BALANCE_RATIO)
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
        X, y, test_size=VAL_SIZE, stratify=y, random_state=42
    )
    return X_val, y_val


def _sequence_val() -> tuple[np.ndarray, np.ndarray]:
    class_names = ALL_CLASS_NAMES.copy()
    X_seqs, y_list = load_sequences_by_recordings(
        DATA, META, class_names, SEQ_LEN, skip_labels=["drop"]
    )
    X = np.array(X_seqs, dtype=np.float32)
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    y = np.array([label_to_idx[l] for l in y_list], dtype=np.int32)
    counts = Counter(y)
    min_count = min(counts.values())
    max_per_class = int(min_count * BALANCE_RATIO)
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
            X, y, test_size=VAL_SIZE, stratify=y, random_state=42
        )
    except ValueError:
        _, X_val, _, y_val = train_test_split(
            X, y, test_size=VAL_SIZE, random_state=42
        )
    return X_val, y_val


def main() -> None:
    class_names = ALL_CLASS_NAMES.copy()
    labels = list(range(len(class_names)))
    i_ul = class_names.index("upper_l")
    i_ur = class_names.index("upper_r")

    # Single-frame
    path_sf = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
    Xv, yv = _single_frame_val()
    m = tf.keras.models.load_model(path_sf, compile=False)
    pred = np.argmax(m.predict(Xv, batch_size=64, verbose=0), axis=1)
    acc = accuracy_score(yv, pred)
    cm = confusion_matrix(yv, pred, labels=labels)
    print("=== pose_classifier.keras (단일 프레임) ===")
    print(f"검증 샘플 수: {len(yv)}")
    print(f"정확도(accuracy): {acc * 100:.2f}%")
    print(classification_report(yv, pred, target_names=class_names, digits=4, zero_division=0))
    print(
        f"어퍼 L/R 혼동: upper_l→upper_r {cm[i_ul, i_ur]}건, "
        f"upper_r→upper_l {cm[i_ur, i_ul]}건"
    )
    print()

    # Sequence
    path_sq = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
    Xv2, yv2 = _sequence_val()
    ms = tf.keras.models.load_model(path_sq, compile=False)
    pred2 = np.argmax(ms.predict(Xv2, batch_size=64, verbose=0), axis=1)
    acc2 = accuracy_score(yv2, pred2)
    cm2 = confusion_matrix(yv2, pred2, labels=labels)
    print("=== pose_classifier_seq.keras (시퀀스, seq_len=8) ===")
    print(f"검증 샘플 수: {len(yv2)}")
    print(f"정확도(accuracy): {acc2 * 100:.2f}%")
    print(classification_report(yv2, pred2, target_names=class_names, digits=4, zero_division=0))
    print(
        f"어퍼 L/R 혼동: upper_l→upper_r {cm2[i_ul, i_ur]}건, "
        f"upper_r→upper_l {cm2[i_ur, i_ul]}건"
    )


if __name__ == "__main__":
    main()
