"""
ì›¹ìº  â†’ Pose ëžœë“œë§ˆí¬ â†’ ML ì¶”ë¡ (ë¡œì»¬ ë˜ëŠ” pose_server) â†’ Godotì— UDPë¡œ ì•¡ì…˜ ì „ì†¡.

- ê¸°ë³¸: pose_classifier_seq_len4.keras(4í”„ë ˆìž„ ìš°ì„ , ADR-0002) â†’ seq.keras(8í”„ë ˆìž„ í´ë°±) + pose_classifier.keras(ê°€ë“œ í´ë°±). pose_server ë¶ˆí•„ìš”.
- ì‹œí€€ìŠ¤ ëª¨ë¸ì´ ì—†ìœ¼ë©´ HTTPë¡œ pose_serverì— ìš”ì²­. ì„œë²„ê°€ ì—†ìœ¼ë©´ pose_server.pyë¥¼ ìžë™ìœ¼ë¡œ ë„ì›€ (--no-auto-server ë¡œ ëŒ ìˆ˜ ìžˆìŒ).

ì‚¬ìš© ìˆœì„œ:
  1) ë°ì´í„° ìˆ˜ì§‘: python collect_pose_data.py
  2) ì‹œí€€ìŠ¤ í•™ìŠµ: python train_pose_classifier_seq.py  [ê°€ë“œ í´ë°±: train_pose_classifier.py]
  3) ë³¸ ìŠ¤í¬ë¦½íŠ¸: python udp_send_webcam_ml.py
  4) Godot ì‹¤í–‰ í›„ í”Œë ˆì´

íŽ€ì¹˜(punch_l/r) ë¼ë²¨ì´ ì „í˜€ ì•ˆ ëœ° ë•Œ: --debug-topk 5 ë¡œ ì‹œí€€ìŠ¤ softmax ìˆœìœ„ í™•ì¸.
  ìƒìœ„ê°€ noneì´ë©´ ë°ì´í„°Â·ìž¬í•™ìŠµ ìª½, punchê°€ ìžˆëŠ”ë° í™•ë¥ ë§Œ ë‚®ìœ¼ë©´ --punch-confidence 0.5~0.65.
  ê°€ë“œë§Œ ëœ¨ë©´ --skip-guard-single ìœ¼ë¡œ ë‹¨ì¼ ê°€ë“œ ëª¨ë¸ ë‹¨ì¶•ì„ ë„ê³  ë¹„êµ.
  ì–´í¼ ìœˆë“œì—…ì—ì„œ ì§ì„ ì´ ë¨¼ì € ë‚˜ê°€ë©´: `--upper-windup-punch-suppress`. ì§ì„  ìž½ì€ ì–´í¼ë³´ë‹¤ í™•ì • í”„ë ˆìž„ ì§§ê²ŒÂ·softmaxëŠ” ì–´í¼ì™€ ë™ì¼ í•˜í•œ ê¶Œìž¥.
  í•œ ë²ˆì˜ íŽ€ì¹˜Â·ì–´í¼ì— UDPê°€ ì—¬ëŸ¬ ë²ˆ ë‚˜ê°€ë©´: `--attack-rearm-frames`(ê¸°ë³¸ 3). 0ì´ë©´ ë”.
  Godot UDP ì•¡ì…˜: punch_l, punch_r, upper_l, upper_r, guard, squat â€¦
"""
import math
import os
import time
import socket
import urllib.request
import json
import threading
import argparse
import subprocess
import sys
from collections import deque
from typing import Any, List, Optional, Tuple

# ë¡œê·¸: MediaPipeÂ·TensorFlowê°€ ê°ê° C++ ìª½ absl/oneDNNì„ ì¼œì„œ ë¹„ìŠ·í•œ ì˜ì–´ ë¬¸êµ¬ê°€ 2ë²ˆ ë‚˜ì˜¬ ìˆ˜ ìžˆìŒ(ì •ìƒ).
# TF ìª½ INFO/WARN ì¤„ì´ê¸°(3=ERRORë§Œ). oneDNNì€ ê¸°ë³¸ ì„±ëŠ¥ì„ ìœ ì§€í•˜ê³ , í•„ìš”í•  ë•Œë§Œ í™˜ê²½ë³€ìˆ˜ë¡œ ëˆë‹¤.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
if os.environ.get("BODY_HERO_DISABLE_ONEDNN", "").strip().lower() in ("1", "true", "yes", "on"):
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 4242
PREDICT_URL = "http://127.0.0.1:5000/predict"
POSE_SERVER_HEALTH_URL = "http://127.0.0.1:5000/health"
POSE_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "pose_server.py")

from pose_normalize import normalize_landmarks_flat, shoulder_center_and_width
from pose_class_names import GUARD_INDEX, POSE_CLASS_NAMES
from cv_capture import open_cv_video_capture

# ë¡œì»¬ ì¶”ë¡ ìš© (pose_serverì™€ ë™ì¼). ì‹œí€€ìŠ¤ ê¸¸ì´ëŠ” ë¡œë“œí•œ ëª¨ë¸ ìž…ë ¥(time)ì—ì„œ ìžë™ ì„¤ì •.
# ìš°ì„ ìˆœìœ„: seq_len=4 â†’ 8 (ADR-0002).
_MODEL_SEQ_4 = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")
_MODEL_SEQ_8 = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
if os.path.exists(_MODEL_SEQ_4):
    MODEL_SEQ_PATH = _MODEL_SEQ_4
    SEQ_LEN = 4
elif os.path.exists(_MODEL_SEQ_8):
    MODEL_SEQ_PATH = _MODEL_SEQ_8
    SEQ_LEN = 8
else:
    MODEL_SEQ_PATH = _MODEL_SEQ_4  # ì—†ìœ¼ë©´ ê¸°ë³¸ ê²½ë¡œ ìœ ì§€(í•™ìŠµ ì „)
    SEQ_LEN = 4
MODEL_SINGLE_PATH = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
CLASS_NAMES = list(POSE_CLASS_NAMES)
# MLÂ·UDP ë¼ë²¨ = POSE_CLASS_NAMES (punch_l/r â€¦)
# ì‹œí€€ìŠ¤ ëª¨ë¸: 1ë“± í´ëž˜ìŠ¤ í™•ë¥ ì´ ì´ ê°’ ë¯¸ë§Œì´ë©´ none. (ê¸°ë³¸ì€ balancedì— ë§žì¶¤; --profile ë¡œ ë®ì–´ì”€)
CONFIDENCE_THRESHOLD = 0.93
UPPER_CONFIDENCE_THRESHOLD = 0.88
# ì§ì„  íŽ€ì¹˜ softmax í•˜í•œ. ê¸°ë³¸ì€ ì–´í¼ì™€ ë™ì¼(0.88) â€” ë„ˆë¬´ ë†’ìœ¼ë©´ ìž½ì´ ìž˜ ì•ˆ ë‚˜ê°. --punch-confidence ë¡œ ë®ì–´ì”€.
PUNCH_CONFIDENCE_THRESHOLD = 0.88
GUARD_FALLBACK_THRESHOLD = 0.65
COOLDOWN_SEC = 0.08  # ê°™ì€ ì† ì—°ì† ë°©ì§€ (per-side, 0.08së©´ ì•½ 2~3í”„ë ˆìž„)
MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.04  # ìµœì†Œ ê°„ê²©ë§Œ (êµì°¨íŽ€ì¹˜ Lâ†’Râ†’L ìš©, ê±°ì˜ ì°¨ë‹¨ ì—†ìŒ)
GUARD_EXIT_FRAMES = 2  # ê°€ë“œ í•´ì œ ê°ì§€: 2í”„ë ˆìž„(ì•½ 66ms) ì—°ì† not guardë©´ guard_end ì „ì†¡
FPS_TARGET = 30
# ì²˜ë¦¬ í•´ìƒë„: ë†’ì„ìˆ˜ë¡ ì¢Œìš°(íŽ€ì¹˜) êµ¬ë¶„Â·í¬ì¦ˆ ì•ˆì •ì— ìœ ë¦¬, CPU ë¶€í•˜ ì¦ê°€ (ë ‰ ì‹œ 320x240 ë˜ëŠ” --process-w/hë¡œ ë‚®ì¶¤)
PROCESS_W, PROCESS_H = 480, 360
# ì´ í”„ë ˆìž„ ìˆ˜ë§ˆë‹¤ë§Œ í¬ì¦ˆ+ML ì‹¤í–‰ (1=ë§¤í”„ë ˆìž„, 2=2í”„ë ˆìž„ë§ˆë‹¤). test_pose_liveì²˜ëŸ¼ ì¸ì‹í•˜ë ¤ë©´ 1
PROCESS_EVERY_N_FRAMES = 1
# Godotìœ¼ë¡œ ì•¡ì…˜ ì „ì†¡ ì‹œì—ë§Œ ì ìš©: ì–´ê¹¨ ì¤‘ì‹¬ Xì¢Œí‘œë§Œ ê²€ì‚¬ (YëŠ” í•­ìƒ ì „ì²´)
CENTER_ZONE_X = (0.3, 0.7)  # normalized [0,1] ê¸°ì¤€
CENTER_ZONE_Y = (0.0, 1.0)  # ì„¸ë¡œ ì „ì²´
PUNCH_CONFIRM_FRAMES = 2
OTHER_PUNCH_CONFIRM_FRAMES = 1
UPPER_PUNCH_CONFIRM_FRAMES = 2
UPPER_MOTION_MEAN_ABS_MIN = 0.0015
UPPER_L_MOTION_RELAX = 0.6
PUNCH_HOLDOFF_AFTER_UPPER_FRAMES = 4
UPPER_LR_OPPOSITE_BLOCK_FRAMES = 6
NONE_STREAK_TO_CLEAR_PUNCH_HOLDOFF = 3
SQUAT_CONFIRM_FRAMES = 2
# íŽ€ì¹˜Â·ì–´í¼ 1íšŒ ì „ì†¡ í›„, MLì´ ê³µê²© ë¼ë²¨ì´ ì•„ë‹Œ í”„ë ˆìž„ì´ ì´ ê°’ ì—°ì†ì¼ ë•Œë§Œ ë‹¤ìŒ ê³µê²© ì „ì†¡(ê¸°ë³¸ì€ argparseë¡œ ë®ì–´ì”€).
ACTION_REARM_OFF_ATTACK_FRAMES_DEFAULT = 0
POWER_PUNCH_LABELS = ("upper_l", "upper_r")
PUNCH_LABELS = ("punch_l", "punch_r", "upper_l", "upper_r")
# ì •ê·œí™” ì¢Œí‘œ: yëŠ” ì•„ëž˜ë¡œ ê°ˆìˆ˜ë¡ ì¦ê°€. ì†ëª©ì´ ê°™ì€ìª½ ì–´ê¹¨ë³´ë‹¤ ì´ ê°’ë§Œí¼ ë” ì•„ëž˜ë©´ "ë‚®ì€ ì¤€ë¹„"ë¡œ ê°„ì£¼.
UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT = 0.08

# main()ì—ì„œ argparseë¡œ ë®ì–´ì”€ (ì¶”ë¡  ìŠ¤ë ˆë“œê°€ ì½ìŒ)
_debug_seq_topk: int = 0
_skip_guard_single: bool = False
_punch_confidence_override: Optional[float] = None

# ì†ë„/ì •í™•ë„ í”„ë¦¬ì…‹ (ëŸ°íƒ€ìž„ì—ì„œ ìƒìˆ˜ë“¤ì„ ë®ì–´ì”€)
SPEED_PROFILES = ("precise", "balanced", "classic", "rapid", "max_speed")

class RemappedLandmark:
    __slots__ = ("x", "y", "z", "visibility")

    def __init__(self, x: float, y: float, z: float, visibility: float = 1.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility

try:
    import cv2
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core import image as mp_core_image
except ImportError:
    print("pip install mediapipe opencv-python")
    raise SystemExit(1)

if not hasattr(cv2, "VideoCapture"):
    print(
        "OpenCV(cv2)ì— VideoCaptureê°€ ì—†ìŠµë‹ˆë‹¤. headless ì œê±° í›„ íŒ¨í‚¤ì§€ê°€ ê¼¬ì˜€ê±°ë‚˜ ìž˜ëª»ëœ cv2ê°€ ë¡œë“œëœ ê²½ìš°ìž…ë‹ˆë‹¤.\n"
        f"  cv2 ë¡œë“œ ê²½ë¡œ: {getattr(cv2, '__file__', '?')}\n"
        "  (venv_ml)ì—ì„œ ì•„ëž˜ë¥¼ ì‹¤í–‰í•œ ë’¤ ë‹¤ì‹œ ì‹œë„í•˜ì„¸ìš”:\n"
        "    pip uninstall opencv-python opencv-python-headless opencv-contrib-python -y\n"
        "    pip install --force-reinstall \"opencv-python>=4.9,<5\""
    )
    raise SystemExit(1)


# ë¡œì»¬ ì¶”ë¡ : numpyëŠ” ì¦‰ì‹œ, TensorFlowëŠ” _load_local_models()ì—ì„œë§Œ ë¡œë“œ(ì‹œìž‘Â·ìŠ¤ë ˆë“œ ë¶„ë¦¬ë¡œ ì²´ê° ì§€ì—° ì™„í™”)
_np = None
_tf = None
_model_seq = None
_model_single = None
_use_local_inference = False

# EMA logit smoothing state (Î±=0.7)
_ema_logits = None
# Hysteresis state (active action index, held until confidence drops below 0.35)
_active_state = None

try:
    import numpy as _np
except ImportError:
    _np = None


def _prepare_tf_import_env() -> None:
    """CUDA/GPU í”„ë¡œë¸Œê°€ ì˜¤ëž˜ ê±¸ë¦¬ëŠ” PCì—ì„œ TF ì²« ìž„í¬íŠ¸ ì‹œê°„ì„ ì¤„ì´ê¸° ìœ„í•´ CPUë§Œ ì”€(í™˜ê²½ ë³€ìˆ˜ë¡œ ëŒ ìˆ˜ ìžˆìŒ)."""
    v = os.environ.get("BODY_HERO_TF_CPU_ONLY", "1")
    if str(v).strip().lower() not in ("0", "false", "no", "off"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"


def _keras_load_model_safe(path: str):
    """compile=Falseë¡œ ê·¸ëž˜í”„/ë©”íŠ¸ë¦­ ì»´íŒŒì¼ ìƒëžµ â†’ ë¡œë“œ ì‹œê°„ ë‹¨ì¶•. êµ¬í˜• TFëŠ” ì¸ìž ì—†ì´ ìž¬ì‹œë„."""
    if _tf is None:
        return None
    try:
        return _tf.keras.models.load_model(path, compile=False)
    except TypeError:
        return _tf.keras.models.load_model(path)


def _load_local_models():
    """ë™ê¸°: ì‹œí€€ìŠ¤+ê°€ë“œ ëª¨ë¸ ì „ë¶€ ë¡œë“œ. (í…ŒìŠ¤íŠ¸Â·ìŠ¤í¬ë¦½íŠ¸ í˜¸í™˜ìš©; ëŸ°íƒ€ìž„ì€ _tf_load_worker_phased ì‚¬ìš©)"""
    global _model_seq, _model_single, _use_local_inference, SEQ_LEN, _tf
    if _np is None:
        return False
    if not os.path.isfile(MODEL_SEQ_PATH):
        return False
    _prepare_tf_import_env()
    try:
        import tensorflow as tf

        _tf = tf
    except ImportError:
        return False
    try:
        _model_seq = _keras_load_model_safe(MODEL_SEQ_PATH)
        inp = _model_seq.input_shape
        if isinstance(inp, (list, tuple)) and len(inp) >= 2 and inp[1] is not None:
            SEQ_LEN = int(inp[1])
        if os.path.isfile(MODEL_SINGLE_PATH):
            _model_single = _keras_load_model_safe(MODEL_SINGLE_PATH)
        _use_local_inference = True
        return True
    except Exception:
        _model_seq = None
        _model_single = None
        _use_local_inference = False
        return False


def _tf_load_worker_phased(seq_model_ready: threading.Event, load_errors: list) -> None:
    """ë°±ê·¸ë¼ìš´ë“œ: ì‹œí€€ìŠ¤ ëª¨ë¸ë§Œ ë¨¼ì € ëë‚´ê³  ì´ë²¤íŠ¸ë¡œ ì•Œë¦¼ â†’ ê°€ë“œìš© ë‹¨ì¼ ëª¨ë¸ì€ ê·¸ ë’¤ì— ë¡œë“œ(ê²Œìž„ ì‹œìž‘ ëŒ€ê¸° ì‹œê°„ ë‹¨ì¶•)."""
    global _tf, _model_seq, _model_single, _use_local_inference, SEQ_LEN
    try:
        if _np is None:
            load_errors.append(RuntimeError("numpyê°€ ì—†ìŠµë‹ˆë‹¤."))
            return
        if not os.path.isfile(MODEL_SEQ_PATH):
            return
        _prepare_tf_import_env()
        import tensorflow as tf

        _tf = tf
        _model_seq = _keras_load_model_safe(MODEL_SEQ_PATH)
        inp = _model_seq.input_shape
        if isinstance(inp, (list, tuple)) and len(inp) >= 2 and inp[1] is not None:
            SEQ_LEN = int(inp[1])
        _use_local_inference = True
    except Exception as e:
        _model_seq = None
        _model_single = None
        _use_local_inference = False
        load_errors.append(e)
    finally:
        seq_model_ready.set()

    if load_errors or not _use_local_inference or _tf is None:
        return
    if not os.path.isfile(MODEL_SINGLE_PATH):
        return
    try:
        print("ê°€ë“œ ë³´ì¡° ëª¨ë¸(Keras) ì¶”ê°€ ë¡œë“œ ì¤‘â€¦", flush=True)
        _model_single = _keras_load_model_safe(MODEL_SINGLE_PATH)
        print("ê°€ë“œ ë³´ì¡° ëª¨ë¸ ë¡œë“œ ì™„ë£Œ.", flush=True)
    except Exception as e:
        print("ê°€ë“œ ë³´ì¡° ëª¨ë¸ ë¡œë“œ ì‹¤íŒ¨(ì‹œí€€ìŠ¤ë§Œ ì‚¬ìš©):", e, flush=True)


def _predict_local(
    sequence: list,
    seq_topk: int = 0,
) -> Tuple[Optional[str], float, Optional[List[Tuple[str, float]]]]:
    """ê°€ë“œ ë‹¨ì¼(ì„ íƒ) â†’ ì‹œí€€ìŠ¤ softmax. (í‘œì‹œ ë¼ë²¨, í™•ì‹ ë„, seq_topk>0ì¼ ë•Œ ìƒìœ„k (ì´ë¦„,í™•ë¥ )).

    seq_topk>0ì´ë©´ ê°€ë“œë¡œ ë‹¨ì¶•ë˜ê¸° ì „ì—ë„ ì‹œí€€ìŠ¤ë¥¼ í•œ ë²ˆ ëŒë ¤ ìƒìœ„ í™•ë¥ ì„ ëŒë ¤ì¤€ë‹¤(ì›ì¸ ì¡°ì‚¬ìš©).

    EMA smoothing: raw softmaxë¥¼ EMA(Î±=0.7)ë¡œ smoothingí•œ í›„ threshold ì ìš©.
    Hysteresis: í˜„ìž¬ active stateì˜ exit thresholdê°€ enterë³´ë‹¤ ë‚®ì•„ flicker ë°©ì§€.
    """
    none3: Tuple[Optional[str], float, Optional[List[Tuple[str, float]]]] = (None, 0.0, None)
    if _model_seq is None or _np is None or not sequence or len(sequence) != SEQ_LEN:
        return none3
    sequence = list(sequence)
    last_frame = _np.array(sequence[-1], dtype=_np.float32).reshape(1, -1)

    X = _np.array(sequence, dtype=_np.float32).reshape(1, SEQ_LEN, -1)
    pred_vec = _model_seq.predict(X, verbose=0)[0]
    topk_list = None
    if seq_topk > 0:
        k = min(seq_topk, len(CLASS_NAMES))
        idxs = _np.argsort(pred_vec)[-k:][::-1]
        topk_list = [(CLASS_NAMES[int(i)], float(pred_vec[int(i)])) for i in idxs]

    # EMA logit smoothing for state maintenance (Î±=0.7)
    # raw â†’ argmax (instant onset), EMA â†’ hysteresis (smooth state)
    global _ema_logits, _active_state
    if _ema_logits is None:
        _ema_logits = pred_vec.copy()
    else:
        _ema_logits = 0.7 * pred_vec + 0.3 * _ema_logits

    # Raw logits for action label (no latency)
    raw_idx = int(_np.argmax(pred_vec))
    raw_conf = float(pred_vec[raw_idx])
    raw_label = CLASS_NAMES[raw_idx]

    # EMA-smoothed for stability check
    ema_conf = float(_ema_logits[_active_state]) if _active_state is not None else 0.0

    # Determine action label
    if raw_label in ("upper_l", "upper_r"):
        need = UPPER_CONFIDENCE_THRESHOLD
    elif raw_label in ("punch_l", "punch_r"):
        need = (
            _punch_confidence_override
            if _punch_confidence_override is not None
            else PUNCH_CONFIDENCE_THRESHOLD
        )
    else:
        need = CONFIDENCE_THRESHOLD

    if raw_conf < need:
        raw_label = "none"

    # Hysteresis: maintain active state via EMA confidence
    HYST_EXIT = 0.60
    if raw_label == "none":
        if _active_state is not None and ema_conf >= HYST_EXIT:
            label = CLASS_NAMES[_active_state]
            conf = ema_conf
        else:
            label = "none"
            conf = raw_conf
            _active_state = None
    else:
        label = raw_label
        conf = raw_conf
        if _active_state is None:
            _active_state = raw_idx
        elif _active_state != raw_idx:
            current_ema_conf = float(_ema_logits[_active_state])
            new_raw_conf = float(pred_vec[raw_idx])
            if new_raw_conf > current_ema_conf + 0.05:
                _active_state = raw_idx

    return label, conf, topk_list

MODEL_PATH_LITE = os.path.join(SCRIPT_DIR, "pose_landmarker.task")
MODEL_PATH_FULL = os.path.join(SCRIPT_DIR, "pose_landmarker_full.task")
MODEL_URL_LITE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker/lite/1/pose_landmarker_lite.task"
MODEL_URL_LITE_FALLBACK = "https://huggingface.co/AndorML/Public/resolve/02ef083b988890f7444aa40afad3a2029d3b9faa/pose_landmarker_lite.task"
MODEL_URL_FULL = "https://storage.googleapis.com/mediapipe-tasks/pose_landmarker/pose_landmarker_full.task"
POSE_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19), (16, 18), (16, 20), (16, 22), (18, 20),
    (23, 24), (11, 23), (12, 24), (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30), (29, 31), (30, 32),
)


def _download_pose_model(model_path, model_url, fallback_url=None):
    if os.path.isfile(model_path):
        return
    import urllib.request
    urls = [model_url]
    if fallback_url:
        urls.append(fallback_url)
    for url in urls:
        try:
            urllib.request.urlretrieve(url, model_path)
            return
        except Exception:
            pass


def predict_action(sequence):
    """ë¡œì»¬ ëª¨ë¸ì´ ìžˆìœ¼ë©´ ë¡œì»¬ ì¶”ë¡ , ì—†ìœ¼ë©´ HTTPë¡œ pose_server ìš”ì²­. (ì•¡ì…˜, í™•ì‹ ë„) ë°˜í™˜. ìŠ¤ë ˆë“œì—ì„œë§Œ í˜¸ì¶œ."""
    if not sequence or len(sequence) != SEQ_LEN:
        return None, 0.0
    if _use_local_inference:
        a, b, _ = _predict_local(sequence, seq_topk=0)
        return a, b
    try:
        req = urllib.request.Request(
            PREDICT_URL,
            data=json.dumps({"sequence": sequence}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result"), float(data.get("confidence", 0.0))
    except Exception:
        return None, 0.0


# ML ì˜ˆì¸¡ ê²°ê³¼ (ë°±ê·¸ë¼ìš´ë“œ ìŠ¤ë ˆë“œì—ì„œ ê°±ì‹ , ë©”ì¸ ë£¨í”„ëŠ” ì½ê¸°ë§Œ)
_pred_lock = threading.Lock()
_last_pred = None
_last_confidence = 0.0
_last_seq_topk: Optional[List[Tuple[str, float]]] = None
_predict_busy = False


def _predict_worker(sequence):
    global _last_pred, _last_confidence, _last_seq_topk, _predict_busy
    if _use_local_inference:
        res, conf, topk = _predict_local(sequence, seq_topk=_debug_seq_topk)
    else:
        res, conf = predict_action(sequence)
        topk = None
    with _pred_lock:
        _last_pred = res
        _last_confidence = conf
        _last_seq_topk = topk
        _predict_busy = False


def start_predict_async(sequence):
    """ì‹œí€€ìŠ¤ë¥¼ ë°±ê·¸ë¼ìš´ë“œì—ì„œ ì˜ˆì¸¡í•˜ë„ë¡ ìš”ì²­. ì´ë¯¸ ì˜ˆì¸¡ ì¤‘ì´ë©´ ë¬´ì‹œ."""
    global _predict_busy
    with _pred_lock:
        if _predict_busy or not sequence or len(sequence) != SEQ_LEN:
            return
        _predict_busy = True
    t = threading.Thread(target=_predict_worker, args=(sequence.copy(),), daemon=True)
    t.start()


def get_last_pred():
    with _pred_lock:
        return _last_pred, _last_confidence, _last_seq_topk


def _low_chamber_straight_punch_ambiguous(
    flat: List[float], pred: Optional[str], margin: float
) -> bool:
    """ê°™ì€ ìª½ ì†ëª©ì´ ì–´ê¹¨ë³´ë‹¤ ì¶©ë¶„ížˆ ì•„ëž˜ë©´ ì§ì„  íŽ€ì¹˜ ë¼ë²¨ì„ UDPë¡œ í™•ì •í•˜ì§€ ì•ŠìŒ(ì–´í¼ ìœˆë“œì—…ê³¼ êµ¬ë¶„)."""
    if not flat or len(flat) < 99 or pred not in ("punch_l", "punch_r"):
        return False
    if pred == "punch_l":
        w_y, s_y = flat[46], flat[34]  # LEFT_WRIST y, LEFT_SHOULDER y
    else:
        w_y, s_y = flat[49], flat[37]  # RIGHT_WRIST y, RIGHT_SHOULDER y
    return bool(w_y > s_y + margin)


def _pose_server_health_ok() -> bool:
    try:
        with urllib.request.urlopen(POSE_SERVER_HEALTH_URL, timeout=0.35) as r:
            return r.getcode() == 200
    except Exception:
        return False


def _wait_pose_server_ready(proc: subprocess.Popen, timeout_sec: float = 60.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        if proc.poll() is not None:
            err = b""
            try:
                if proc.stderr:
                    err = proc.stderr.read()
            except Exception:
                pass
            print("pose_serverê°€ ë°”ë¡œ ì¢…ë£Œë˜ì—ˆìŠµë‹ˆë‹¤ (ì½”ë“œ %s)." % proc.returncode)
            if err:
                print(err.decode(errors="replace")[-1200:])
            return False
        if _pose_server_health_ok():
            return True
        time.sleep(0.25)
    print("pose_server í—¬ìŠ¤ ì²´í¬ íƒ€ìž„ì•„ì›ƒ (%sì´ˆ)." % int(timeout_sec))
    return False


def _ensure_pose_server(auto_spawn: bool):
    """HTTP ì¶”ë¡ ìš© pose_server. (ì„±ê³µ ì—¬ë¶€, ì´ ìŠ¤í¬ë¦½íŠ¸ê°€ ë„ìš´ Popen ë˜ëŠ” None)."""
    if _pose_server_health_ok():
        print("ì¶”ë¡ : pose_server (HTTP, ì´ë¯¸ ì‹¤í–‰ ì¤‘)")
        return True, None
    if not auto_spawn:
        print("ì¶”ë¡ : pose_server í•„ìš”. ìˆ˜ë™ ì‹¤í–‰: cd tools && python pose_server.py")
        print("      (ìžë™ ì‹œìž‘ì„ ì“°ë ¤ë©´ --no-auto-server ì˜µì…˜ì„ ë¹¼ì„¸ìš”)")
        return False, None
    if not os.path.isfile(MODEL_SEQ_PATH):
        print("ë¡œì»¬ ì¶”ë¡  ë¶ˆê°€ + pose_classifier_seq.keras ì—†ìŒ â†’ pose_serverë¥¼ ì‹œìž‘í•  ìˆ˜ ì—†ìŠµë‹ˆë‹¤.")
        return False, None
    if not os.path.isfile(POSE_SERVER_SCRIPT):
        print("pose_server.pyë¥¼ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤:", POSE_SERVER_SCRIPT)
        return False, None
    print("ë¡œì»¬ ì¶”ë¡  ë¶ˆê°€ â†’ pose_server ìžë™ ì‹œìž‘ ì¤‘...")
    proc = subprocess.Popen(
        [sys.executable, POSE_SERVER_SCRIPT],
        cwd=SCRIPT_DIR,
    )
    if not _wait_pose_server_ready(proc):
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return False, None
    print("pose_server ì¤€ë¹„ ì™„ë£Œ (http://127.0.0.1:5000)")
    return True, proc


def main():
    global MODEL_SEQ_PATH
    parser = argparse.ArgumentParser(description="Webcam -> ML -> UDP for Body Hero")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index (ê¸°ë³¸ 0, ì™¸ë¶€ ì›¹ìº ì€ 1/2ì¼ ìˆ˜ ìžˆìŒ)")
    parser.add_argument(
        "--camera-backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windows ê¶Œìž¥: auto(DirectShow ìš°ì„ ). USBê°€ ì•ˆ ìž¡ížˆë©´ dshow + --camera-index ë°”ê¿” ë³´ì„¸ìš”.",
    )
    parser.add_argument(
        "--no-auto-server",
        action="store_true",
        help="ë¡œì»¬ ì¶”ë¡  ë¶ˆê°€ ì‹œ pose_serverë¥¼ ìžë™ìœ¼ë¡œ ë„ìš°ì§€ ì•ŠìŒ (ë³„ë„ í„°ë¯¸ë„ì—ì„œ ìˆ˜ë™ ì‹¤í–‰)",
    )
    parser.add_argument(
        "--process-w",
        type=int,
        default=None,
        metavar="W",
        help=f"MediaPipe/ML ìž…ë ¥ ë„ˆë¹„ (ê¸°ë³¸ {PROCESS_W}, ê°€ë²¼ìš°ë ¤ë©´ 320)",
    )
    parser.add_argument(
        "--process-h",
        type=int,
        default=None,
        metavar="H",
        help=f"MediaPipe/ML ìž…ë ¥ ë†’ì´ (ê¸°ë³¸ {PROCESS_H})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="ë¯¸ë¦¬ë³´ê¸° ì°½ ì—†ì´ ì‹¤í–‰ (opencv-python-headlessÂ·ì›ê²© í„°ë¯¸ë„ ë“±). ì¢…ë£Œ: Ctrl+C",
    )
    parser.add_argument(
        "--allow-tf-gpu",
        action="store_true",
        help="TensorFlowê°€ GPU/CUDAë¥¼ íƒìƒ‰í•˜ê²Œ í•¨. ê¸°ë³¸ì€ CPUë§Œ ì‚¬ìš©í•´ ì²« ìž„í¬íŠ¸ê°€ ë” ë¹ ë¥¸ ê²½ìš°ê°€ ë§ŽìŒ.",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="MediaPipe GPU delegate 사용 (OpenGL ES). 기본= CPU.",
    )
    parser.add_argument(
        "--full-model",
        action="store_true",
        help="Full Pose Landmarker 사용 (더 정확, 더 느림). 기본=Lite.",
    )
    parser.add_argument(
        "--seq-model",
        default=None,
        help="ì‹œí€€ìŠ¤ ëª¨ë¸ ê²½ë¡œ(ê¸°ë³¸ tools/pose_classifier_seq.keras). seq_len4/6/8 ëª¨ë¸ì„ ë°”ê¿” ë¼ì›Œ ì²« ë°˜ì‘ ì†ë„ íŠœë‹ ê°€ëŠ¥",
    )
    parser.add_argument(
        "--profile",
        choices=list(SPEED_PROFILES),
        default="balanced",
        help="í”„ë¡œí•„: precise(ì •í™•ë„ìµœìš°ì„ ) | balanced(ê¸°ë³¸) | classic(ì´ˆê¸°ë²„ì „ëŠë‚Œ) | rapid(ë¹ ë¥¸ì—°íƒ€) | max_speed(ìµœëŒ€ì†ë„), ê¸°ë³¸ balanced",
    )
    parser.add_argument(
        "--react",
        type=float,
        default=None,
        help="ë°˜ì‘ ì†ë„(0~1). ë†’ì„ìˆ˜ë¡ ìž„ê³„ê°’ í•˜í–¥ + ì¿¨ë‹¤ìš´ ë‹¨ì¶•. --profile ìœ„ì— ì¶”ê°€ ì¡°ì •",
    )
    parser.add_argument(
        "--combo",
        type=float,
        default=None,
        help="ì—°íƒ€ ì†ë„(0~1). ë†’ì„ìˆ˜ë¡ COOLDOWN/MIN_GAPì„ profile ê¸°ì¤€ ìµœëŒ€ 60%%ê¹Œì§€ ë‹¨ì¶•",
    )
    parser.add_argument(
        "--debug-topk",
        type=int,
        default=0,
        metavar="K",
        help="ì‹œí€€ìŠ¤ ëª¨ë¸ softmax ìƒìœ„ Kê°œë¥¼ í™”ë©´ ì™¼ìª½ì— í‘œì‹œ(0=ë”). íŽ€ì¹˜ê°€ ìˆœìœ„ì—ë§Œ ì˜¬ë¼ì˜¤ëŠ”ì§€Â·í™•ë¥ ì´ ì–¼ë§ˆì¸ì§€ í™•ì¸.",
    )
    parser.add_argument(
        "--skip-guard-single",
        action="store_true",
        help="ë§ˆì§€ë§‰ í”„ë ˆìž„ ê°€ë“œ ë‹¨ì¼ ëª¨ë¸ ë‹¨ì¶•ì„ ëˆë‹¤. ê°€ë“œì— íŽ€ì¹˜ê°€ ë¨¹ížˆëŠ”ì§€ ë¹„êµìš©(ì‹œí€€ìŠ¤ë§Œìœ¼ë¡œ ë¼ë²¨ ê²°ì •).",
    )
    parser.add_argument(
        "--full-body-squat",
        action="store_true",
        help="ìŠ¤ì¿¼íŠ¸ íŒì • ì‹œ í•˜ì²´ visibility + ì—‰ë©ì´ í•˜ê°•ì„ ìš”êµ¬. ì „ì‹ ì´ ë³´ì¼ ë•Œë§Œ ìŠ¤ì¿¼íŠ¸ ì¸ì‹. ê¸°ë³¸ì€ ë”(ìƒë°˜ì‹ ë§Œìœ¼ë¡œë„ ìŠ¤ì¿¼íŠ¸ ê°€ëŠ¥).",
    )
    parser.add_argument(
        "--punch-confidence",
        type=float,
        default=None,
        metavar="P",
        help="punch_l/punch_rë§Œ ì±„íƒ ìµœì†Œ softmax(0~1). ìƒëžµ ì‹œ í”„ë¡œí•„ì˜ PUNCH_CONFIDENCE_THRESHOLD. ì•½í•˜ë©´ 0.55~0.88ë¡œ ì‹œí—˜.",
    )
    parser.add_argument(
        "--upper-windup-punch-suppress",
        action="store_true",
        help="ë‚®ì€ ì¤€ë¹„(ì†ëª©ì´ ì–´ê¹¨ ì•„ëž˜)ì—ì„œ punch_l/r UDP í™•ì • ì–µì œ(ì–´í¼ ìœˆë“œì—… ì‹œ ì§ì„  ë¨¼ì € ë‚˜ê° ì™„í™”). ê¸°ë³¸ì€ ë”.",
    )
    parser.add_argument(
        "--upper-windup-punch-margin",
        type=float,
        default=None,
        metavar="M",
        help="ì–µì œ íŒì •: ì†ëª© y > ì–´ê¹¨ y + M ì¼ ë•Œ ì§ì„  íŽ€ì¹˜ ë¯¸í™•ì •. ê¸°ë³¸ %.2f (--upper-windup-punch-suppress ì¼°ì„ ë•Œë§Œ)."
        % UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT,
    )
    parser.add_argument(
        "--attack-rearm-frames",
        type=int,
        default=ACTION_REARM_OFF_ATTACK_FRAMES_DEFAULT,
        metavar="N",
        help="íŽ€ì¹˜Â·ì–´í¼ UDP 1íšŒ í›„, punch/upper ê°€ ì•„ë‹Œ ë¼ë²¨ì´ Ní”„ë ˆìž„ ì—°ì†ì¼ ë•Œë§Œ ë‹¤ìŒ íŽ€ì¹˜Â·ì–´í¼ í—ˆìš©. ê¸°ë³¸ 3. 0=ë”.",
    )
    parser.add_argument(
        "--roi",
        action="store_true",
        help="ROI ëª¨ë“œ: í”Œë ˆì´ì–´ ì¶”ì  í›„ ì£¼ë³€ë§Œ í¬ë¡­í•˜ì—¬ MediaPipeì— ì „ë‹¬. ì „ì‹œíšŒ ë“± ë§Žì€ ì‚¬ëžŒì´ ì§€ë‚˜ë‹¤ë‹ ë•Œ ê°„ì„­ ìµœì†Œí™”.",
    )
    parser.add_argument(
        "--center-zone",
        type=float,
        default=0.3,
        metavar="M",
        help="ê°€ë¡œ ì¤‘ì‹¬ ì˜ì—­ margin (0.0~0.5). ì„¸ë¡œëŠ” í•­ìƒ ì „ì²´. M=0.3 â†’ ê°€ë¡œ 30~70%%. ê¸°ë³¸ 0.3.",
    )
    args = parser.parse_args()
    if args.allow_tf_gpu:
        os.environ["BODY_HERO_TF_CPU_ONLY"] = "0"

    global _debug_seq_topk, _skip_guard_single, _punch_confidence_override
    _debug_seq_topk = max(0, int(args.debug_topk))
    _skip_guard_single = bool(args.skip_guard_single)
    full_body_squat: bool = bool(args.full_body_squat)
    if args.punch_confidence is not None:
        jc = float(args.punch_confidence)
        if jc < 0.0 or jc > 1.0:
            print("--punch-confidence ëŠ” 0~1 ì‚¬ì´ì—¬ì•¼ í•©ë‹ˆë‹¤. ë¬´ì‹œí•©ë‹ˆë‹¤.", flush=True)
            _punch_confidence_override = None
        else:
            _punch_confidence_override = jc
    else:
        _punch_confidence_override = None

    # ---- runtime tuning (profile + react/combo sliders) ----
    global MODEL_SEQ_PATH
    global CONFIDENCE_THRESHOLD, UPPER_CONFIDENCE_THRESHOLD, PUNCH_CONFIDENCE_THRESHOLD
    global COOLDOWN_SEC, MIN_GAP_BETWEEN_ANY_PUNCH_SEC
    global PUNCH_CONFIRM_FRAMES, OTHER_PUNCH_CONFIRM_FRAMES, UPPER_PUNCH_CONFIRM_FRAMES
    global UPPER_MOTION_MEAN_ABS_MIN, UPPER_L_MOTION_RELAX

    if args.seq_model:
        MODEL_SEQ_PATH = args.seq_model

    if args.profile == "precise":
        PUNCH_CONFIRM_FRAMES = 2
        OTHER_PUNCH_CONFIRM_FRAMES = 2
        UPPER_PUNCH_CONFIRM_FRAMES = 2
        SQUAT_CONFIRM_FRAMES = 3
        COOLDOWN_SEC = 0.12
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.10
        CONFIDENCE_THRESHOLD = 0.95
        UPPER_CONFIDENCE_THRESHOLD = 0.90
        PUNCH_CONFIDENCE_THRESHOLD = 0.88
        UPPER_MOTION_MEAN_ABS_MIN = 0.0020
        UPPER_L_MOTION_RELAX = 0.65
    elif args.profile == "balanced":
        PUNCH_CONFIRM_FRAMES = 2
        OTHER_PUNCH_CONFIRM_FRAMES = 1
        UPPER_PUNCH_CONFIRM_FRAMES = 2
        SQUAT_CONFIRM_FRAMES = 2
        COOLDOWN_SEC = 0.10
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.08
        CONFIDENCE_THRESHOLD = 0.93
        UPPER_CONFIDENCE_THRESHOLD = 0.88
        PUNCH_CONFIDENCE_THRESHOLD = 0.85
        UPPER_MOTION_MEAN_ABS_MIN = 0.0015
        UPPER_L_MOTION_RELAX = 0.55
    elif args.profile == "classic":
        # ì´ˆê¸°ë²„ì „ LSTM ëª¨ë¸ ì‚¬ìš© + ë‚®ì€ thresholds
        if not args.seq_model:
            classic_path = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4_classic.keras")
            if os.path.isfile(classic_path):
                MODEL_SEQ_PATH = classic_path
        PUNCH_CONFIRM_FRAMES = 1
        OTHER_PUNCH_CONFIRM_FRAMES = 1
        UPPER_PUNCH_CONFIRM_FRAMES = 1
        SQUAT_CONFIRM_FRAMES = 1
        COOLDOWN_SEC = 0.04
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.02
        CONFIDENCE_THRESHOLD = 0.75
        UPPER_CONFIDENCE_THRESHOLD = 0.65
        PUNCH_CONFIDENCE_THRESHOLD = 0.55
        UPPER_MOTION_MEAN_ABS_MIN = 0.0005
        UPPER_L_MOTION_RELAX = 0.40
    elif args.profile == "rapid":
        PUNCH_CONFIRM_FRAMES = 1
        OTHER_PUNCH_CONFIRM_FRAMES = 1
        UPPER_PUNCH_CONFIRM_FRAMES = 1
        SQUAT_CONFIRM_FRAMES = 1
        COOLDOWN_SEC = 0.08
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.06
        CONFIDENCE_THRESHOLD = 0.85
        UPPER_CONFIDENCE_THRESHOLD = 0.78
        PUNCH_CONFIDENCE_THRESHOLD = 0.72
        UPPER_MOTION_MEAN_ABS_MIN = 0.0010
        UPPER_L_MOTION_RELAX = 0.50
    elif args.profile == "max_speed":
        PUNCH_CONFIRM_FRAMES = 1
        OTHER_PUNCH_CONFIRM_FRAMES = 1
        UPPER_PUNCH_CONFIRM_FRAMES = 1
        SQUAT_CONFIRM_FRAMES = 1
        COOLDOWN_SEC = 0.04
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.02
        CONFIDENCE_THRESHOLD = 0.75
        UPPER_CONFIDENCE_THRESHOLD = 0.65
        PUNCH_CONFIDENCE_THRESHOLD = 0.55
        UPPER_MOTION_MEAN_ABS_MIN = 0.0005
        UPPER_L_MOTION_RELAX = 0.40

    if args.react is not None:
        r = max(0.0, min(1.0, float(args.react)))
        COOLDOWN_SEC *= (1.1 - 0.5 * r)
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC *= (1.1 - 0.5 * r)
        CONFIDENCE_THRESHOLD *= (1.0 - 0.15 * r)
        UPPER_CONFIDENCE_THRESHOLD *= (1.0 - 0.20 * r)
        PUNCH_CONFIDENCE_THRESHOLD *= (1.0 - 0.25 * r)

    if args.combo is not None:
        c = max(0.0, min(1.0, float(args.combo)))
        COOLDOWN_SEC *= (1.0 - 0.6 * c)
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC *= (1.0 - 0.6 * c)
    process_w = PROCESS_W if args.process_w is None else max(64, args.process_w)
    process_h = PROCESS_H if args.process_h is None else max(64, args.process_h)
    upper_windup_margin = UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT
    if args.upper_windup_punch_margin is not None:
        upper_windup_margin = max(0.0, float(args.upper_windup_punch_margin))
    suppress_low_chamber_punch = bool(args.upper_windup_punch_suppress)
    attack_rearm_n: int = max(0, int(args.attack_rearm_frames))
    roi_mode: bool = bool(args.roi)
    zone_margin: float = max(0.0, min(0.5, float(args.center_zone)))
    CENTER_ZONE_X = (zone_margin, 1.0 - zone_margin)
    CENTER_ZONE_Y = (0.0, 1.0)  # ì„¸ë¡œëŠ” í•­ìƒ ì „ì²´ â€” ìŠ¤ì¿¼íŠ¸ ì¸ì‹ ë°©í•´ ë°©ì§€
    spawned_server = None
    cap = None
    landmarker = None
    sock = None

    try:
        use_full = args.full_model
        model_path = MODEL_PATH_FULL if use_full else MODEL_PATH_LITE
        model_url = MODEL_URL_FULL if use_full else MODEL_URL_LITE
        model_fallback = None if use_full else MODEL_URL_LITE_FALLBACK
        _download_pose_model(model_path, model_url, model_fallback)
        print(f"Pose Landmarker: {'Full' if use_full else 'Lite'}", flush=True)

        load_errors: list = []
        seq_model_ready = threading.Event()
        load_th = threading.Thread(
            target=_tf_load_worker_phased,
            args=(seq_model_ready, load_errors),
            daemon=True,
            name="tf_keras_seq",
        )
        load_th.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cap, cap_backend_note = open_cv_video_capture(args.camera_index, args.camera_backend)
        if not cap.isOpened():
            print(f"ì›¹ìº ì„ ì—´ ìˆ˜ ì—†ìŠµë‹ˆë‹¤. (--camera-index {args.camera_index} --camera-backend {args.camera_backend})")
            load_th.join(timeout=3.0)
            return

        print(
            f"ì¹´ë©”ë¼ ì—´ë¦¼: index={args.camera_index} backend={args.camera_backend} ({cap_backend_note})",
            flush=True,
        )

        BaseOptions = mp_tasks.BaseOptions
        PoseLandmarker = vision.PoseLandmarker
        PoseLandmarkerOptions = vision.PoseLandmarkerOptions
        RunningMode = vision.RunningMode
        _gpu_delegate = BaseOptions.Delegate.CPU
        if args.gpu:
            try:
                _gpu_delegate = BaseOptions.Delegate.GPU
                print("[ì„¤ì •] MediaPipe GPU delegate ì‚¬ìš© ì¤‘...", flush=True)
            except AttributeError:
                print("[ê²½ê³ ] ì´ MediaPipe ë²„ì „ì´ GPU delegateë¥¼ ì§€ì›í•˜ì§€ ì•ŠìŒ, CPU ì‚¬ìš©", flush=True)
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path, delegate=_gpu_delegate),
            running_mode=RunningMode.VIDEO,
            num_poses=3,
            min_pose_detection_confidence=0.55,
            min_tracking_confidence=0.7,
            min_pose_presence_confidence=0.5,
        )

        landmarker_holder: dict = {"lm": None, "err": None}

        def _mp_init_worker() -> None:
            try:
                landmarker_holder["lm"] = PoseLandmarker.create_from_options(options)
            except BaseException as e:
                landmarker_holder["err"] = e

        mp_th = threading.Thread(target=_mp_init_worker, daemon=True, name="mediapipe_pose_init")
        mp_th.start()

        t_load0 = time.time()
        gui_load_wait: bool = not args.headless
        last_console_ping = 0.0
        while mp_th.is_alive() or not seq_model_ready.is_set():
            if time.time() - t_load0 > 900.0:
                print("ëª¨ë¸ ë¡œë”© íƒ€ìž„ì•„ì›ƒ(900ì´ˆ).", flush=True)
                return
            wait_bits: list = []
            if mp_th.is_alive():
                wait_bits.append("MediaPipe")
            if not seq_model_ready.is_set():
                wait_bits.append("TensorFlow")
            status_line = (" + ").join(wait_bits) + " ..." if wait_bits else "..."
            ok, frame = cap.read()
            if gui_load_wait and ok:
                frame = cv2.flip(frame, 1)
                frame_s = cv2.resize(frame, (process_w, process_h))
                cv2.putText(
                    frame_s,
                    status_line,
                    (12, 32),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.62,
                    (0, 220, 255),
                    2,
                )
                sec = int(time.time() - t_load0)
                cv2.putText(
                    frame_s,
                    "%d s" % sec,
                    (12, 64),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.65,
                    (200, 200, 200),
                    2,
                )
                try:
                    cv2.imshow("Body Hero â€” ML Pose", frame_s)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        print("ë¡œë”© ì¤‘ ì‚¬ìš©ìžê°€ Që¡œ ì¢…ë£Œí–ˆìŠµë‹ˆë‹¤.")
                        return
                except Exception:
                    gui_load_wait = False
            else:
                time.sleep(0.05)
            if not gui_load_wait and time.time() - last_console_ping > 8.0:
                print("ì¤€ë¹„ ì¤‘ (%s) %.0fì´ˆ ê²½ê³¼" % (status_line, time.time() - t_load0), flush=True)
                last_console_ping = time.time()

        mp_th.join()
        if landmarker_holder["err"] is not None and _gpu_delegate != BaseOptions.Delegate.CPU:
            print("[GPU] GPU delegate ì‹¤íŒ¨, CPUë¡œ í´ë°±", flush=True)
            _gpu_delegate = BaseOptions.Delegate.CPU
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path, delegate=BaseOptions.Delegate.CPU),
                running_mode=RunningMode.VIDEO,
                num_poses=3,
                min_pose_detection_confidence=0.55,
                min_tracking_confidence=0.7,
                min_pose_presence_confidence=0.5,
            )
            landmarker_holder = {"lm": None, "err": None}
            mp_th = threading.Thread(target=_mp_init_worker, daemon=True, name="mediapipe_pose_init")
            mp_th.start()
            mp_th.join()
        if landmarker_holder["err"] is not None:
            raise landmarker_holder["err"]
        landmarker = landmarker_holder["lm"]
        if landmarker is None:
            print("MediaPipe PoseLandmarker ì´ˆê¸°í™”ì— ì‹¤íŒ¨í–ˆìŠµë‹ˆë‹¤.", flush=True)
            return

        def make_mp_image(rgb):
            return mp_core_image.Image(image_format=mp_core_image.ImageFormat.SRGB, data=rgb.copy(order="C"))

        def letterbox_square_bgr(bgr, side: int):
            """ë¹„ì •ì‚¬ê° ìž…ë ¥ ì‹œ MediaPipe NORM_RECT ê²½ê³  ì™„í™”(ì •ì‚¬ê° ROI)."""
            h, w = bgr.shape[:2]
            if h <= 0 or w <= 0:
                return bgr
            scale = min(side / w, side / h)
            nw = max(1, int(round(w * scale)))
            nh = max(1, int(round(h * scale)))
            resized = cv2.resize(bgr, (nw, nh))
            top = (side - nh) // 2
            left = (side - nw) // 2
            bottom = side - nh - top
            right = side - nw - left
            return cv2.copyMakeBorder(
                resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )

        mp_square_side = max(process_w, process_h)

        if load_errors:
            print("ëª¨ë¸ ë¡œë“œ ì‹¤íŒ¨:", load_errors[0], flush=True)
            raise load_errors[0]

        if _use_local_inference:
            guard_ok = (
                "ê°€ë“œ í´ë°± O"
                if _model_single is not None
                else "ê°€ë“œ í´ë°± X(ì‹œí€€ìŠ¤ë§Œ, ë³´ì¡° ëª¨ë¸ì€ ë°±ê·¸ë¼ìš´ë“œ ë¡œë”© ì¤‘ì¼ ìˆ˜ ìžˆìŒ)"
            )
            print("ì¶”ë¡ : ë¡œì»¬ ëª¨ë¸ (pose_server ë¶ˆí•„ìš”). %s (ì‹œí€€ìŠ¤ %dí”„ë ˆìž„)" % (guard_ok, SEQ_LEN), flush=True)
        else:
            ok, spawned_server = _ensure_pose_server(auto_spawn=not args.no_auto_server)
            if not ok:
                return

        print("ë¡œì»¬ ê°€ì¤‘ì¹˜ ì¤€ë¹„ ì™„ë£Œ (%.1fì´ˆ)" % (time.time() - t_load0), flush=True)

        last_action_time = 0.0
        last_any_punch_send_time = -999.0
        last_punch_l_send_time = -999.0
        last_punch_r_send_time = -999.0
        guarding = False
        guard_exit_count = 0
        punch_l_count = 0
        punch_r_count = 0
        other_punch_pred = None
        other_punch_count = 0
        squat_count = 0
        squat_armed = True
        hip_y_recent: deque = deque(maxlen=15)  # ìµœê·¼ ì—‰ë©ì´ yì¢Œí‘œ (ìŠ¤ì¿¼íŠ¸ ì˜¤ì¸ì‹ ë°©ì§€ìš©)
        last_upper_sent_side = None  # "l" | "r" â€” upper_l/upper_r ì§í›„ ë°˜ëŒ€ìª½ ì–´í¼ í™•ì • ì–µì œìš©
        upper_block_other_until_frame = 0
        punch_holdoff_until_frame = 0
        none_streak = 0
        frame_idx = 0
        sequence_buffer = []  # ìµœê·¼ SEQ_LENí”„ë ˆìž„ (test_pose_liveì²˜ëŸ¼ í¬ì¦ˆ ìžˆìœ¼ë©´ ë¬´ì¡°ê±´ ì¶”ê°€)
        last_lm = None
        last_flat = None
        prev_flat_norm = None  # ì§ì „ í¬ì¦ˆ ì •ê·œí™” ë²¡í„° â€” ì–´í¼ ì¤€ë¹„(ì €ì†) vs ì‹¤ì œ ê¶¤ì  êµ¬ë¶„ìš©
        motion_mean_abs = 0.0
        pred_history: deque = deque(maxlen=12)
        in_zone = False  # Godot ì „ì†¡ ì—¬ë¶€ë§Œ ì œì–´
        last_sent_side: str = ""  # "l" or "r", same-hand rearm용
        sent_side_none_streak: int = 0  # none 연속 프레임 카운터 (last_sent_side 리셋용)

        # ë©€í‹° íŽ˜ë¥´ì†Œë‚˜ ì¶”ì  ìƒíƒœ (ì „ì‹œíšŒ ë“± ê°„ì„­ ë°©ì§€)
        tracked_center: Tuple[float, float] = (0.5, 0.5)
        tracked_width: float = 0.0
        tracked_bbox: Optional[Tuple[int, int, int, int]] = None
        track_lost_frames: int = 0
        MAX_TRACK_LOST: int = 60
        TRACK_JUMP_THRESHOLD: float = 0.10
        ROI_PADDING_RATIO: float = 0.30
        ROI_FULL_SCAN_INTERVAL: int = 15
        roi_active: bool = False
        MIN_SHOULDER_WIDTH: float = 0.025

        def _select_player_pose(landmarks_list, tc, tw):
            scored: list = []
            for i, lm in enumerate(landmarks_list):
                try:
                    (cx, cy), w = shoulder_center_and_width(lm)
                except Exception:
                    continue
                if w < MIN_SHOULDER_WIDTH or w > 0.50:
                    continue
                if tw > 0.001:
                    dist: float = math.hypot(cx - tc[0], cy - tc[1])
                    sd: float = abs(w - tw) / max(tw, 0.001)
                    score: float = dist + sd * 2.0
                else:
                    dc: float = math.hypot(cx - 0.5, cy - 0.5)
                    score: float = dc
                scored.append((score, i, (cx, cy), w))
            if not scored:
                return None, -1, 0.0
            scored.sort(key=lambda x: x[0])
            best = scored[0]
            return landmarks_list[best[1]], best[1], float(best[3])

        def _compute_landmark_bbox(landmarks, w, h):
            xs: list = []
            ys: list = []
            for lm in landmarks:
                if hasattr(lm, "x"):
                    xs.append(lm.x * w)
                    ys.append(lm.y * h)
                else:
                    xs.append(lm[0] * w)
                    ys.append(lm[1] * h)
            return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

        def _lower_body_visible(landmarks) -> bool:
            """í•˜ì²´ ëžœë“œë§ˆí¬(23~28)ì˜ visibilityê°€ ì¶©ë¶„í•œì§€ í™•ì¸."""
            if not landmarks or len(landmarks) < 29:
                return False
            key_indices = [23, 24, 25, 26, 27, 28]
            visible_count = 0
            for idx in key_indices:
                lm = landmarks[idx]
                vis = getattr(lm, "visibility", 1.0)
                if vis > 0.5:
                    visible_count += 1
            return visible_count >= 3

        print("ì›¹ìº  + ML(ì‹œí€€ìŠ¤) íŒì • â†’ Godot UDP")
        print(f"ì¹´ë©”ë¼: index={args.camera_index} backend={args.camera_backend} â†’ {cap_backend_note}")
        print(f"ì„¤ì •: í•´ìƒë„ {process_w}x{process_h}, ì‹œí€€ìŠ¤ {SEQ_LEN}í”„ë ˆìž„, FPS ëª©í‘œ {FPS_TARGET}")
        print(
            f"íŽ€ì¹˜: ì§ì„ ì€ ì—°ì† {PUNCH_CONFIRM_FRAMES}í”„ë ˆìž„ í™•ì •, softmax í•˜í•œ "
            f"{PUNCH_CONFIDENCE_THRESHOLD:.2f} (ì–´í¼ {UPPER_PUNCH_CONFIRM_FRAMES}í”„Â·{UPPER_CONFIDENCE_THRESHOLD:.2f})",
            flush=True,
        )
        if attack_rearm_n > 0:
            print(
                f"ê³µê²© ìž¬ìž¥ì „: íŽ€ì¹˜Â·ì–´í¼ ì „ì†¡ í›„, ë¹„ê³µê²© ë¼ë²¨ {attack_rearm_n}í”„ë ˆìž„ ì—°ì† ì‹œì—ë§Œ ë‹¤ìŒ ê³µê²© ì „ì†¡. "
                "ë”: --attack-rearm-frames 0",
                flush=True,
            )
        if suppress_low_chamber_punch:
            print(
                f"ì–´í¼ ìœˆë“œì—… ì–µì œ ì¼¬: ì†ëª©ì´ ê°™ì€ìª½ ì–´ê¹¨ë³´ë‹¤ y+{upper_windup_margin:.2f} ì´ìƒ ì•„ëž˜ë©´ "
                "punch_l/r UDP í™•ì • ì•ˆ í•¨.",
                flush=True,
            )
        if _debug_seq_topk <= 0 and _punch_confidence_override is None and not _skip_guard_single:
            print(
                "íŒ: ìƒë‹¨ì— punch_l/punch_rì´ ì „í˜€ ì•ˆ ëœ¨ë©´: --debug-topk 5 (ì‹œí€€ìŠ¤ ìˆœìœ„Â·í™•ë¥ ), "
                "ë˜ëŠ” --punch-confidence 0.55 / --skip-guard-single",
                flush=True,
            )
        gui_enabled: bool = not args.headless
        if args.headless:
            print("í—¤ë“œë¦¬ìŠ¤ ëª¨ë“œ: ë¯¸ë¦¬ë³´ê¸° ì°½ ì—†ìŒ. ì¢…ë£Œ: Ctrl+C")
        else:
            print("ì¢…ë£Œ: Q í‚¤ ë˜ëŠ” Ctrl+C")
        print("â€» [ì•¡ì…˜] í•œ ì¤„ = UDPë¡œ ê²Œìž„ì— ì „ì†¡ 1íšŒìž…ë‹ˆë‹¤. ê°™ì€ ì¤„ì´ ì—°ì†ì´ë©´ ê·¸ë§Œí¼ ì—¬ëŸ¬ ë²ˆ ë‚˜ê°„ ê²ƒìž…ë‹ˆë‹¤.\n")

        def send(action: str):
            sock.sendto(action.encode("utf-8"), (GODOT_HOST, GODOT_PORT))
            print(f"  [ì•¡ì…˜] {action}")

        try:
            while True:
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    time.sleep(1 / FPS_TARGET)
                    continue

                frame = cv2.flip(frame, 1)
                frame_small = cv2.resize(frame, (process_w, process_h))
                frame_mp = letterbox_square_bgr(frame_small, mp_square_side)
                rgb = cv2.cvtColor(frame_mp, cv2.COLOR_BGR2RGB)
                ts_ms = int(frame_idx * 1000 / FPS_TARGET)
                frame_idx += 1

                best_idx: int = -1
                selected_w: float = 0.0
                result_poses = None

                # test_pose_liveì™€ ë™ì¼: í¬ì¦ˆ ìžˆìœ¼ë©´ ë²„í¼ì— ì¶”ê°€, SEQ_LENê°œ ì°¨ë©´ ì˜ˆì¸¡ ìš”ì²­ (zone ë¬´ê´€)
                run_pose_this_frame = (frame_idx % PROCESS_EVERY_N_FRAMES == 0)
                do_full_scan: bool = (
                    (frame_idx % ROI_FULL_SCAN_INTERVAL == 0)
                    or (not roi_mode)
                    or (not roi_active)
                    or (track_lost_frames > MAX_TRACK_LOST // 2)
                )
                use_roi_crop: bool = (
                    roi_mode
                    and roi_active
                    and not do_full_scan
                    and tracked_bbox is not None
                )

                if run_pose_this_frame:
                    if use_roi_crop:
                        rx1, ry1, rx2, ry2 = tracked_bbox
                        pad_x: int = int((rx2 - rx1) * ROI_PADDING_RATIO)
                        pad_y: int = int((ry2 - ry1) * ROI_PADDING_RATIO)
                        fh, fw = frame_small.shape[:2]
                        rx1 = max(0, rx1 - pad_x)
                        ry1 = max(0, ry1 - pad_y)
                        rx2 = min(fw, rx2 + pad_x)
                        ry2 = min(fh, ry2 + pad_y)
                        crop_w: int = rx2 - rx1
                        crop_h: int = ry2 - ry1
                        if crop_w >= 80 and crop_h >= 80:
                            crop = frame_small[ry1:ry2, rx1:rx2]
                            crop_rs = cv2.resize(crop, (process_w, process_h))
                            crop_mp = letterbox_square_bgr(crop_rs, mp_square_side)
                            rgb = cv2.cvtColor(crop_mp, cv2.COLOR_BGR2RGB)
                            result = landmarker.detect_for_video(make_mp_image(rgb), ts_ms)
                            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                                all_remapped: list = []
                                for pose_lm in result.pose_landmarks:
                                    rlist: list = []
                                    for lm in pose_lm:
                                        gx: float = (rx1 + lm.x * crop_w) / fw
                                        gy: float = (ry1 + lm.y * crop_h) / fh
                                        gz: float = lm.z
                                        gvis: float = getattr(lm, "visibility", 1.0)
                                        rlist.append(RemappedLandmark(gx, gy, gz, gvis))
                                    all_remapped.append(rlist)
                                result_poses = all_remapped
                            else:
                                result_poses = None
                        else:
                            result_poses = None
                    elif do_full_scan:
                        result = landmarker.detect_for_video(make_mp_image(rgb), ts_ms)
                        result_poses = result.pose_landmarks if result.pose_landmarks else None
                    else:
                        result_poses = None

                    if result_poses and len(result_poses) > 0:
                        best_lm, best_idx, selected_w = _select_player_pose(
                            result_poses, tracked_center, tracked_width
                        )
                        if best_lm is None:
                            # ìœ íš¨í•œ í¬ì¦ˆ ì—†ìŒ (ì–´ê¹¨ ë„ˆë¹„ ë¹„ì •ìƒ) â†’ íƒì§€ ì‹¤íŒ¨ë¡œ ì²˜ë¦¬
                            last_lm = None
                            sequence_buffer.clear()
                            globals().update(_ema_logits=None, _active_state=None)
                            prev_flat_norm = None
                            motion_mean_abs = 0.0
                            in_zone = False
                            track_lost_frames += 1
                            if track_lost_frames > MAX_TRACK_LOST:
                                roi_active = False
                                tracked_width = 0.0
                        else:
                            (cx, cy), w = shoulder_center_and_width(best_lm)
                            hh, ww = frame_small.shape[:2]
                            bbox = _compute_landmark_bbox(best_lm, ww, hh)
                            selected_w = w

                            pose_accepted: bool = True
                            jump: float = math.hypot(cx - tracked_center[0], cy - tracked_center[1])
                            width_collapse: bool = (
                                tracked_width > 0.02
                                and w < tracked_width * 0.4
                                and jump < TRACK_JUMP_THRESHOLD * 1.5
                            )

                            if track_lost_frames == 0 and jump > TRACK_JUMP_THRESHOLD:
                                track_lost_frames += 1
                                pose_accepted = False
                            elif width_collapse:
                                # ê°€ë“œ ìžì„¸: ì–´ê¹¨ê°€ ê°€ë ¤ì ¸ ë„ˆë¹„ê°€ ì¼ì‹œì ìœ¼ë¡œ ê¸‰ê°.
                                # ìœ„ì¹˜Â·bboxëŠ” ê°±ì‹ , ë„ˆë¹„ë§Œ ê¸°ì¡´ ê°’ ìœ ì§€.
                                track_lost_frames = 0
                                tracked_center = (cx, cy)
                                tracked_bbox = bbox
                                pose_accepted = True
                            elif jump > TRACK_JUMP_THRESHOLD and track_lost_frames < MAX_TRACK_LOST:
                                track_lost_frames += 1
                                pose_accepted = False
                            else:
                                track_lost_frames = 0
                                tracked_center = (cx, cy)
                                tracked_width = w
                                tracked_bbox = bbox
                                roi_active = True
                                pose_accepted = True

                            if pose_accepted:
                                last_lm = best_lm
                                in_zone = (CENTER_ZONE_X[0] <= cx <= CENTER_ZONE_X[1] and
                                           CENTER_ZONE_Y[0] <= cy <= CENTER_ZONE_Y[1])
                                last_flat = normalize_landmarks_flat(last_lm)
                                if prev_flat_norm is not None and len(prev_flat_norm) == len(last_flat):
                                    motion_mean_abs = sum(
                                        abs(a - b) for a, b in zip(last_flat, prev_flat_norm)
                                    ) / float(len(last_flat))
                                else:
                                    motion_mean_abs = 1.0
                                prev_flat_norm = list(last_flat)
                                sequence_buffer.append(last_flat)
                                if len(sequence_buffer) > SEQ_LEN:
                                    sequence_buffer.pop(0)
                                if len(sequence_buffer) == SEQ_LEN:
                                    start_predict_async(sequence_buffer.copy())
                                # ì—‰ë©ì´ ìœ„ì¹˜ ì¶”ì  (ìŠ¤ì¿¼íŠ¸ ì˜¤ì¸ì‹ ë°©ì§€)
                                if last_lm and len(last_lm) > 24:
                                    try:
                                        hy23: float = last_lm[23].y if hasattr(last_lm[23], "y") else last_lm[23][1]
                                        hy24: float = last_lm[24].y if hasattr(last_lm[24], "y") else last_lm[24][1]
                                        hip_y_recent.append((hy23 + hy24) / 2.0)
                                    except Exception:
                                        pass
                    else:
                        last_lm = None
                        sequence_buffer.clear()
                        globals().update(_ema_logits=None, _active_state=None)
                        prev_flat_norm = None
                        motion_mean_abs = 0.0
                        in_zone = False
                        track_lost_frames += 1
                        if track_lost_frames > MAX_TRACK_LOST:
                            roi_active = False
                            tracked_width = 0.0

                # Draw tracking zone rectangle on frame_small
                if gui_enabled:
                    fsh, fsw = frame_small.shape[:2]
                    # Zone rectangle
                    zx1 = int(CENTER_ZONE_X[0] * fsw)
                    zx2 = int(CENTER_ZONE_X[1] * fsw)
                    zy1 = int(CENTER_ZONE_Y[0] * fsh)
                    zy2 = int(CENTER_ZONE_Y[1] * fsh)
                    zone_color = (0, 255, 200) if in_zone else (80, 80, 180)
                    cv2.rectangle(frame_small, (zx1, zy1), (zx2, zy2), zone_color, 1)
                    # Tracking status
                    if track_lost_frames == 0:
                        ts = "OK"
                        tc = (0, 255, 0)
                    elif track_lost_frames < MAX_TRACK_LOST // 2:
                        ts = "WARN"
                        tc = (0, 200, 255)
                    else:
                        ts = "LOST"
                        tc = (50, 50, 255)
                    if roi_mode:
                        ts = "ROI " + ts
                    cv2.putText(
                        frame_small,
                        f"{ts} #{best_idx}+{len(result_poses) if result_poses else 0} w={selected_w:.3f}",
                        (zx1 + 4, zy1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        tc,
                        1,
                        cv2.LINE_AA,
                    )
                    if roi_mode and roi_active and tracked_bbox is not None:
                        bx1, by1, bx2, by2 = tracked_bbox
                        cv2.rectangle(frame_small, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                        if roi_mode:
                            cv2.putText(frame_small, "ROI", (bx1 + 4, by1 - 6),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                pred, confidence, seq_topk_debug = get_last_pred()
                pred_history.append(pred if pred is not None else "none")
                lm = last_lm

                # same-hand rearm: per-side check in send logic below

                if pred in (None, "none"):
                    none_streak += 1
                    if none_streak >= NONE_STREAK_TO_CLEAR_PUNCH_HOLDOFF:
                        punch_holdoff_until_frame = 0
                else:
                    none_streak = 0
                if pred in PUNCH_LABELS:
                    sent_side_none_streak = 0
                else:
                    sent_side_none_streak += 1
                    if sent_side_none_streak >= 2:
                        last_sent_side = ""
                if pred == "squat":
                    squat_count += 1
                else:
                    squat_count = 0
                    squat_armed = True
                if pred in POWER_PUNCH_LABELS:
                    punch_holdoff_until_frame = max(
                        punch_holdoff_until_frame,
                        frame_idx + PUNCH_HOLDOFF_AFTER_UPPER_FRAMES,
                    )

                action = None
                now = time.time()
                if pred == "guard":
                    guard_exit_count = 0
                    punch_l_count = 0
                    punch_r_count = 0
                    other_punch_pred = None
                    other_punch_count = 0
                    if not guarding and (now - last_action_time) >= 0.15:
                        action = "guard"
                        guarding = True
                else:
                    if guarding:
                        # ê°€ë“œ ì¤‘ MLì´ íŽ€ì¹˜ë¡œ íŠ€ì–´ë„ ì¹´ìš´íŠ¸ë§Œ ìŒ“ì´ë©´ guard_end ì§í›„ ë°”ë¡œ íŽ€ì¹˜ê°€ ë‚˜ê°€ëŠ” ê²ƒ ë°©ì§€
                        punch_l_count = 0
                        punch_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0
                        guard_exit_count += 1
                        if guard_exit_count >= GUARD_EXIT_FRAMES:
                            action = "guard_end"
                            guarding = False
                    if action is None and (now - last_action_time) >= COOLDOWN_SEC:
                        punch_allowed = frame_idx >= punch_holdoff_until_frame
                        if pred == "punch_l":
                            other_punch_pred = None
                            other_punch_count = 0
                            punch_r_count = 0
                            low_chamber = (
                                suppress_low_chamber_punch
                                and last_flat is not None
                                and len(last_flat) >= 99
                                and _low_chamber_straight_punch_ambiguous(
                                    last_flat, pred, upper_windup_margin
                                )
                            )
                            if punch_allowed and not low_chamber:
                                punch_l_count += 1
                            else:
                                punch_l_count = 0
                            if punch_l_count >= PUNCH_CONFIRM_FRAMES:
                                action = "punch_l"
                                punch_l_count = 0
                        elif pred == "punch_r":
                            other_punch_pred = None
                            other_punch_count = 0
                            punch_l_count = 0
                            low_chamber = (
                                suppress_low_chamber_punch
                                and last_flat is not None
                                and len(last_flat) >= 99
                                and _low_chamber_straight_punch_ambiguous(
                                    last_flat, pred, upper_windup_margin
                                )
                            )
                            if punch_allowed and not low_chamber:
                                punch_r_count += 1
                            else:
                                punch_r_count = 0
                            if punch_r_count >= PUNCH_CONFIRM_FRAMES:
                                action = "punch_r"
                                punch_r_count = 0
                        elif pred in ("upper_l", "upper_r"):
                            punch_l_count = 0
                            punch_r_count = 0
                            block_upper_opp = False
                            if pred == "upper_r" and (
                                frame_idx < upper_block_other_until_frame
                                and last_upper_sent_side == "l"
                            ):
                                block_upper_opp = True
                            elif pred == "upper_l" and (
                                frame_idx < upper_block_other_until_frame
                                and last_upper_sent_side == "r"
                            ):
                                block_upper_opp = True
                            is_upper: bool = pred == "upper_l" or pred == "upper_r"
                            confirm_need: int = (
                                UPPER_PUNCH_CONFIRM_FRAMES
                                if is_upper
                                else OTHER_PUNCH_CONFIRM_FRAMES
                            )
                            # ì–´í¼: ì²« ì¹´ìš´íŠ¸ëŠ” ëžœë“œë§ˆí¬ê°€ ì›€ì§ì¼ ë•Œë§Œ(ì¤€ë¹„ ìžì„¸ ì •ì§€ ì–µì œ). í•œë²ˆ ìŒ“ì¸ ë’¤ëŠ” í”¼í¬ì—ì„œ ë©ˆì¶°ë„ ìœ ì§€.
                            motion_min: float = UPPER_MOTION_MEAN_ABS_MIN
                            if pred == "upper_l":
                                motion_min *= UPPER_L_MOTION_RELAX
                            upper_motion_ok: bool = (not is_upper) or (
                                motion_mean_abs >= motion_min
                                or other_punch_count > 0
                            )
                            if block_upper_opp:
                                other_punch_pred = None
                                other_punch_count = 0
                            elif is_upper and not upper_motion_ok:
                                other_punch_pred = None
                                other_punch_count = 0
                            elif pred == other_punch_pred:
                                other_punch_count += 1
                            else:
                                other_punch_pred = pred
                                other_punch_count = 1
                            if other_punch_count >= confirm_need:
                                action = pred
                                other_punch_pred = None
                                other_punch_count = 0
                        elif pred == "squat":
                            # ìŠ¤ì¿¼íŠ¸ 1íšŒ(ì§§ê²Œ ë‚´ë ¤ê°”ë‹¤ ì˜¬ë¼ì˜¤ê¸°)ë‹¹ 1íšŒë§Œ ì „ì†¡.
                            # ìœ ì§€ ìžì„¸ì—ì„œ ë°˜ë³µ ì „ì†¡ë˜ì§€ ì•Šë„ë¡ squat_armed ë¡œ ìž¬ìž¥ì „.
                            punch_l_count = 0
                            punch_r_count = 0
                            other_punch_pred = None
                            other_punch_count = 0
                            # [ìŠ¤ì¿¼íŠ¸ ì˜¤ì¸ì‹ ë°©ì§€] í•˜ì²´ ëžœë“œë§ˆí¬ visibility ì²´í¬ + ì—‰ë©ì´ í•˜ê°• ì²´í¬
                            squat_valid: bool = True
                            if full_body_squat and last_lm and len(last_lm) > 28:
                                if not _lower_body_visible(last_lm):
                                    # í•˜ì²´ê°€ í”„ë ˆìž„ ë°–(visibility ë‚®ìŒ) â†’ ìŠ¤ì¿¼íŠ¸ ë¶ˆê°€
                                    squat_valid = False
                                    squat_count = 0
                                elif len(hip_y_recent) >= 8:
                                    old_hip: float = sum(list(hip_y_recent)[:5]) / min(5, len(hip_y_recent))
                                    new_hip: float = hip_y_recent[-1]
                                    dropped: bool = (new_hip - old_hip) > 0.02
                                    if not dropped:
                                        # í•˜ì²´ëŠ” ë³´ì´ëŠ”ë° ì—‰ë©ì´ê°€ ë‚ ì•„ê°€ì§€ ì•ŠìŒ â†’ ìŠ¤ì¿¼íŠ¸ ì•„ë‹˜
                                        squat_valid = False
                                        squat_count = 0
                            if squat_valid and squat_armed and squat_count >= SQUAT_CONFIRM_FRAMES:
                                action = "squat"
                                squat_armed = False
                        else:
                            # none ë“±: íŽ€ì¹˜ ì¹´ìš´íŠ¸ëŠ” ìœ ì§€. ë™ìž‘ì´ ì§§ì•„ punchâ†’noneâ†’punch íŒ¨í„´ì´ í”í•¨.
                            if pred not in (None, "none"):
                                punch_l_count = 0
                                punch_r_count = 0
                            other_punch_pred = None
                            other_punch_count = 0

                # ê°€ë“œ ì¤‘ì—ëŠ” íŽ€ì¹˜ UDP ë¬´ì‹œ (MLì´ ì–´í¼ë¡œ íŠ€ì–´ë„ ê²Œìž„ ê°€ë“œ ìœ ì§€)
                if guarding and action and action in PUNCH_LABELS:
                    action = None

                if action and action in PUNCH_LABELS:
                    # ê°™ì€ ì† ì—°ì† ë°©ì§€: Lâ†’L ë˜ëŠ” Râ†’Rë§Œ ë§‰ìŒ (Lâ†’Râ†’L ì½¤ë³´ í—ˆìš©)
                    side_time = last_punch_l_send_time if "l" in action else last_punch_r_send_time
                    if (now - side_time) < COOLDOWN_SEC:
                        action = None
                        punch_l_count = 0
                        punch_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0

                if action and action in PUNCH_LABELS:
                    side = "l" if "l" in action else "r" if "r" in action else ""
                    if side and side == last_sent_side:
                        action = None
                        punch_l_count = 0
                        punch_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0

                if action and in_zone:
                    send(action)
                    last_action_time = time.time()
                    if action in PUNCH_LABELS:
                        last_any_punch_send_time = time.time()
                        if "l" in action:
                            last_punch_l_send_time = time.time()
                        elif "r" in action:
                            last_punch_r_send_time = time.time()
                        if action == "upper_l":
                            last_upper_sent_side = "l"
                            upper_block_other_until_frame = (
                                frame_idx + UPPER_LR_OPPOSITE_BLOCK_FRAMES
                            )
                        elif action == "upper_r":
                            last_upper_sent_side = "r"
                            upper_block_other_until_frame = (
                                frame_idx + UPPER_LR_OPPOSITE_BLOCK_FRAMES
                            )
                    if action in POWER_PUNCH_LABELS:
                        punch_holdoff_until_frame = max(
                            punch_holdoff_until_frame,
                            frame_idx + PUNCH_HOLDOFF_AFTER_UPPER_FRAMES,
                        )
                    if action in PUNCH_LABELS and "l" in action:
                        last_sent_side = "l"
                    elif action in PUNCH_LABELS and "r" in action:
                        last_sent_side = "r"

                # ìƒë‹¨ ì¤‘ì•™ì— í˜„ìž¬ ë™ìž‘ í‘œì‹œ
                pred_display = pred if pred else "none"
                conf_display = confidence if pred else 0.0
                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 1.4 if process_w <= 320 else 1.8
                thickness = 3 if process_w <= 320 else 4
                (tw, th), _ = cv2.getTextSize(pred_display, font, font_scale, thickness)
                x_label = (frame_small.shape[1] - tw) // 2
                y_label = 40
                if pred_display == "none":
                    color = (255, 255, 255)
                else:
                    color = (0, 255, 0)
                cv2.putText(frame_small, pred_display, (x_label, y_label), font, font_scale, color, thickness)
                if pred_display != "none":
                    cv2.putText(frame_small, f"{conf_display:.0%}", (x_label + tw + 10, y_label), font, 0.6, color, 2)

                if seq_topk_debug:
                    yk = 58
                    cv2.putText(
                        frame_small,
                        "seq top-K (raw)",
                        (8, yk),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (180, 220, 255),
                        1,
                        cv2.LINE_AA,
                    )
                    yk += 16
                    for name, pv in seq_topk_debug:
                        cv2.putText(
                            frame_small,
                            f"{name} {pv:.0%}",
                            (8, yk),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (200, 200, 255),
                            1,
                            cv2.LINE_AA,
                        )
                        yk += 18

                def _get_lm_xy(lm):
                    if hasattr(lm, "x"):
                        return (lm.x, lm.y)
                    return (lm[0], lm[1])

                def _lm_to_frame(lm):
                    """MediaPipe ì¢Œí‘œ(letterbox ì •ì‚¬ê°) â†’ frame_small ì¢Œí‘œë¡œ ë³€í™˜."""
                    x_norm, y_norm = _get_lm_xy(lm)
                    top = (mp_square_side - process_h) // 2
                    left = (mp_square_side - process_w) // 2
                    fx = int((x_norm * mp_square_side - left) * fsw / process_w) if process_w > 0 else 0
                    fy = int((y_norm * mp_square_side - top) * fsh / process_h) if process_h > 0 else 0
                    return (fx, fy)

                if lm:
                    fsh, fsw = frame_small.shape[:2]
                    for (i, j) in POSE_CONNECTIONS:
                        if i < len(lm) and j < len(lm):
                            a = _lm_to_frame(lm[i])
                            b = _lm_to_frame(lm[j])
                            cv2.line(frame_small, a, b, (0, 255, 100), 2)
                    for p in lm:
                        x, y = _lm_to_frame(p)
                        cv2.circle(frame_small, (x, y), 3, (0, 200, 255), -1)

                if gui_enabled:
                    try:
                        cv2.imshow("Body Hero â€” ML Pose", frame_small)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    except Exception:
                        gui_enabled = False
                        print(
                            "OpenCV highgui ì—†ìŒ â†’ í—¤ë“œë¦¬ìŠ¤ë¡œ ì „í™˜í–ˆìŠµë‹ˆë‹¤ (ì¢…ë£Œ: Ctrl+C).\n"
                            "  ì°½ì´ í•„ìš”í•˜ë©´: pip uninstall opencv-python-headless -y && pip install opencv-python"
                        )
                elapsed = time.time() - t0
                time.sleep(max(0.0, 1 / FPS_TARGET - elapsed))

        except KeyboardInterrupt:
            pass
        finally:
            if cap is not None:
                cap.release()
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            if landmarker is not None and getattr(landmarker, "close", None):
                try:
                    landmarker.close()
                except BaseException:
                    pass
            if sock is not None:
                sock.close()
    finally:
        if spawned_server is not None and spawned_server.poll() is None:
            spawned_server.terminate()
            try:
                spawned_server.wait(timeout=5.0)
            except Exception:
                try:
                    spawned_server.kill()
                except Exception:
                    pass
            print("pose_server ìžë™ ì‹œìž‘ í”„ë¡œì„¸ìŠ¤ë¥¼ ì¢…ë£Œí–ˆìŠµë‹ˆë‹¤.")
    print("ì¢…ë£Œ.")


if __name__ == "__main__":
    main()

