# -*- coding: utf-8 -*-
# 원본: Downloads/body_hero.ipynb 9번 셀(코덱스 2x2 실험). 증강 버그 2곳과 경로만 수정함.
# ============================================================
# Body Hero - Thesis Final 2x2 Experiment
#
# 2 x 2 factorial comparison
#
# Factor A: Sequence length
#   - 2 frames
#   - 4 frames
#
# Factor B: Architecture
#   - Conv1D + LSTM
#   - Conv1D + GAP
#
# Repeated training:
#   5 training seeds
#
# Total:
#   4 models x 5 seeds = 20 training runs
#
# IMPORTANT:
#   - Recording-level train/validation split
#   - Split is FIXED across all 20 runs
#   - Only training seed changes
#   - Same validation recordings for every model
#   - Validation data is never augmented
#   - Each completed run is immediately saved
#   - Safe to resume after Colab disconnection
# ============================================================

import os
import json
import random
import gc
import time
import subprocess

import numpy as np
import pandas as pd
import tensorflow as tf

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)


# ============================================================
# 0. Google Drive
# ============================================================

# IMPORTANT:
# Run this once before executing the experiment:
#
# from google.colab import drive
# drive.mount("/content/drive")

DRIVE_ROOT = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 1. Paths / experiment configuration
# ============================================================

ROOT = r"C:\Users\User\Documents\body-hero"
TOOLS = os.path.join(ROOT, "tools")

# ------------------------------------------------------------
# SAVE EXPERIMENT RESULTS TO GOOGLE DRIVE
# ------------------------------------------------------------

RESULT_DIR = os.path.join(
    DRIVE_ROOT,
    "results"
)

os.makedirs(
    RESULT_DIR,
    exist_ok=True
)

DATA_PATH = os.path.join(
    TOOLS,
    "pose_data.json"
)

META_PATH = os.path.join(
    TOOLS,
    "pose_recordings_meta.json"
)


# ------------------------------------------------------------
# FIXED DATA SPLIT
# ------------------------------------------------------------

SPLIT_SEED = 42
VAL_RATIO = 0.20


# ------------------------------------------------------------
# FIVE TRAINING SEEDS
# ------------------------------------------------------------

TRAINING_SEEDS = [
    42,
    43,
    44,
    45,
    46,
]


# ------------------------------------------------------------
# MODEL CONDITIONS
# ------------------------------------------------------------

SEQ_LENS = [
    2,
    4,
]

ARCHITECTURES = [
    "lstm",
    "gap",
]


# ------------------------------------------------------------
# Training hyperparameters
# ------------------------------------------------------------

EPOCHS = 120
BATCH_SIZE = 32
LEARNING_RATE = 1e-3

EARLY_STOP_PATIENCE = 22
LR_PATIENCE = 7


# ------------------------------------------------------------
# Existing Body Hero sequence training profile
# ------------------------------------------------------------

BALANCE_RATIO = 4.0

GAUSSIAN_NOISE_STD = 0.03

XY_SCALE_MIN = 0.80
XY_SCALE_MAX = 1.20


# ------------------------------------------------------------
# Classes
# ------------------------------------------------------------

CLASS_NAMES = [
    "none",
    "guard",
    "punch_l",
    "punch_r",
    "upper_l",
    "upper_r",
    "squat",
]

LABEL_TO_ID = {
    name: i
    for i, name in enumerate(CLASS_NAMES)
}

SKIP_LABELS = {
    "drop"
}


print("=" * 80)
print("BODY HERO - THESIS 2x2 EXPERIMENT")
print("=" * 80)

print("TensorFlow:", tf.__version__)

print(
    "GPU:",
    tf.config.list_physical_devices("GPU")
)

print(
    "Training seeds:",
    TRAINING_SEEDS
)

total_runs = (
    len(SEQ_LENS)
    * len(ARCHITECTURES)
    * len(TRAINING_SEEDS)
)

print(
    "Total runs:",
    total_runs
)

print(
    "Result directory:",
    RESULT_DIR
)


# ============================================================
# 2. Load data
# ============================================================

print("\nLoading data...")

with open(
    DATA_PATH,
    "r",
    encoding="utf-8"
) as f:
    pose_data = json.load(f)


with open(
    META_PATH,
    "r",
    encoding="utf-8"
) as f:
    meta = json.load(f)


recordings = meta["recordings"]

print(
    "Total frames:",
    len(pose_data)
)

print(
    "Total recordings:",
    len(recordings)
)


# ============================================================
# 3. Convert pose data
# ============================================================

X_all = np.asarray(
    [
        item["landmarks"]
        for item in pose_data
    ],
    dtype=np.float32
)

labels_all = np.asarray(
    [
        item["label"]
        for item in pose_data
    ],
    dtype=object
)

print(
    "Pose array:",
    X_all.shape
)

assert X_all.shape[1] == 99


# ============================================================
# 4. Create FIXED recording-level split
# ============================================================

def build_recording_split(
    recordings,
    val_ratio,
    seed,
):

    rng = np.random.default_rng(seed)

    label_to_recordings = {}

    for record_id, rec in enumerate(recordings):

        label = rec["label"]

        if label in SKIP_LABELS:
            continue

        label_to_recordings.setdefault(
            label,
            []
        ).append(record_id)

    train_ids = []
    val_ids = []

    for label in CLASS_NAMES:

        indices = list(
            label_to_recordings.get(
                label,
                []
            )
        )

        if len(indices) == 0:
            continue

        rng.shuffle(indices)

        n_val = max(
            1,
            int(
                len(indices)
                * val_ratio
            )
        )

        val_ids.extend(
            indices[:n_val]
        )

        train_ids.extend(
            indices[n_val:]
        )

    return (
        sorted(train_ids),
        sorted(val_ids)
    )


SPLIT_PATH = os.path.join(
    RESULT_DIR,
    "recording_split.json"
)


# ------------------------------------------------------------
# IMPORTANT:
# Reuse existing split if experiment was already started.
# ------------------------------------------------------------

if os.path.exists(SPLIT_PATH):

    print(
        "\nExisting recording split found."
    )

    print(
        "Reusing the original fixed split."
    )

    with open(
        SPLIT_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        split_info = json.load(f)

    train_record_ids = (
        split_info["train_record_ids"]
    )

    val_record_ids = (
        split_info["validation_record_ids"]
    )

    if (
        split_info["split_seed"]
        != SPLIT_SEED
    ):

        raise RuntimeError(
            "Existing split seed does not "
            "match current SPLIT_SEED."
        )

else:

    (
        train_record_ids,
        val_record_ids
    ) = build_recording_split(
        recordings,
        VAL_RATIO,
        SPLIT_SEED,
    )

    with open(
        SPLIT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "split_seed": SPLIT_SEED,
                "validation_ratio": VAL_RATIO,
                "train_record_ids": train_record_ids,
                "validation_record_ids": val_record_ids,
            },
            f,
            indent=2,
        )


print("\nFIXED RECORDING SPLIT")
print("---------------------")

print(
    "Train recordings:",
    len(train_record_ids)
)

print(
    "Validation recordings:",
    len(val_record_ids)
)


# ============================================================
# 5. Sequence extraction
# ============================================================

def extract_sequences(
    record_ids,
    seq_len,
):

    sequences = []
    labels = []
    centers = []
    recording_ids = []

    for record_id in record_ids:

        rec = recordings[record_id]

        start = int(
            rec["start_index"]
        )

        count = int(
            rec["frame_count"]
        )

        if (
            "impact_idx" in rec
            and rec["impact_idx"] is not None
        ):

            impact_idx = int(
                rec["impact_idx"]
            )

            start += impact_idx

            count -= impact_idx

        end = start + count

        end = min(
            end,
            len(X_all)
        )

        if count < seq_len:
            continue

        for win_start in range(
            start,
            end - seq_len + 1
        ):

            win_end = (
                win_start
                + seq_len
            )

            center = (
                win_start
                + seq_len // 2
            )

            center_label = (
                labels_all[center]
            )

            if (
                center_label
                in SKIP_LABELS
            ):
                continue

            if (
                center_label
                not in LABEL_TO_ID
            ):
                continue

            seq = X_all[
                win_start:win_end
            ]

            if seq.shape != (
                seq_len,
                99
            ):
                continue

            sequences.append(seq)

            labels.append(
                LABEL_TO_ID[
                    center_label
                ]
            )

            centers.append(
                center
            )

            recording_ids.append(
                record_id
            )

    return (
        np.asarray(
            sequences,
            dtype=np.float32
        ),
        np.asarray(
            labels,
            dtype=np.int64
        ),
        np.asarray(
            centers,
            dtype=np.int64
        ),
        np.asarray(
            recording_ids,
            dtype=np.int64
        ),
    )


# ============================================================
# 6. Training balance
# ============================================================

def balance_sequences(
    X,
    y,
    centers,
    recording_ids,
    seed,
):

    rng = np.random.default_rng(
        seed
    )

    counts = {}

    for class_id in range(
        len(CLASS_NAMES)
    ):

        indices = np.where(
            y == class_id
        )[0]

        if len(indices):
            counts[class_id] = len(
                indices
            )

    if not counts:

        raise RuntimeError(
            "No training sequences."
        )

    min_count = min(
        counts.values()
    )

    target_max = int(
        min_count
        * BALANCE_RATIO
    )

    selected = []

    for class_id in range(
        len(CLASS_NAMES)
    ):

        indices = np.where(
            y == class_id
        )[0]

        if len(indices) == 0:
            continue

        if len(indices) > target_max:

            indices = rng.choice(
                indices,
                size=target_max,
                replace=False,
            )

        selected.extend(
            indices.tolist()
        )

    selected = np.asarray(
        selected
    )

    rng.shuffle(
        selected
    )

    return (
        X[selected],
        y[selected],
        centers[selected],
        recording_ids[selected],
    )


# ============================================================
# 7. Augmentation
# ============================================================

LR_PAIRS = [
    (1, 4),
    (2, 5),
    (3, 6),
    (7, 8),
    (11, 12),
    (13, 14),
    (15, 16),
    (17, 18),
    (19, 20),
    (21, 22),
    (23, 24),
    (25, 26),
    (27, 28),
    (29, 30),
    (31, 32),
]

FLIP_LABEL_MAP = {

    LABEL_TO_ID["punch_l"]:
        LABEL_TO_ID["punch_r"],

    LABEL_TO_ID["punch_r"]:
        LABEL_TO_ID["punch_l"],

    LABEL_TO_ID["upper_l"]:
        LABEL_TO_ID["upper_r"],

    LABEL_TO_ID["upper_r"]:
        LABEL_TO_ID["upper_l"],
}


def augment_training_data(
    X,
    y,
    seed,
):

    rng = np.random.default_rng(
        seed
    )

    X_aug = X.copy()

    # --------------------------------------------------------
    # Gaussian noise
    # --------------------------------------------------------

    noise = rng.normal(
        0.0,
        GAUSSIAN_NOISE_STD,
        size=X_aug.shape,
    ).astype(
        np.float32
    )

    X_aug += noise

    # --------------------------------------------------------
    # XY scaling
    # --------------------------------------------------------

    scale = rng.uniform(
        XY_SCALE_MIN,
        XY_SCALE_MAX,
        size=(
            len(X_aug),
            1,
            1,
        ),
    ).astype(
        np.float32
    )

    # [수정] 모든 관절의 x, y에 스케일 적용 (기존 0:2 는 코 좌표만 변경)
    X_aug[:, :, 0::3] *= scale
    X_aug[:, :, 1::3] *= scale

    # --------------------------------------------------------
    # Horizontal flip
    # --------------------------------------------------------

    X_flip = X_aug.copy()

    # [수정] 모든 관절의 x 부호를 뒤집은 뒤 좌우 쌍을 교환해야 실제 거울상이 됨 (기존은 코 x만 반전)
    X_flip[:, :, 0::3] *= -1.0

    for left, right in LR_PAIRS:

        left_start = left * 3
        right_start = right * 3

        temp = X_flip[
            :,
            :,
            left_start:left_start + 3
        ].copy()

        X_flip[
            :,
            :,
            left_start:left_start + 3
        ] = X_flip[
            :,
            :,
            right_start:right_start + 3
        ]

        X_flip[
            :,
            :,
            right_start:right_start + 3
        ] = temp

    y_flip = y.copy()

    for source, target in (
        FLIP_LABEL_MAP.items()
    ):

        y_flip[
            y == source
        ] = target

    X_final = np.concatenate(
        [
            X_aug,
            X_flip,
        ],
        axis=0
    )

    y_final = np.concatenate(
        [
            y,
            y_flip,
        ],
        axis=0
    )

    return (
        X_final.astype(
            np.float32
        ),
        y_final.astype(
            np.int64
        ),
    )


# ============================================================
# 8. Model
# ============================================================

def build_model(
    seq_len,
    architecture,
):

    inputs = tf.keras.Input(
        shape=(
            seq_len,
            99
        ),
        name="pose_sequence"
    )

    x = tf.keras.layers.Conv1D(
        64,
        kernel_size=3,
        padding="same",
        activation="relu",
        name="conv1d",
    )(inputs)

    x = tf.keras.layers.BatchNormalization(
        name="batch_norm"
    )(x)

    x = tf.keras.layers.Dropout(
        0.25,
        name="dropout_conv",
    )(x)

    if architecture == "lstm":

        x = tf.keras.layers.LSTM(
            64,
            return_sequences=False,
            name="lstm",
        )(x)

    elif architecture == "gap":

        x = tf.keras.layers.GlobalAveragePooling1D(
            name="global_average_pooling"
        )(x)

    else:

        raise ValueError(
            architecture
        )

    x = tf.keras.layers.Dropout(
        0.30,
        name="dropout_head",
    )(x)

    outputs = tf.keras.layers.Dense(
        len(CLASS_NAMES),
        activation="softmax",
        name="classifier",
    )(x)

    model = tf.keras.Model(
        inputs,
        outputs,
        name=(
            f"conv1d_{architecture}"
            f"_seq{seq_len}"
        ),
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(
            learning_rate=LEARNING_RATE
        ),
        loss=(
            "sparse_categorical_crossentropy"
        ),
        metrics=[
            "accuracy"
        ],
    )

    return model


# ============================================================
# 9. Validation data cache
# ============================================================

print("\nPreparing validation sets...")

validation_cache = {}

for seq_len in SEQ_LENS:

    (
        X_val,
        y_val,
        centers,
        record_ids
    ) = extract_sequences(
        val_record_ids,
        seq_len,
    )

    validation_cache[
        seq_len
    ] = (
        X_val,
        y_val,
        centers,
        record_ids,
    )

    print(
        f"\nseq_len={seq_len}"
    )

    print(
        "X:",
        X_val.shape
    )

    print(
        "Class counts:",
        np.bincount(
            y_val,
            minlength=len(
                CLASS_NAMES
            )
        )
    )


# ============================================================
# 10. Evaluation
# ============================================================

def evaluate_model(
    model,
    X_val,
    y_val,
    seq_len,
    architecture,
    seed,
):

    probs = model.predict(
        X_val,
        batch_size=512,
        verbose=0,
    )

    predictions = np.argmax(
        probs,
        axis=1
    )

    accuracy = accuracy_score(
        y_val,
        predictions,
    )

    macro_f1 = f1_score(
        y_val,
        predictions,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        y_val,
        predictions,
        average="weighted",
        zero_division=0,
    )

    true_probs = probs[
        np.arange(
            len(y_val)
        ),
        y_val,
    ]

    report = classification_report(
        y_val,
        predictions,
        labels=list(
            range(
                len(CLASS_NAMES)
            )
        ),
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(
        y_val,
        predictions,
        labels=list(
            range(
                len(CLASS_NAMES)
            )
        ),
    )

    result = {

        "seed":
            seed,

        "architecture":
            architecture,

        "seq_len":
            seq_len,

        "accuracy":
            float(
                accuracy
            ),

        "macro_f1":
            float(
                macro_f1
            ),

        "weighted_f1":
            float(
                weighted_f1
            ),

        "mean_true_class_probability":
            float(
                np.mean(
                    true_probs
                )
            ),

        "std_true_class_probability":
            float(
                np.std(
                    true_probs
                )
            ),
    }


    # --------------------------------------------------------
    # Per-class F1
    # --------------------------------------------------------

    for class_name in CLASS_NAMES:

        result[
            f"f1_{class_name}"
        ] = float(
            report[
                class_name
            ][
                "f1-score"
            ]
        )


    # --------------------------------------------------------
    # Same-label neighboring probability stability
    # --------------------------------------------------------

    deltas = []

    for i in range(
        1,
        len(probs)
    ):

        if (
            y_val[i]
            != y_val[i - 1]
        ):
            continue

        previous_prob = probs[
            i - 1,
            y_val[i]
        ]

        current_prob = probs[
            i,
            y_val[i]
        ]

        deltas.append(
            abs(
                float(
                    current_prob
                    - previous_prob
                )
            )
        )

    if deltas:

        deltas = np.asarray(
            deltas
        )

        result[
            "stability_n"
        ] = int(
            len(deltas)
        )

        result[
            "mean_abs_probability_delta_pp"
        ] = float(
            np.mean(
                deltas
            ) * 100.0
        )

        result[
            "median_abs_probability_delta_pp"
        ] = float(
            np.median(
                deltas
            ) * 100.0
        )

        result[
            "p95_abs_probability_delta_pp"
        ] = float(
            np.percentile(
                deltas,
                95
            ) * 100.0
        )

    else:

        result[
            "stability_n"
        ] = 0

        result[
            "mean_abs_probability_delta_pp"
        ] = np.nan

        result[
            "median_abs_probability_delta_pp"
        ] = np.nan

        result[
            "p95_abs_probability_delta_pp"
        ] = np.nan


    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    cm_path = os.path.join(
        RESULT_DIR,
        (
            f"confusion_"
            f"{architecture}_"
            f"seq{seq_len}_"
            f"seed{seed}.csv"
        ),
    )

    pd.DataFrame(
        cm,
        index=CLASS_NAMES,
        columns=CLASS_NAMES,
    ).to_csv(
        cm_path,
        encoding="utf-8-sig"
    )


    # --------------------------------------------------------
    # Probability output
    # --------------------------------------------------------

    probability_path = os.path.join(
        RESULT_DIR,
        (
            f"probabilities_"
            f"{architecture}_"
            f"seq{seq_len}_"
            f"seed{seed}.npy"
        ),
    )

    np.save(
        probability_path,
        probs,
    )

    return result


# ============================================================
# 11. Resume helper
# ============================================================

def run_key(
    architecture,
    seq_len,
    seed,
):

    return (
        f"{architecture}_"
        f"seq{seq_len}_"
        f"seed{seed}"
    )


def result_path_for_run(
    architecture,
    seq_len,
    seed,
):

    return os.path.join(
        RESULT_DIR,
        (
            f"result_"
            f"{architecture}_"
            f"seq{seq_len}_"
            f"seed{seed}.json"
        ),
    )


def load_completed_results():

    completed = []

    for seq_len in SEQ_LENS:

        for architecture in ARCHITECTURES:

            for seed in TRAINING_SEEDS:

                path = result_path_for_run(
                    architecture,
                    seq_len,
                    seed,
                )

                if not os.path.exists(path):
                    continue

                try:

                    with open(
                        path,
                        "r",
                        encoding="utf-8"
                    ) as f:

                        result = json.load(f)

                    completed.append(
                        result
                    )

                except Exception as e:

                    print(
                        "WARNING:",
                        "Could not read",
                        path,
                        e
                    )

    return completed


completed_results = load_completed_results()

completed_keys = {
    run_key(
        r["architecture"],
        r["seq_len"],
        r["seed"],
    )
    for r in completed_results
}


print("\nRESUME STATUS")
print("-------------")

print(
    "Completed runs:",
    len(completed_results),
    "/",
    total_runs
)

print(
    "Remaining runs:",
    total_runs
    - len(completed_results)
)


# ============================================================
# 12. Experiment configuration
# ============================================================

CONFIG_PATH = os.path.join(
    RESULT_DIR,
    "experiment_config.json"
)


def get_git_commit():

    try:

        return subprocess.check_output(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=ROOT,
            text=True,
        ).strip()

    except Exception:

        return "unknown"


if not os.path.exists(CONFIG_PATH):

    config = {

        "experiment":
            "2x2 factorial repeated training",

        "git_commit":
            get_git_commit(),

        "tensorflow":
            tf.__version__,

        "split_seed":
            SPLIT_SEED,

        "validation_ratio":
            VAL_RATIO,

        "training_seeds":
            TRAINING_SEEDS,

        "sequence_lengths":
            SEQ_LENS,

        "architectures":
            ARCHITECTURES,

        "total_runs":
            total_runs,

        "epochs":
            EPOCHS,

        "batch_size":
            BATCH_SIZE,

        "learning_rate":
            LEARNING_RATE,

        "balance_ratio":
            BALANCE_RATIO,

        "gaussian_noise_std":
            GAUSSIAN_NOISE_STD,

        "xy_scale":
            [
                XY_SCALE_MIN,
                XY_SCALE_MAX,
            ],

        "early_stop_patience":
            EARLY_STOP_PATIENCE,

        "lr_patience":
            LR_PATIENCE,

        "class_names":
            CLASS_NAMES,
    }

    with open(
        CONFIG_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config,
            f,
            indent=2
        )


# ============================================================
# 13. Run experiments
# ============================================================

global_start = time.time()

run_number = len(completed_results)


for seq_len in SEQ_LENS:

    print("\n")
    print("=" * 80)
    print(
        f"SEQUENCE LENGTH: {seq_len}"
    )
    print("=" * 80)


    # --------------------------------------------------------
    # Extract training data ONCE
    # --------------------------------------------------------

    (
        X_train_base,
        y_train_base,
        centers_train,
        record_ids_train,
    ) = extract_sequences(
        train_record_ids,
        seq_len,
    )

    print(
        "Original training:",
        X_train_base.shape
    )


    # --------------------------------------------------------
    # Fixed validation
    # --------------------------------------------------------

    (
        X_val,
        y_val,
        _,
        _,
    ) = validation_cache[
        seq_len
    ]


    for architecture in ARCHITECTURES:

        for training_seed in TRAINING_SEEDS:


            current_key = run_key(
                architecture,
                seq_len,
                training_seed,
            )


            # ------------------------------------------------
            # SKIP COMPLETED RUN
            # ------------------------------------------------

            if current_key in completed_keys:

                print("\n")
                print(
                    f"SKIP: {current_key}"
                )

                continue


            run_number += 1

            print("\n")
            print("#" * 80)
            print(
                f"RUN {run_number}/{total_runs}"
            )
            print(
                f"Architecture: "
                f"{architecture.upper()}"
            )
            print(
                f"Sequence: "
                f"{seq_len}"
            )
            print(
                f"Training seed: "
                f"{training_seed}"
            )
            print(
                f"Split seed: "
                f"{SPLIT_SEED}"
            )
            print("#" * 80)


            # ------------------------------------------------
            # Reproducibility
            # ------------------------------------------------

            os.environ[
                "PYTHONHASHSEED"
            ] = str(
                training_seed
            )

            random.seed(
                training_seed
            )

            np.random.seed(
                training_seed
            )

            tf.keras.utils.set_random_seed(
                training_seed
            )

            try:

                tf.config.experimental.enable_op_determinism()

            except Exception:

                pass

            tf.keras.backend.clear_session()

            gc.collect()


            # ------------------------------------------------
            # Balance training data
            # ------------------------------------------------

            (
                X_train,
                y_train,
                _,
                _,
            ) = balance_sequences(
                X_train_base,
                y_train_base,
                centers_train,
                record_ids_train,
                training_seed,
            )

            print(
                "Balanced:",
                X_train.shape
            )


            # ------------------------------------------------
            # Augmentation
            # ------------------------------------------------

            (
                X_train,
                y_train
            ) = augment_training_data(
                X_train,
                y_train,
                training_seed,
            )

            print(
                "Augmented:",
                X_train.shape
            )


            # ------------------------------------------------
            # Model
            # ------------------------------------------------

            model = build_model(
                seq_len,
                architecture,
            )


            model_path = os.path.join(
                RESULT_DIR,
                (
                    f"model_"
                    f"{architecture}_"
                    f"seq{seq_len}_"
                    f"seed{training_seed}.keras"
                ),
            )


            history_path = os.path.join(
                RESULT_DIR,
                (
                    f"history_"
                    f"{architecture}_"
                    f"seq{seq_len}_"
                    f"seed{training_seed}.json"
                ),
            )


            callbacks = [

                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=EARLY_STOP_PATIENCE,
                    restore_best_weights=True,
                    verbose=1,
                ),

                tf.keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss",
                    factor=0.5,
                    patience=LR_PATIENCE,
                    min_lr=1e-6,
                    verbose=1,
                ),

                tf.keras.callbacks.ModelCheckpoint(
                    model_path,
                    monitor="val_loss",
                    save_best_only=True,
                    verbose=1,
                ),
            ]


            # ------------------------------------------------
            # Training
            # ------------------------------------------------

            start_time = time.time()

            history = model.fit(
                X_train,
                y_train,
                validation_data=(
                    X_val,
                    y_val,
                ),
                epochs=EPOCHS,
                batch_size=BATCH_SIZE,
                shuffle=True,
                callbacks=callbacks,
                verbose=1,
            )


            training_seconds = (
                time.time()
                - start_time
            )


            # ------------------------------------------------
            # Save training history
            # ------------------------------------------------

            with open(
                history_path,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    {
                        key: [
                            float(value)
                            for value in values
                        ]
                        for key, values
                        in history.history.items()
                    },
                    f,
                    indent=2,
                )


            # ------------------------------------------------
            # Evaluation
            # ------------------------------------------------

            result = evaluate_model(
                model,
                X_val,
                y_val,
                seq_len,
                architecture,
                training_seed,
            )


            result[
                "training_seconds"
            ] = float(
                training_seconds
            )

            result[
                "epochs_trained"
            ] = len(
                history.history[
                    "loss"
                ]
            )


            # ------------------------------------------------
            # SAVE RESULT IMMEDIATELY
            # ------------------------------------------------

            single_result_path = (
                result_path_for_run(
                    architecture,
                    seq_len,
                    training_seed,
                )
            )

            with open(
                single_result_path,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    result,
                    f,
                    indent=2,
                )


            # Mark as completed only AFTER
            # all important files have been written.

            completed_results.append(
                result
            )

            completed_keys.add(
                current_key
            )


            # ------------------------------------------------
            # Print result
            # ------------------------------------------------

            print("\nRESULT")

            print(
                "Accuracy:",
                f"{result['accuracy'] * 100:.3f}%"
            )

            print(
                "Macro-F1:",
                f"{result['macro_f1'] * 100:.3f}%"
            )

            print(
                "True-class probability:",
                (
                    f"{result['mean_true_class_probability'] * 100:.3f}%"
                )
            )

            print(
                "Mean probability delta:",
                (
                    f"{result['mean_abs_probability_delta_pp']:.4f} pp"
                )
            )

            print(
                "Epochs:",
                result[
                    "epochs_trained"
                ]
            )

            print(
                "Training time:",
                round(
                    training_seconds / 60,
                    2
                ),
                "min"
            )

            print(
                "Saved:",
                single_result_path
            )


            # ------------------------------------------------
            # Cleanup
            # ------------------------------------------------

            del model
            del X_train
            del y_train

            gc.collect()

            tf.keras.backend.clear_session()


# ============================================================
# 14. Rebuild ALL results from saved JSON files
# ============================================================

print("\n")
print("=" * 80)
print("REBUILDING RESULTS FROM SAVED RUN FILES")
print("=" * 80)


all_results = load_completed_results()

results_df = pd.DataFrame(
    all_results
)


# ------------------------------------------------------------
# Raw results
# ------------------------------------------------------------

raw_results_path = os.path.join(
    RESULT_DIR,
    "results_all_20_runs.csv"
)

results_df.to_csv(
    raw_results_path,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 15. Mean ± SD summary
# ============================================================

metric_columns = [

    "accuracy",

    "macro_f1",

    "weighted_f1",

    "mean_true_class_probability",

    "std_true_class_probability",

    "mean_abs_probability_delta_pp",

    "median_abs_probability_delta_pp",

    "p95_abs_probability_delta_pp",
]


group_columns = [
    "architecture",
    "seq_len",
]


summary = (
    results_df
    .groupby(
        group_columns
    )[metric_columns]
    .agg(
        [
            "mean",
            "std",
        ]
    )
)


summary_path = os.path.join(
    RESULT_DIR,
    "results_mean_sd.csv"
)

summary.to_csv(
    summary_path,
    encoding="utf-8-sig"
)


# ============================================================
# 16. Thesis-friendly summary table
# ============================================================

thesis_rows = []


for (
    architecture,
    seq_len,
), group in results_df.groupby(
    group_columns
):

    row = {

        "Architecture":
            (
                "Conv1D + LSTM"
                if architecture == "lstm"
                else "Conv1D + GAP"
            ),

        "Sequence length":
            seq_len,

        "Accuracy (%)":
            (
                group["accuracy"].mean()
                * 100
            ),

        "Accuracy SD (pp)":
            (
                group["accuracy"].std()
                * 100
            ),

        "Macro-F1 (%)":
            (
                group["macro_f1"].mean()
                * 100
            ),

        "Macro-F1 SD (pp)":
            (
                group["macro_f1"].std()
                * 100
            ),

        "True-class probability (%)":
            (
                group[
                    "mean_true_class_probability"
                ].mean()
                * 100
            ),

        "True-class probability SD (pp)":
            (
                group[
                    "mean_true_class_probability"
                ].std()
                * 100
            ),

        "Mean probability delta (pp)":
            group[
                "mean_abs_probability_delta_pp"
            ].mean(),

        "Probability delta SD (pp)":
            group[
                "mean_abs_probability_delta_pp"
            ].std(),

        "Runs":
            len(group),
    }

    thesis_rows.append(
        row
    )


thesis_summary = pd.DataFrame(
    thesis_rows
)


thesis_summary = (
    thesis_summary
    .sort_values(
        [
            "Sequence length",
            "Architecture",
        ]
    )
)


thesis_path = os.path.join(
    RESULT_DIR,
    "thesis_summary_mean_sd.csv"
)


thesis_summary.to_csv(
    thesis_path,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 17. Final status
# ============================================================

print("\n")
print("=" * 100)
print("FINAL THESIS EXPERIMENT STATUS")
print("=" * 100)

print(
    "Completed runs:",
    len(results_df),
    "/",
    total_runs
)

print()

display(
    thesis_summary
)

print("\nFiles:")
print(
    RESULT_DIR
)

print(
    "\nRaw results:"
)

print(
    raw_results_path
)

print(
    "\nMean ± SD:"
)

print(
    summary_path
)

print(
    "\nThesis summary:"
)

print(
    thesis_path
)

print(
    "\nAll individual run results are saved separately."
)

if len(results_df) == total_runs:

    print(
        "\n20 training runs completed successfully."
    )

else:

    print(
        "\nExperiment is incomplete."
    )

    print(
        "Re-run this cell to continue "
        "from the first missing run."
    )