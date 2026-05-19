# -*- coding: utf-8 -*-
"""
Streaming simulation: EMA logit smoothing + hysteresis + delta features.

Simulates frame-by-frame inference on recording-based holdout data.
Measures: accuracy, flicker rate (false transitions), per-class stability.
"""
import os, sys, json, time
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from pose_class_names import POSE_CLASS_NAMES

ALL_CLASSES = list(POSE_CLASS_NAMES)
NUM_CLASSES = len(ALL_CLASSES)
FEATURE_DIM = 33 * 3

DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
MODEL_PATH = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")

# ── Data ──

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
    """frame-by-frame 스트림 시뮬레이션용. 각 프레임마다 seq_len 버퍼 반환."""
    import tensorflow as tf
    label_to_idx = {c: i for i, c in enumerate(ALL_CLASSES)}
    streams = []
    for rec in recs:
        start = rec.get("start_index", 0)
        count = rec.get("frame_count", 0)
        end = min(start + count, len(data))
        frames = []
        labels = []
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

# ── Inference Simulator ──

class StreamSimulator:
    """Pre-loads model, runs frame-by-frame simulation with various post-processing."""
    
    def __init__(self, model):
        self.model = model
        self.seq_len = model.input_shape[1]
        
    def predict(self, seq):
        X = np.array(seq, dtype=np.float32).reshape(1, self.seq_len, FEATURE_DIM)
        return self.model.predict(X, verbose=0)[0]
    
    def predict_all(self, frames_list):
        """Batch predict all sequences at once. Returns list of (logits, true_labels)."""
        all_X = []
        for frames, _ in frames_list:
            n = len(frames)
            if n < self.seq_len:
                continue
            for i in range(n - self.seq_len + 1):
                seq = frames[i:i + self.seq_len]
                all_X.append(seq)
        if not all_X:
            return [], []
        X = np.array(all_X, dtype=np.float32)
        preds = self.model.predict(X, verbose=0, batch_size=256)
        logits_by_stream = []
        idx = 0
        for frames, labels in frames_list:
            n = len(frames)
            if n < self.seq_len:
                continue
            n_preds = n - self.seq_len + 1
            logits_by_stream.append((preds[idx:idx+n_preds], labels[self.seq_len-1:].copy()))
            idx += n_preds
        return logits_by_stream

    def simulate(self, logits_stream, true_labels_stream, ema_alpha=None, hysteresis=None):
        """Apply EMA and hysteresis to pre-computed logits."""
        all_results = []
        
        for logits_arr, true_arr in zip(logits_stream, true_labels_stream):
            n = len(logits_arr)
            if n < 1:
                continue
            true_labels = true_arr
            
            # Raw
            raw_labels = np.argmax(logits_arr, axis=1)
            
            # EMA
            if ema_alpha is not None:
                ema = logits_arr[0].copy()
                ema_labels = np.empty(n, dtype=np.int32)
                ema_logits_list = np.empty_like(logits_arr)
                for t in range(n):
                    ema = ema_alpha * logits_arr[t] + (1 - ema_alpha) * ema
                    ema_labels[t] = int(np.argmax(ema))
                    ema_logits_list[t] = ema
            else:
                ema_labels = raw_labels
                ema_logits_list = logits_arr
            
            # Hysteresis
            if hysteresis is not None:
                enter_th, exit_th = hysteresis
                hyst_labels = np.empty(n, dtype=np.int32)
                state = 0
                for t in range(n):
                    ema_label = int(ema_labels[t])
                    ema_logit = ema_logits_list[t]
                    ema_conf = float(ema_logit[ema_label])
                    
                    if state == 0:
                        if ema_label != 0 and ema_conf >= enter_th:
                            state = ema_label
                    else:
                        if ema_label == 0:
                            state = 0
                        elif ema_label == state:
                            pass
                        else:
                            current_conf = float(ema_logit[state])
                            if ema_conf > current_conf and ema_conf >= enter_th:
                                state = ema_label
                            elif ema_conf < exit_th:
                                state = 0
                    hyst_labels[t] = state
            else:
                hyst_labels = ema_labels
            
            # Per-stream metrics
            def metric(pred):
                correct = pred == true_labels
                acc = float(np.mean(correct))
                trans = int(np.sum(pred[1:] != pred[:-1]))
                recall = {}
                for c in range(NUM_CLASSES):
                    mask = true_labels == c
                    if np.sum(mask) > 0:
                        recall[ALL_CLASSES[c]] = float(np.sum(pred[mask] == c) / np.sum(mask))
                    else:
                        recall[ALL_CLASSES[c]] = 0.0
                return acc, trans, recall
            
            raw_acc, raw_trans, raw_recall = metric(raw_labels)
            ema_acc, ema_trans, ema_recall = metric(ema_labels)
            hyst_acc, hyst_trans, hyst_recall = metric(hyst_labels)
            
            all_results.append({
                "raw": (raw_acc, raw_trans, raw_recall),
                "ema": (ema_acc, ema_trans, ema_recall),
                "hysteresis": (hyst_acc, hyst_trans, hyst_recall),
            })
        
        return all_results

# ── Main ──

def main():
    import tensorflow as tf
    from collections import Counter

    tf.get_logger().setLevel("ERROR")
    print("=" * 70)
    print("  Streaming Simulation: EMA + Hysteresis")
    print("=" * 70)

    with open(DATA_PATH) as f: data = json.load(f)
    groups = group_recordings_by_label(load_recordings(META_PATH))
    train_recs, test_recs = build_split(groups, 0.2, 42)
    
    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    sim = StreamSimulator(model)
    seq_len = sim.seq_len
    print(f"Model: {MODEL_PATH}, seq_len={seq_len}")
    
    streams = build_stream(data, test_recs, seq_len)
    n_streams = len(streams)
    total_frames = sum(s[0].shape[0] for s in streams)
    print(f"Test streams: {n_streams}, total frames: {total_frames}")
    
    # Batch predict once
    print("\nBatch predicting all sequences...", flush=True)
    logits_stream = sim.predict_all(streams)
    print(f"Done. {sum(len(l[0]) for l in logits_stream)} predictions total.\n", flush=True)
    
    # Extract logits and labels
    logits_list = [l[0] for l in logits_stream]
    labels_list = [l[1] for l in logits_stream]
    
    configs = [
        ("Raw (no smoothing)", {"ema_alpha": None, "hysteresis": None}),
        ("EMA α=0.5", {"ema_alpha": 0.5, "hysteresis": None}),
        ("EMA α=0.7", {"ema_alpha": 0.7, "hysteresis": None}),
        ("EMA α=0.5 + Hyst(0.8/0.4)", {"ema_alpha": 0.5, "hysteresis": (0.8, 0.4)}),
        ("EMA α=0.5 + Hyst(0.7/0.3)", {"ema_alpha": 0.5, "hysteresis": (0.7, 0.3)}),
        ("EMA α=0.7 + Hyst(0.8/0.4)", {"ema_alpha": 0.7, "hysteresis": (0.8, 0.4)}),
        ("EMA α=0.7 + Hyst(0.9/0.5)", {"ema_alpha": 0.7, "hysteresis": (0.9, 0.5)}),
    ]
    
    for name, cfg in configs:
        results = sim.simulate(logits_list, labels_list, **cfg)
        if not results:
            continue
        
        key = "raw" if cfg["ema_alpha"] is None else "ema" if cfg["hysteresis"] is None else "hysteresis"
        accs = [r[key][0] for r in results]
        trans = [r[key][1] for r in results]
        recalls = {c: [r[key][2][c] for r in results if r[key][2][c] > 0] for c in ALL_CLASSES}
        
        mean_acc = np.mean(accs)
        total_trans = sum(trans)
        
        print(f"\n  [{name}]")
        print(f"    Accuracy:      {mean_acc*100:.2f}%")
        print(f"    Transitions:   {total_trans} total ({total_trans/max(1,n_streams):.1f}/stream)")
        for c in ALL_CLASSES:
            r_vals = [v for v in recalls[c] if v > 0]
            if r_vals:
                print(f"    {c:8s} recall: {np.mean(r_vals)*100:.1f}%")

if __name__ == "__main__":
    main()
