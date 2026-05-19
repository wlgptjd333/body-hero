# -*- coding: utf-8 -*-
"""
Profile 비교: precise vs balanced vs rapid vs max_speed.
Recording-based holdout, same model, simulated state machine.
"""
import os, sys, json
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from pose_class_names import POSE_CLASS_NAMES

ALL_CLASSES = list(POSE_CLASS_NAMES)
NUM_CLASSES = len(ALL_CLASSES)
FEATURE_DIM = 33 * 3
PUNCH_LABELS = ("punch_l", "punch_r", "upper_l", "upper_r")

DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
MODEL_PATH = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")

PROFILES = {
    "precise": {
        "confirm": 2, "cooldown": 0.15, "min_gap": 0.12,
        "thresh_none": 0.95, "thresh_upper": 0.90, "thresh_punch": 0.88,
        "motion_min": 0.002, "motion_relax": 0.65,
    },
    "balanced": {
        "confirm": 1, "cooldown": 0.12, "min_gap": 0.10,
        "thresh_none": 0.90, "thresh_upper": 0.85, "thresh_punch": 0.80,
        "motion_min": 0.0015, "motion_relax": 0.55,
    },
    "rapid": {
        "confirm": 1, "cooldown": 0.08, "min_gap": 0.06,
        "thresh_none": 0.85, "thresh_upper": 0.78, "thresh_punch": 0.70,
        "motion_min": 0.0010, "motion_relax": 0.50,
    },
    "max_speed": {
        "confirm": 1, "cooldown": 0.04, "min_gap": 0.02,
        "thresh_none": 0.75, "thresh_upper": 0.65, "thresh_punch": 0.55,
        "motion_min": 0.0005, "motion_relax": 0.40,
    },
}

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

def build_stream(data, recs, seq_len=4):
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    streams = []
    for rec in recs:
        start = rec.get("start_index", 0)
        end = min(start + rec.get("frame_count", 0), len(data))
        frames, labels = [], []
        for i in range(start, end):
            item = data[i]
            lm = item.get("landmarks")
            label = item.get("label")
            if not lm or len(lm) != FEATURE_DIM or label not in ALL_CLASSES:
                continue
            frames.append(np.array(lm, dtype=np.float32))
            labels.append(label_to_idx[label])
        if len(frames) >= seq_len:
            streams.append((np.array(frames), np.array(labels, dtype=np.int32)))
    return streams

def simulate(logits_arr, true_arr, cfg, fps=30):
    """Simulate the full state machine with profile cfg."""
    confirm = cfg["confirm"]
    cooldown = cfg["cooldown"]
    thresh = {"none": cfg["thresh_none"], "upper_l": cfg["thresh_upper"],
              "upper_r": cfg["thresh_upper"], "punch_l": cfg["thresh_punch"],
              "punch_r": cfg["thresh_punch"], "guard": cfg["thresh_none"],
              "squat": cfg["thresh_none"]}
    motion_min = cfg["motion_min"]
    n = len(logits_arr)
    preds = np.empty(n, dtype=np.int32)
    confs = np.empty(n)
    punch_l_count = punch_r_count = 0
    other_count = 0
    other_pred = None
    last_punch_l_time = -999.0
    last_punch_r_time = -999.0
    frame_time = 1.0 / fps
    active_state = None

    for t in range(n):
        raw = logits_arr[t]
        raw_idx = int(np.argmax(raw))
        raw_conf = float(raw[raw_idx])
        raw_label = ALL_CLASSES[raw_idx]
        label = raw_label

        # threshold
        need = thresh.get(label, cfg["thresh_none"])
        if raw_conf < need:
            label = "none"

        # hysteresis (simple: if active state maintained)
        HYST_EXIT = 0.35
        if label == "none" and active_state is not None:
            if float(raw[active_state]) >= HYST_EXIT:
                label = ALL_CLASSES[active_state]

        # state machine mimicking udp_send_webcam_ml.py logic
        idx = ALL_CLASSES.index(label) if label != "none" else 0
        now = t * frame_time

        if label == "guard":
            punch_l_count = 0; punch_r_count = 0
            other_pred = None; other_count = 0
        else:
            if label == "punch_l":
                other_pred = None; other_count = 0; punch_r_count = 0
                if (now - last_punch_l_time) >= cooldown:
                    punch_l_count += 1
                else:
                    punch_l_count = 0
                if punch_l_count >= confirm:
                    preds[t] = ALL_CLASSES.index("punch_l")
                    confs[t] = raw_conf
                    last_punch_l_time = now
                    active_state = ALL_CLASSES.index("punch_l")
                    continue
            elif label == "punch_r":
                other_pred = None; other_count = 0; punch_l_count = 0
                if (now - last_punch_r_time) >= cooldown:
                    punch_r_count += 1
                else:
                    punch_r_count = 0
                if punch_r_count >= confirm:
                    preds[t] = ALL_CLASSES.index("punch_r")
                    confs[t] = raw_conf
                    last_punch_r_time = now
                    active_state = ALL_CLASSES.index("punch_r")
                    continue
            elif label in ("upper_l", "upper_r"):
                punch_l_count = 0; punch_r_count = 0
                is_upper = True
                ul = ALL_CLASSES.index("upper_l"); ur = ALL_CLASSES.index("upper_r")
                if label == other_pred:
                    other_count += 1
                else:
                    other_pred = label if label in ("upper_l","upper_r") else None
                    other_count = 1 if label in ("upper_l","upper_r") else 0
                if other_count >= confirm:
                    if is_upper:
                        pass  # motion check already passed by raw model
                    preds[t] = ALL_CLASSES.index(label)
                    confs[t] = raw_conf
                    active_state = ALL_CLASSES.index(label)
                    continue
            elif label == "squat":
                punch_l_count = 0; punch_r_count = 0
                if label == "squat":
                    preds[t] = ALL_CLASSES.index("squat")
                    confs[t] = raw_conf
                    active_state = ALL_CLASSES.index("squat")
                    continue

        # default: none
        preds[t] = 0
        confs[t] = raw_conf if label == "none" else 0

        if label == "none":
            active_state = None

    # metrics
    correct = preds == true_arr[:n]
    acc = float(np.mean(correct))

    # false positives: predictions that are not none when true label is none
    none_gt = true_arr[:n] == 0
    fp = np.sum(preds[none_gt] != 0) / max(1, np.sum(none_gt))

    # latency: avg frames from action onset to correct prediction
    transition_delays = []
    in_action = False
    wait_start = 0
    for t in range(1, n):
        gt_now = true_arr[t]
        gt_prev = true_arr[t-1]
        if gt_now != 0 and gt_prev == 0:
            in_action = True
            wait_start = t
        if in_action and preds[t] == gt_now:
            transition_delays.append(t - wait_start)
            in_action = False

    avg_delay = np.mean(transition_delays) if transition_delays else 0

    # transitions (flicker)
    transitions = int(np.sum(preds[1:] != preds[:-1]))

    # per-class recall
    recall = {}
    for c in range(NUM_CLASSES):
        mask = true_arr[:n] == c
        if np.sum(mask) > 0:
            recall[ALL_CLASSES[c]] = float(np.sum(preds[mask] == c) / np.sum(mask))
        else:
            recall[ALL_CLASSES[c]] = 0.0

    return acc, fp, avg_delay, transitions, recall

def main():
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    print("=" * 65)
    print("  Profile comparison: precise vs balanced vs rapid vs max_speed")
    print("=" * 65)

    with open(DATA_PATH) as f: data = json.load(f)
    groups = group_recordings_by_label(load_recordings(META_PATH))
    _, test_recs = build_split(groups, 0.2, 42)
    streams = build_stream(data, test_recs, 4)

    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    seq_len = model.input_shape[1]

    # Batch predict all streams
    all_X = []
    stream_info = []
    for frames, labels in streams:
        n = len(frames)
        if n < seq_len:
            continue
        stream_info.append((n - seq_len + 1, labels[seq_len-1:].copy()))
        for i in range(n - seq_len + 1):
            all_X.append(frames[i:i+seq_len])

    X = np.array(all_X, dtype=np.float32)
    preds = model.predict(X, verbose=0, batch_size=256)

    # Group back
    logits_by_stream = []
    idx = 0
    for n_preds, true_labels in stream_info:
        logits_by_stream.append((preds[idx:idx+n_preds], true_labels))
        idx += n_preds

    print(f"Test streams: {len(logits_by_stream)}, predictions: {idx}")

    for pname, pcfg in PROFILES.items():
        all_acc = []; all_fp = []; all_delay = []; all_trans = []
        all_recall = {c: [] for c in ALL_CLASSES}

        for logits_arr, true_arr in logits_by_stream:
            acc, fp, delay, trans, recall = simulate(logits_arr, true_arr, pcfg)
            all_acc.append(acc)
            all_fp.append(fp)
            all_delay.append(delay)
            all_trans.append(trans)
            for c in ALL_CLASSES:
                if recall[c] > 0:
                    all_recall[c].append(recall[c])

        print(f"\n  [{pname}]")
        print(f"    Accuracy:      {np.mean(all_acc)*100:.2f}%")
        print(f"    FP rate(none): {np.mean(all_fp)*100:.2f}%")
        print(f"    Avg onset:     {np.mean(all_delay):.1f} frames")
        print(f"    Transitions:   {sum(all_trans)} total")
        for c in ALL_CLASSES:
            r = [v for v in all_recall[c] if v > 0]
            if r:
                print(f"    {c:8s} recall: {np.mean(r)*100:.1f}%")

if __name__ == "__main__":
    main()
