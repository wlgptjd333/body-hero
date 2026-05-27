"""
í¬ì¦ˆ ë°ì´í„° ìˆ˜ì§‘: ì›¹ìº  + MediaPipe â†’ ì–´ê¹¨ ë„ˆë¹„ ì •ê·œí™” â†’ 2ì´ˆ ë…¹í™” í›„ ë¼ë²¨ë³„ ì €ìž¥.

- ë²ˆí˜¸ í‚¤ ëˆ„ë¦„ â†’ 1ì´ˆ ì§€ì—°(ì† ì¹˜ìš°ëŠ” ì‹œê°„) â†’ 2ì´ˆ ë…¹í™”. (í•œ ë²ˆ ë…¹í™” = í•œ ë²ˆì˜ ë™ìž‘ë§Œ)
- ê¸°ë³¸: ë…¹í™”ëœ ëª¨ë“  í”„ë ˆìž„ì„ **ëˆ„ë¥¸ í‚¤ì™€ ë™ì¼í•œ ë¼ë²¨**ë¡œ ì €ìž¥(none/ê°€ë“œ/íŽ€ì¹˜ ê³µí†µ). í•™ìŠµ íƒ€ìž„ë¼ì¸ì´ ë‹¨ìˆœí•´ì§.
- ì˜µì…˜ `--impact-labeling`: ì˜ˆì „ ë°©ì‹ â€” none/drop ë¶„í• , íŽ€ì¹˜Â·ì–´í¼ëŠ” ìž„íŒ©íŠ¸ ì¶”ì • í›„ êµ¬ê°„ ë¼ë²¨,
  ê°€ë“œëŠ” 21í”„ë ˆìž„ ì´í›„ ì²« ê°€ë“œ ìžì„¸ë¶€í„° guard(ê·¸ ì „ì€ none).

ì‹¤í–‰: cd tools â†’ python collect_pose_data.py [--impact-labeling] [--drop-frames 4] [--camera-index 1] [--camera-backend dshow]
í‚¤: 0=none, 1=guard, 2=punch_l, 3=punch_r, 4=upper_l, 5=upper_r, 6=squat, Q=ì¢…ë£Œ ë° ì €ìž¥
(ê¸°ë³¸) ê° ë…¹í™”Â·ë°±ìŠ¤íŽ˜ì´ìŠ¤ ì§í›„ pose_data.json + pose_recordings_meta.json ìžë™ ì €ìž¥ â€” Q ì „ í¬ëž˜ì‹œì—ë„ ë””ìŠ¤í¬ì™€ ë™ê¸°í™”.
10ê°œ ì´ìƒ ë™ìž‘ ì‹œ: --key-map key_map.json ì‚¬ìš©.
"""
import os
import json
import time
import argparse

os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "pose_data.json")


def flush_pose_to_disk(data_path: str, meta_path: str, data: list, recordings_meta: list) -> tuple:
    """
    pose_data + ë©”íƒ€ë¥¼ í•œ ì„¸íŠ¸ë¡œ ì €ìž¥.
    1) ë‘ íŒŒì¼ ëª¨ë‘ .tmp ì— ì“´ ë’¤ 2) pose_data.json êµì²´ 3) ë©”íƒ€ êµì²´.
    (ë©”íƒ€ë¥¼ ë¨¼ì € êµì²´í•˜ë©´ ë°ì´í„°ë³´ë‹¤ ë©”íƒ€ë§Œ ê¸¸ì–´ì§€ëŠ” ë¶ˆì¼ì¹˜ê°€ ìƒê¸°ê¸° ì‰¬ì›Œ data ë¨¼ì €.)
    ì„±ê³µ ì‹œ (True, ""), ì‹¤íŒ¨ ì‹œ (False, ì—ëŸ¬ë¬¸ìžì—´).
    """
    d_tmp = data_path + ".tmp"
    m_tmp = meta_path + ".tmp"
    try:
        with open(d_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(m_tmp, "w", encoding="utf-8") as f:
            json.dump({"recordings": recordings_meta}, f, ensure_ascii=False, indent=2)
        os.replace(d_tmp, data_path)
        os.replace(m_tmp, meta_path)
        return True, ""
    except Exception as e:
        for p in (d_tmp, m_tmp):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return False, str(e)

# ë¼ë²¨ ë§¤í•‘ (í‚¤ â†’ ì•¡ì…˜). 0=none, 1=guard, 2=punch_l, 3=punch_r, 4=upper_l, 5=upper_r, 6=squat
LABELS = {
    ord("0"): "none",
    ord("1"): "guard",
    ord("2"): "punch_l",
    ord("3"): "punch_r",
    ord("4"): "upper_l",
    ord("5"): "upper_r",
    ord("6"): "squat",
}

BASE_RECORD_FPS = 30
BASE_CHUNK_FRAMES = 60  # 2ì´ˆ * 30fps â€” ë¶„í• /í˜¸í™˜ ë‹¨ìœ„
MS_PER_FRAME = 1000 // BASE_RECORD_FPS  # MediaPipe detect_for_videoëŠ” íƒ€ìž„ìŠ¤íƒ¬í”„ê°€ í•­ìƒ ì¦ê°€í•´ì•¼ í•¨
DELAY_AFTER_KEY_SEC = 1.0   # í‚¤ ëˆ„ë¥¸ ë’¤ ì´ ì‹œê°„ë§Œí¼ ì§€ì—° í›„ ë…¹í™” ì‹œìž‘ (ìžì„¸ ë§ê°€ì§ ë°©ì§€)
IMPACT_WINDOW = 3           # ìž„íŒ©íŠ¸ë¡œ ì¸ì •í•  í”„ë ˆìž„ ìˆ˜ (ì¤‘ì•™ Â±1 = 3í”„ë ˆìž„)
HOLD_FRAMES = 5             # ìž„íŒ©íŠ¸ ì§í›„ ìœ ì§€ êµ¬ê°„ (í•™ìŠµ í¬í•¨)
WINDUP_DROP_FRAMES = 4      # ìž„íŒ©íŠ¸ ì „ ìœˆë“œì—… drop (í•™ìŠµ ì œì™¸)
RECOVERY_DROP_FRAMES = 4    # ìœ ì§€ ì§í›„ íšŒìˆ˜ drop (í•™ìŠµ ì œì™¸), ê·¸ ë‹¤ìŒì€ none
LABEL_DROP = "drop"         # í•™ìŠµ ì‹œ ì œì™¸í•  ë¼ë²¨ (ëª¨í˜¸ êµ¬ê°„)


def _recording_counts_from_data(data, recordings_meta=None):
    """
    ë™ìž‘ë³„ ë…¹í™” íšŸìˆ˜. recordings_metaê°€ ìžˆìœ¼ë©´ íŽ€ì¹˜ë¥˜ëŠ” 'ëˆ„ë¥¸ í‚¤' ê¸°ì¤€ìœ¼ë¡œ ì…ˆ(ëŠ¦ê²Œ íŽ€ì¹˜í•´ë„ punch_lë¡œ ì§‘ê³„).
    ë‚˜ë¨¸ì§€(none/ê°€ë“œ) êµ¬ê°„ì€ 60í”„ë ˆìž„ ë‹¨ìœ„ë¡œ ë‹¤ìˆ˜ ë¼ë²¨ë¡œ ì§‘ê³„.
    """
    from collections import Counter
    counts = {}
    meta_starts = set()
    if recordings_meta:
        for rec in recordings_meta:
            label = rec.get("label")
            if label:
                counts[label] = counts.get(label, 0) + 1
            meta_starts.add(rec.get("start_index", -1))
    for i in range(0, len(data), BASE_CHUNK_FRAMES):
        if i in meta_starts:
            continue
        chunk = data[i : i + BASE_CHUNK_FRAMES]
        if not chunk:
            break
        labels = [x.get("label") for x in chunk]
        c = Counter(l for l in labels if l and l != LABEL_DROP)
        label = c.most_common(1)[0][0] if c else "none"
        counts[label] = counts.get(label, 0) + 1
    return counts


def _format_counts(counts):
    """ë™ìž‘ë³„ ë…¹í™” íšŸìˆ˜ ë¬¸ìžì—´ (ê°€ë…ì„±)."""
    order = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
    parts = [f"{l}:{counts[l]}" for l in order if counts.get(l)]
    for k, v in counts.items():
        if k not in order:
            parts.append(f"{k}:{v}")
    return "  ".join(parts) if parts else "(ì—†ìŒ)"


def _wrap_text_for_display(text, max_chars_per_line=42):
    """ë¬¸ìžì—´ì„ ê³µë°± ë‹¨ìœ„ë¡œ ìž˜ë¼ ìµœëŒ€ max_chars_per_line ê¸€ìžì”© ì—¬ëŸ¬ ì¤„ë¡œ. OpenCV putTextìš©."""
    if not text or len(text) <= max_chars_per_line:
        return [text] if text else []
    parts = text.split()
    lines = []
    current = []
    current_len = 0
    for p in parts:
        need = len(p) + (2 if current else 0)  # ê³µë°± 2ì¹¸
        if current and current_len + need > max_chars_per_line:
            lines.append("  ".join(current))
            current = [p]
            current_len = len(p)
        else:
            current.append(p)
            current_len = current_len + need if current_len else len(p)
    if current:
        lines.append("  ".join(current))
    return lines

# ì •ê·œí™”ëœ flat ëžœë“œë§ˆí¬ì—ì„œ ì¸ë±ìŠ¤ (33ì  * 3 = 99, ê° ëžœë“œë§ˆí¬ x,y,z ìˆœ)
# 11=ì™¼ìª½ì–´ê¹¨, 12=ì˜¤ë¥¸ìª½ì–´ê¹¨, 15=ì™¼ìª½ì†ëª©, 16=ì˜¤ë¥¸ìª½ì†ëª©
IDX = {"nose_x": 0, "nose_y": 1, "l_sh_x": 33, "l_sh_y": 34, "r_sh_x": 36, "r_sh_y": 37,
       "l_wr_x": 45, "l_wr_y": 46, "l_wr_z": 47, "r_wr_x": 48, "r_wr_y": 49, "r_wr_z": 50}

# 0~20í”„ë ˆìž„(ì¸ë±ìŠ¤ 0~20)ì€ ìž„íŒ©íŠ¸/ê°€ë“œ ì‹œìž‘ í›„ë³´ì—ì„œ ì œì™¸. 21ë²ˆì§¸ í”„ë ˆìž„(ì¸ë±ìŠ¤ 21)ë¶€í„°ë§Œ í—ˆìš©.
MIN_IMPACT_FRAME = 21

# ì–´í¼ì»·: ì†ì´ ì–¼êµ´(ì½”) ë†’ì´ ê·¼ì²˜ì— ë„ë‹¬í•œ ìˆœê°„ì„ ìž„íŒ©íŠ¸ë¡œ ì”€. ì´ë§Œí¼ ì•„ëž˜ì—¬ë„ "ì–¼êµ´ ì£¼ë³€"ìœ¼ë¡œ ì¸ì •.
UPPER_FACE_LEVEL_MARGIN = 0.06

# íŽ€ì¹˜ ìž„íŒ©íŠ¸: êµ¬ê°„ ë‚´ ì†ëª© z ìµœì†Œì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„(ì•žìœ¼ë¡œ ë»—ìŒ).
PUNCH_Z_NEAR_MARGIN = 0.02  # zê°€ ì´ë§Œí¼ ì´ìƒì´ë©´ "ì•„ì§ ë»—ê¸° ì „"ìœ¼ë¡œ ë´„

# ê°€ë“œ íŒì • (íŽ€ì¹˜Â·ì–´í¼ì™€ ë³„ë„)
GUARD_WRIST_ABOVE_SHOULDER_MARGIN = 0.06
GUARD_WRIST_X_DIFF_MAX = 0.80


def _valid_impact_indices(n: int):
    """ìž„íŒ©íŠ¸ í›„ë³´ë¡œ ì“¸ ìˆ˜ ìžˆëŠ” ì¸ë±ìŠ¤ (MIN_IMPACT_FRAME ì´ìƒ). ë¹„ë©´ ë§ˆì§€ë§‰ í”„ë ˆìž„ë§Œ ë°˜í™˜."""
    start = min(MIN_IMPACT_FRAME, n)
    r = list(range(start, n))
    return r if r else [n - 1]


def _impact_frame_punch_l(frames_flat):
    """ì™¼ì† íŽ€ì¹˜: 21í”„ë ˆìž„ ì´í›„ ì¤‘ ì™¼ì†ëª©(l_wr) z ìµœì†Œì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„."""
    if not frames_flat:
        return 0
    n = len(frames_flat)
    zs = [f[IDX["l_wr_z"]] for f in frames_flat]
    indices = list(_valid_impact_indices(n))
    min_z = min(zs[i] for i in indices)
    for i in indices:
        if zs[i] <= min_z + PUNCH_Z_NEAR_MARGIN:
            return i
    return min(indices, key=lambda i: zs[i])


def _impact_frame_punch_r(frames_flat):
    """ì˜¤ë¥¸ì† íŽ€ì¹˜: 21í”„ë ˆìž„ ì´í›„ ì¤‘ ì˜¤ë¥¸ì†ëª©(r_wr) z ìµœì†Œì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„."""
    if not frames_flat:
        return 0
    n = len(frames_flat)
    zs = [f[IDX["r_wr_z"]] for f in frames_flat]
    indices = list(_valid_impact_indices(n))
    min_z = min(zs[i] for i in indices)
    for i in indices:
        if zs[i] <= min_z + PUNCH_Z_NEAR_MARGIN:
            return i
    return min(indices, key=lambda i: zs[i])


def _impact_frame_upper_l(frames_flat):
    """ì™¼ì† ì–´í¼: 21í”„ë ˆìž„ ì´í›„ ì¤‘ ì™¼ì†ì´ ì–¼êµ´(ì½”) ë†’ì´ ê·¼ì²˜ì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„."""
    if not frames_flat:
        return 0
    n = len(frames_flat)
    indices = list(_valid_impact_indices(n))
    for i in indices:
        nose_y = frames_flat[i][IDX["nose_y"]]
        wr_y = frames_flat[i][IDX["l_wr_y"]]
        if wr_y <= nose_y + UPPER_FACE_LEVEL_MARGIN:
            return i
    # ë„ë‹¬í•œ í”„ë ˆìž„ì´ ì—†ìœ¼ë©´ ê¸°ì¡´ì²˜ëŸ¼ ê°€ìž¥ ìœ„(y ìµœì†Œ)ì¸ í”„ë ˆìž„
    return min(indices, key=lambda i: frames_flat[i][IDX["l_wr_y"]])


def _impact_frame_upper_r(frames_flat):
    """ì˜¤ë¥¸ì† ì–´í¼: 21í”„ë ˆìž„ ì´í›„ ì¤‘ ì˜¤ë¥¸ì†ì´ ì–¼êµ´(ì½”) ë†’ì´ ê·¼ì²˜ì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„."""
    if not frames_flat:
        return 0
    n = len(frames_flat)
    indices = list(_valid_impact_indices(n))
    for i in indices:
        nose_y = frames_flat[i][IDX["nose_y"]]
        wr_y = frames_flat[i][IDX["r_wr_y"]]
        if wr_y <= nose_y + UPPER_FACE_LEVEL_MARGIN:
            return i
    return min(indices, key=lambda i: frames_flat[i][IDX["r_wr_y"]])


def _is_guard_pose(flat):
    """ì •ê·œí™”ëœ ëžœë“œë§ˆí¬ 1í”„ë ˆìž„ì´ 'ê°€ë“œ ìžì„¸'(ì–‘ì† ì˜¬ë¦¬ê³  ê°€ê¹Œì´)ì¸ì§€ íŒë³„.
    ì–¼êµ´ì„ ê°€ë¦¬ë©´ ì½”ê°€ í”ë“¤ë¦¬ë¯€ë¡œ, ë†’ì´ ê¸°ì¤€ì„ ì–´ê¹¨ì„ ìœ¼ë¡œ í•¨."""
    sh_y = (flat[IDX["l_sh_y"]] + flat[IDX["r_sh_y"]]) * 0.5  # ì–´ê¹¨ ì¤‘ì‹¬ ë†’ì´
    l_wr_y, r_wr_y = flat[IDX["l_wr_y"]], flat[IDX["r_wr_y"]]
    l_wr_x, r_wr_x = flat[IDX["l_wr_x"]], flat[IDX["r_wr_x"]]
    # ì–‘ì†ì´ ì–´ê¹¨ì„ ë³´ë‹¤ ìœ„(ë˜ëŠ” ë¹„ìŠ·) â†’ ì–¼êµ´ ê°€ë ¤ë„ ì•ˆì •
    both_high = (l_wr_y < sh_y + GUARD_WRIST_ABOVE_SHOULDER_MARGIN and
                 r_wr_y < sh_y + GUARD_WRIST_ABOVE_SHOULDER_MARGIN)
    # ì–‘ì†ì´ ê°€ê¹Œì´ ëª¨ì—¬ ìžˆìŒ
    both_close = abs(l_wr_x - r_wr_x) < GUARD_WRIST_X_DIFF_MAX
    return both_high and both_close


def _label_recorded_frames(label, frames_flat, hold_frames=None, windup_drop_frames=None, recovery_drop_frames=None, hold_until_end=False):
    """
    ë…¹í™”ëœ 60í”„ë ˆìž„ì— ë¼ë²¨ ë¶€ì—¬. ìž„íŒ©íŠ¸/ê°€ë“œ ì‹œìž‘ì€ 21í”„ë ˆìž„(ì¸ë±ìŠ¤ 21) ì´í›„ì—ì„œë§Œ ì¸ì •.
    - none: ì „ë¶€ none.
    - guard: 21í”„ë ˆìž„ ì´í›„ ì²« _is_guard_pose í”„ë ˆìž„ë¶€í„° ëê¹Œì§€ guard.
    - íŽ€ì¹˜(punch_l/r): 21í”„ë ˆìž„ ì´í›„ ì†ëª© z ìµœì†Œ(ì•žìœ¼ë¡œ ë»—ìŒ) = ìž„íŒ©íŠ¸.
    - ì–´í¼: 21í”„ë ˆìž„ ì´í›„ ì¤‘ í•´ë‹¹ ì†ì´ ì–¼êµ´(ì½”) ë†’ì´ ê·¼ì²˜ì— ì²˜ìŒ ë„ë‹¬í•œ í”„ë ˆìž„ = ìž„íŒ©íŠ¸.
    ìœˆë“œì—…=drop, ìž„íŒ©íŠ¸ ì „í›„ 3í”„ë ˆìž„+ëê¹Œì§€=í•´ë‹¹ ë™ìž‘. hold_until_end=Trueë©´ ëê¹Œì§€ ë™ìž‘.
    """
    if not frames_flat:
        return [], None
    hf = hold_frames if hold_frames is not None else HOLD_FRAMES
    wdf = windup_drop_frames if windup_drop_frames is not None else WINDUP_DROP_FRAMES
    rdf = recovery_drop_frames if recovery_drop_frames is not None else RECOVERY_DROP_FRAMES
    n = len(frames_flat)
    if label == "none":
        return [{"label": "none", "landmarks": flat} for flat in frames_flat], None
    # ê°€ë“œ: 21í”„ë ˆìž„ ì´í›„ì—ì„œë§Œ ê°€ë“œ ì‹œìž‘ íƒìƒ‰. í•œ ë²ˆ ì¸ì‹ë˜ë©´ ê·¸ í”„ë ˆìž„ë¶€í„° ëê¹Œì§€ ì „ë¶€ guard.
    if label == "guard":
        guard_start = None
        for i, flat in enumerate(frames_flat):
            if i < MIN_IMPACT_FRAME:
                continue
            if _is_guard_pose(flat):
                guard_start = i
                break
        if guard_start is None:
            out = [{"label": "none", "landmarks": flat} for flat in frames_flat]
            return out, None
        out = []
        for i, flat in enumerate(frames_flat):
            out.append({"label": "guard" if i >= guard_start else "none", "landmarks": flat})
        return out, guard_start

    if label == "punch_l":
        idx = _impact_frame_punch_l(frames_flat)
    elif label == "punch_r":
        idx = _impact_frame_punch_r(frames_flat)
    elif label == "upper_l":
        idx = _impact_frame_upper_l(frames_flat)
    elif label == "upper_r":
        idx = _impact_frame_upper_r(frames_flat)
    else:
        return [{"label": "none", "landmarks": flat} for flat in frames_flat], None

    half = IMPACT_WINDOW // 2
    action_low = max(0, idx - half)
    if hold_until_end:
        action_high = n  # ìž„íŒ©íŠ¸ ì´í›„ ë‚¨ì€ í”„ë ˆìž„ ì „ë¶€ í•´ë‹¹ ë™ìž‘
        rdf = 0
    else:
        action_high = min(n, idx + half + 1 + hf)
    recovery_end = min(n, action_high + rdf)
    windup_start = max(0, idx - wdf)
    out = []
    for i, flat in enumerate(frames_flat):
        if action_low <= i < action_high:
            out.append({"label": label, "landmarks": flat})
        elif windup_start <= i < action_low:
            out.append({"label": LABEL_DROP, "landmarks": flat})
        elif action_high <= i < recovery_end:
            out.append({"label": LABEL_DROP, "landmarks": flat})
        else:
            out.append({"label": "none", "landmarks": flat})
    return out, idx


def _label_recorded_frames_uniform(label: str, frames_flat: list) -> tuple:
    """ë…¹í™” Ní”„ë ˆìž„ ì „ë¶€ë¥¼ ëˆ„ë¥¸ í‚¤(label)ë¡œ í†µì¼. ë©”íƒ€ì—ëŠ” impact_idxë¥¼ ë„£ì§€ ì•ŠìŒ(í•™ìŠµì´ ì „ êµ¬ê°„ ì‚¬ìš©)."""
    if not frames_flat:
        return [], None
    out = [{"label": label, "landmarks": flat} for flat in frames_flat]
    return out, None


try:
    import cv2
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core import image as mp_core_image
except ImportError:
    print("pip install mediapipe opencv-python")
    raise SystemExit(1)

from pose_normalize import normalize_landmarks_flat
from cv_capture import open_cv_video_capture

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
    print("Pose Landmarker ëª¨ë¸ ë‹¤ìš´ë¡œë“œ ì¤‘...")
    import urllib.request
    urls = [model_url]
    if fallback_url:
        urls.append(fallback_url)
    for url in urls:
        try:
            urllib.request.urlretrieve(url, model_path)
            print("ë‹¤ìš´ë¡œë“œ ì™„ë£Œ:", model_path)
            return
        except Exception as e:
            print("  ì‹œë„ ì‹¤íŒ¨:", url[:50], "...", e)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(
        description="í¬ì¦ˆ ë°ì´í„° ìˆ˜ì§‘ (ê¸°ì¡´ ë°ì´í„° ì´ì–´ì„œ ì €ìž¥). ê¸°ë³¸ì€ 60í”„ë ˆìž„ ì „ë¶€ ëˆ„ë¥¸ í‚¤ ë¼ë²¨."
    )
    parser.add_argument(
        "--impact-labeling",
        action="store_true",
        help="ìž„íŒ©íŠ¸/none/drop ë¶„í•  ë¼ë²¨(êµ¬ ë°©ì‹). ê¸°ë³¸ì€ ë…¹í™” ì „ í”„ë ˆìž„ì„ ëˆ„ë¥¸ í‚¤ë¡œ í†µì¼.",
    )
    parser.add_argument(
        "--drop-frames",
        type=int,
        default=4,
        help="--impact-labeling ì¼ ë•Œë§Œ ì‚¬ìš©: ìœˆë“œì—… drop í”„ë ˆìž„ ìˆ˜ (ê¸°ë³¸ 4)",
    )
    parser.add_argument("--key-map", type=str, default=None, help="í‚¤â†’ë¼ë²¨ JSON (ì˜ˆ: {\"0\":\"none\",\"1\":\"guard\",\"8\":\"extra1\",\"a\":\"extra2\"}). 10ê°œ ì´ìƒ ë™ìž‘ ì‹œ ì‚¬ìš©.")
    parser.add_argument(
        "--autosave",
        action="store_true",
        help="ë…¹í™”/ë°±ìŠ¤íŽ˜ì´ìŠ¤ ì§í›„ ë””ìŠ¤í¬ ìžë™ ì €ìž¥ (ê¸°ë³¸: ì €ìž¥ ì•ˆ í•¨, Q ì¢…ë£Œ ì‹œë§Œ ì €ìž¥)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="1íšŒ ë…¹í™” ê¸¸ì´(ì´ˆ). 2ë³´ë‹¤ í¬ë©´ 2ì´ˆ ë‹¨ìœ„ë¡œ ìžë™ë¶„í•  (ê¸°ë³¸ 20)",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        metavar="N",
        help="OpenCV ì¹´ë©”ë¼ ì¸ë±ìŠ¤ (ê¸°ë³¸ 0). USBê°€ ì•ˆ ë³´ì´ë©´ 1Â·2 ë˜ëŠ” ëª©ë¡ ìƒˆë¡œê³ ì¹¨ìœ¼ë¡œ í™•ì¸.",
    )
    parser.add_argument(
        "--camera-backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windowsì—ì„œ USB ì›¹ìº  ì¸ì‹ ë¬¸ì œ ì‹œ dshow ê¶Œìž¥ (ê²Œìž„ ì„¤ì •ê³¼ ë™ì¼ ì˜µì…˜).",
    )
    parser.add_argument(
        "--full-model",
        action="store_true",
        help="Full Pose Landmarker ì‚¬ìš© (ë” ì •í™•, ë” ëŠë¦¼). ê¸°ë³¸ì€ Lite.",
    )
    args = parser.parse_args()

    if args.duration < 2.0:
        args.duration = 2.0
        print("[ê²½ê³ ] ìµœì†Œ ë…¹í™” ê¸¸ì´ëŠ” 2ì´ˆìž…ë‹ˆë‹¤. 2ì´ˆë¡œ ì„¤ì •í•©ë‹ˆë‹¤.")
    remaining = args.duration * BASE_RECORD_FPS % BASE_CHUNK_FRAMES
    if remaining != 0:
        adjusted = round(args.duration / 2.0) * 2.0
        if adjusted < 2.0:
            adjusted = 2.0
        print(f"[ê²½ê³ ] ë…¹í™” ê¸¸ì´ëŠ” 2ì´ˆ ë‹¨ìœ„ì—¬ì•¼ í•©ë‹ˆë‹¤. {args.duration}ì´ˆ â†’ {adjusted:.0f}ì´ˆë¡œ ì¡°ì •.")
        args.duration = adjusted

    record_sec = args.duration
    record_frames = max(60, int(record_sec * BASE_RECORD_FPS))
    autosave_enabled = args.autosave

    labels_map = dict(LABELS)
    if args.key_map and os.path.isfile(args.key_map):
        try:
            with open(args.key_map, "r", encoding="utf-8") as f:
                km = json.load(f)
            for k, v in km.items():
                if isinstance(k, str) and len(k) == 1 and isinstance(v, str):
                    labels_map[ord(k)] = v
            print(f"í‚¤ë§µ ë¡œë“œ: {args.key_map} ({len(km)}ê°œ)")
        except Exception as e:
            print(f"í‚¤ë§µ ë¡œë“œ ì‹¤íŒ¨: {e}")

    use_full = args.full_model
    model_path = MODEL_PATH_FULL if use_full else MODEL_PATH_LITE
    model_url = MODEL_URL_FULL if use_full else MODEL_URL_LITE
    model_fallback = None if use_full else MODEL_URL_LITE_FALLBACK
    _download_pose_model(model_path, model_url, model_fallback)
    print(f"Pose Landmarker: {'Full' if use_full else 'Lite'}")
    BaseOptions = mp_tasks.BaseOptions
    PoseLandmarker = vision.PoseLandmarker
    PoseLandmarkerOptions = vision.PoseLandmarkerOptions
    RunningMode = vision.RunningMode
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
    )
    landmarker = PoseLandmarker.create_from_options(options)

    def make_mp_image(rgb):
        return mp_core_image.Image(image_format=mp_core_image.ImageFormat.SRGB, data=rgb.copy(order="C"))

    cap, cap_backend_label = open_cv_video_capture(args.camera_index, args.camera_backend)
    if not cap.isOpened():
        print(
            "ì›¹ìº ì„ ì—´ ìˆ˜ ì—†ìŠµë‹ˆë‹¤. --camera-index ë˜ëŠ” --camera-backend dshow ë¥¼ ë°”ê¿” ë³´ì„¸ìš”. "
            "(python list_cameras.py)"
        )
        return
    print(
        f"ì¹´ë©”ë¼: index={args.camera_index}, backend={args.camera_backend} â†’ ì‹¤ì œ: {cap_backend_label}"
    )

    out_path = os.environ.get("POSE_DATA_OUTPUT", DEFAULT_OUTPUT)
    data = []
    recordings_meta = []
    load_ok = True  # ê¸°ì¡´ íŒŒì¼ì„ ì •ìƒ ë¡œë“œí–ˆìœ¼ë©´ True
    if os.path.isfile(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                valid = True
                for item in raw:
                    if not (isinstance(item, dict) and "label" in item and "landmarks" in item):
                        valid = False
                        break
                if valid:
                    data = raw
                else:
                    load_ok = False
            else:
                load_ok = False
        except Exception:
            data = []
            load_ok = False
    meta_path = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
    # Q ì¢…ë£Œ ì‹œÂ·ìžë™ ì €ìž¥ ì‹œ ë™ì¼ ê²½ë¡œ ì‚¬ìš© (ê¸°ì¡´ íŒŒì¼ í˜•ì‹ ì˜¤ë¥˜ ì‹œ _new_session)
    save_data_path = out_path
    save_meta_path = meta_path
    if not load_ok and os.path.isfile(out_path):
        base, ext = os.path.splitext(out_path)
        save_data_path = base + "_new_session" + ext
        mb, me = os.path.splitext(meta_path)
        save_meta_path = mb + "_new_session" + me
        print(f"[ì°¸ê³ ] ê¸°ì¡´ pose_data í˜•ì‹ ì˜¤ë¥˜ â†’ ì´ë²ˆ ì„¸ì…˜ ì €ìž¥ ê²½ë¡œ: {save_data_path}")

    if os.path.isfile(meta_path) and data:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            recs = meta.get("recordings", [])
            if isinstance(recs, list) and len(recs) <= len(data):
                recordings_meta = recs
        except Exception:
            recordings_meta = []

    PUNCH_LIKE = ("punch_l", "punch_r", "upper_l", "upper_r")
    process_w, process_h = 640, 480
    cooldown = 0.0
    cooldown_sec = 0.0
    video_ts_ms = 0  # MediaPipeì— ë„˜ê¸°ëŠ” íƒ€ìž„ìŠ¤íƒ¬í”„ (ì „ì²´ì—ì„œ ë‹¨ì¡° ì¦ê°€ í•„ìˆ˜)

    counts_str = ""
    last_data_len = -1
    if data:
        counts_str = _format_counts(_recording_counts_from_data(data, recordings_meta))
        last_data_len = len(data)
        print(f"ê¸°ì¡´ ë°ì´í„° ë¶ˆëŸ¬ì˜´: {out_path} ({len(data)}í”„ë ˆìž„, ë©”íƒ€ {len(recordings_meta)}ê°œ). ì¶”ê°€ ë…¹í™” í›„ Që¡œ ì¢…ë£Œ ì‹œ ì €ìž¥ë©ë‹ˆë‹¤.")
        if autosave_enabled:
            print("  (ìžë™ ì €ìž¥ ì¼¬: ë…¹í™”Â·ë°±ìŠ¤íŽ˜ì´ìŠ¤ë§ˆë‹¤ ë””ìŠ¤í¬ì— ë°˜ì˜ â€” Q ì „ í¬ëž˜ì‹œ ëŒ€ë¹„)")
        print(f"ë™ìž‘ë³„ ë…¹í™” íšŸìˆ˜(ë©”íƒ€Â·í‚¤ ëˆ„ë¥¸ íšŒì°¨): {counts_str}")
        print(
            "  â€» ìœ„ ìˆ«ìžëŠ” pose_recordings_meta.json ì˜ ë…¹í™” íšŸìˆ˜ìž…ë‹ˆë‹¤. "
            + (
                "í”„ë ˆìž„ë§ˆë‹¤ ì°ížŒ ë¼ë²¨(ìž„íŒ©íŠ¸Â·drop)ê³¼ ë‹¤ë¥¼ ìˆ˜ ìžˆìŠµë‹ˆë‹¤. "
                if args.impact_labeling
                else "ì „ì²´ í†µì¼ ëª¨ë“œì—ì„œëŠ” í”„ë ˆìž„ ë¼ë²¨ì´ í‚¤ì™€ ê°™ì•„ íšŸìˆ˜ê°€ ë§žìŠµë‹ˆë‹¤. "
            )
            + "ë°ì´í„° ì ê²€: python report_pose_lr_balance.py / ë¼ë²¨ ìž¬ìƒì„±: python relabel_pose_with_collect.py"
        )
    if args.impact_labeling:
        print(f"í˜„ìž¬ ì„¤ì •: ë¼ë²¨=ìž„íŒ©íŠ¸ ë¶„í•  | ìœˆë“œì—… drop={args.drop_frames}í”„ë ˆìž„ (íŽ€ì¹˜/ì–´í¼ëŠ” ëê¹Œì§€ ìœ ì§€)")
    else:
        print("í˜„ìž¬ ì„¤ì •: ë¼ë²¨=60í”„ë ˆìž„ ì „ë¶€ ëˆ„ë¥¸ í‚¤ë¡œ í†µì¼ (ë©”íƒ€ì— impact_idx ì—†ìŒ â†’ í•™ìŠµì´ ì „ êµ¬ê°„ ì‚¬ìš©)")
    print("=" * 60)
    print(f"ìžë™ ì €ìž¥: {'ì¼¬' if autosave_enabled else 'ë”'} (Aí‚¤ë¡œ ì „í™˜)")
    dur_str = f"{args.duration}ì´ˆ" if args.duration > 2 else "2ì´ˆ"
    print(f"ë…¹í™” ê¸¸ì´: {dur_str} (Tí‚¤ë¡œ 2ì´ˆâ†”{dur_str} ì „í™˜, 2ì´ˆ ì´ˆê³¼ ì‹œ ìžë™ë¶„í• )")
    if args.impact_labeling:
        print("í¬ì¦ˆ ë°ì´í„° ìˆ˜ì§‘ (ìž„íŒ©íŠ¸/ê°€ë“œ êµ¬ê°„ ë¼ë²¨ë§) â€” ì¢Œìš° íŽ€ì¹˜ í†µí•©")
    else:
        print("í¬ì¦ˆ ë°ì´í„° ìˆ˜ì§‘ (ì „ í”„ë ˆìž„ ë‹¨ì¼ ë¼ë²¨) â€” ì¢Œìš° íŽ€ì¹˜ í†µí•©")
    key_line = "  " + "  ".join(f"[{chr(c)}]{labels_map[c]}" for c in sorted(labels_map.keys()))
    print(key_line)
    print()
    print("  ì‚¬ìš©ë²•: ë™ìž‘ì„ í•œ ë’¤ â†’ í•´ë‹¹ ë²ˆí˜¸ í‚¤ë¥¼ ëˆ„ë¥´ì„¸ìš”.")
    print("  â†’ 1ì´ˆ ì§€ì—° í›„ ë…¹í™” (í‚¤ ëˆ„ë¥´ëŠ” ìˆœê°„ì€ ë…¹í™”ì— ì•ˆ ë“¤ì–´ê°).")
    if args.impact_labeling:
        print("  - íŽ€ì¹˜/ì–´í¼: ë™ìž‘ì„ ë»—ì€ ì±„ë¡œ ëê¹Œì§€ ìœ ì§€í•˜ë©° ë…¹í™” (íšŒìˆ˜í•˜ì§€ ë§ˆì„¸ìš”). ìž„íŒ©íŠ¸ ì´í›„ ëê¹Œì§€ í•´ë‹¹ ë¼ë²¨, ìœˆë“œì—…ë§Œ drop.")
        print("  - none/ê°€ë“œ: í•´ë‹¹ êµ¬ê°„ë§Œ ë¼ë²¨(ê°€ë“œëŠ” ìžì„¸ ì¸ì‹ í›„ guard).")
        print("  í•œ ë²ˆ ë…¹í™” = í•œ ë²ˆì˜ ë™ìž‘ë§Œ (ì—°ì†ìœ¼ë¡œ ê°™ì€ íŽ€ì¹˜ë§Œ ë°˜ë³µí•˜ì§€ ë§ ê²ƒ).")
        print()
        print("  [íŒ] íŽ€ì¹˜/ì–´í¼: ì²˜ìŒ 1ì´ˆëŠ” ì‚´ì§ ì›€ì§ì´ë‹¤ê°€ ëŠ¦ê²Œ íŽ€ì¹˜í•˜ë©´(ì˜ˆ: ë§ˆì§€ë§‰ 20í”„ë ˆìž„ë§Œ íŽ€ì¹˜)")
        print("       none ë‹¤ì–‘ì„±â†‘, íŽ€ì¹˜ êµ¬ê°„ ê¸¸ì´ ìžì—° ì¡°ì ˆ â†’ í•™ìŠµì— ë„ì›€.")
    else:
        print("  - ê° ë…¹í™”ì˜ ëª¨ë“  í”„ë ˆìž„ì´ ëˆ„ë¥¸ í‚¤ì™€ ê°™ì€ ë¼ë²¨ë¡œ ì €ìž¥ë©ë‹ˆë‹¤ (none/ê°€ë“œ/íŽ€ì¹˜ ê³µí†µ).")
        print("  - êµ¬ ë°©ì‹(ìž„íŒ©íŠ¸Â·dropÂ·ê°€ë“œ ì‹œìž‘ íƒìƒ‰): python collect_pose_data.py --impact-labeling")
        print("  í•œ ë²ˆ ë…¹í™” = í•œ ë²ˆì˜ ë™ìž‘ë§Œ (ì—°ì†ìœ¼ë¡œ ê°™ì€ íŽ€ì¹˜ë§Œ ë°˜ë³µí•˜ì§€ ë§ ê²ƒ).")
    print()
    print("  Q: ì¢…ë£Œ(ì €ìž¥ í™•ì¸) | Backspace: ë°©ê¸ˆ ë…¹í™” 1íšŒ ì‚­ì œ | T: ë…¹í™”ê¸¸ì´ ì „í™˜ | A: ìžë™ì €ìž¥ ì „í™˜")
    print()
    print("  [ì°¸ê³ ] í•™ìŠµ ë°ì´í„° ê¶Œìž¥: ë™ìž‘ë‹¹ 40~60íšŒ ë…¹í™”(ì‹¤ìš©), 60~100íšŒ(ì¡¸ì—…ìž‘í’ˆ ê¶Œìž¥). noneì€ 30íšŒë§Œ í•´ë„ ë¨.")
    print("=" * 60)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            frame_small = cv2.resize(frame, (process_w, process_h))
            rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                break
            # Backspace: ë°©ê¸ˆ ë…¹í™”í•œ 1íšŒë¶„ ì‚­ì œ (ì €ìž¥ ì „ì´ë¯€ë¡œ Q ëˆ„ë¥´ë©´ ë°˜ì˜ë¨)
            if key == 8 and data and recordings_meta and cooldown <= 0:
                rec = recordings_meta[-1]
                start = rec["start_index"]
                count = rec.get("frame_count", record_frames)
                data = data[:start]
                recordings_meta = recordings_meta[:-1]
                print(f"  [ì‚­ì œ] ë§ˆì§€ë§‰ ë…¹í™” 1íšŒ ì œê±° ({rec.get('label', '?')}, {count}í”„ë ˆìž„). ì´ {len(data)}ê°œ.")
                last_data_len = len(data)
                cooldown = 0.0
                if autosave_enabled:
                    ok_a, err_a = flush_pose_to_disk(
                        save_data_path, save_meta_path, data, recordings_meta
                    )
                    if ok_a:
                        print("  [ìžë™ì €ìž¥] ë””ìŠ¤í¬ ë°˜ì˜ ì™„ë£Œ (ë°±ìŠ¤íŽ˜ì´ìŠ¤)")
                    else:
                        print(f"  [ìžë™ì €ìž¥ ì‹¤íŒ¨] {err_a}")
                continue
            if key == ord("t") or key == ord("T"):
                if record_sec == 2.0:
                    record_sec = args.duration
                else:
                    record_sec = 2.0
                record_frames = max(60, int(record_sec * BASE_RECORD_FPS))
                sec_str = f"{record_sec}초" if record_sec > 2 else "2초"
                print(f"  [모드 전환] 녹화 길이: {sec_str} ({record_frames}프레임)")
                continue
            if key == ord("a") or key == ord("A"):
                autosave_enabled = not autosave_enabled
                print(f"  [ìžë™ì €ìž¥] {'ì¼¬' if autosave_enabled else 'ë”'}")
                continue
            if key in labels_map and cooldown <= 0:
                label = labels_map[key]
                cooldown = cooldown_sec
                sec_str = f"{record_sec}ì´ˆ" if record_sec > 2 else "2ì´ˆ"
                print(f"  [{label}] 1ì´ˆ ì§€ì—° í›„ {sec_str} ë…¹í™” ì‹œìž‘...")

                # â”€â”€ 1ì´ˆ ì§€ì—° êµ¬ê°„: í™”ë©´ì— ê°€ë…ì„± ìžˆê²Œ í‘œì‹œ â”€â”€
                skip_record = False
                delay_start = time.time()
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        time.sleep(0.02)
                        continue
                    frame = cv2.flip(frame, 1)
                    frame_small = cv2.resize(frame, (process_w, process_h))
                    elapsed_delay = time.time() - delay_start
                    remaining_delay = max(0.0, DELAY_AFTER_KEY_SEC - elapsed_delay)
                    if remaining_delay <= 0:
                        break
                    # ì§€ì—° ì§„í–‰ë¥  ë°” (ìƒë‹¨)
                    bar_w = process_w - 40
                    fill = int(bar_w * (elapsed_delay / DELAY_AFTER_KEY_SEC))
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (60, 60, 60), -1)
                    cv2.rectangle(frame_small, (20, 18), (20 + fill, 38), (0, 200, 255), -1)
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (200, 200, 200), 2)
                    cv2.putText(frame_small, "DELAY 1 sec", (20, 52), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2)
                    cv2.putText(frame_small, "%.1f s" % remaining_delay, (process_w // 2 - 45, 90), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 255), 3)
                    cv2.imshow("Pose data collection", frame_small)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        skip_record = True
                        break
                if skip_record:
                    continue

                frames_flat = []
                start = time.time()
                recording_aborted = False
                while len(frames_flat) < record_frames:
                    ok, frame = cap.read()
                    if not ok:
                        time.sleep(0.02)
                        continue
                    frame = cv2.flip(frame, 1)
                    frame_small = cv2.resize(frame, (process_w, process_h))
                    rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
                    video_ts_ms += MS_PER_FRAME
                    result = landmarker.detect_for_video(make_mp_image(rgb), video_ts_ms)
                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        lm = result.pose_landmarks[0]
                        frames_flat.append(normalize_landmarks_flat(lm))
                    # ë…¹í™” êµ¬ê°„: í”„ë ˆìž„ ë‹¨ìœ„ ì§„í–‰ë¥ 
                    n_frame = len(frames_flat)
                    progress = n_frame / record_frames if record_frames else 0
                    bar_w = process_w - 40
                    fill = int(bar_w * progress)
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (60, 60, 60), -1)
                    cv2.rectangle(frame_small, (20, 18), (20 + fill, 38), (0, 255, 100), -1)
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (200, 200, 200), 2)
                    # 10í”„ë ˆìž„ ë‹¨ìœ„ ëˆˆê¸ˆ (20, 30, 40, 50, 60)
                    for t in range(10, record_frames, 10):
                        x = 20 + int(bar_w * t / record_frames)
                        if 20 < x < process_w - 20:
                            cv2.line(frame_small, (x, 22), (x, 34), (180, 180, 180), 1)
                    cv2.putText(frame_small, f"RECORD {int(record_sec)}s", (20, 52), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 200), 2)
                    cv2.putText(frame_small, f"{n_frame}/{record_frames}", (process_w // 2 - 45, 90), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 100), 3)
                    cv2.putText(frame_small, label, (20, 120), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2)
                    # ë…¹í™” ì¤‘ì—ë„ ë¼ˆëŒ€ í‘œì‹œ (í‰ìƒì‹œì™€ ë™ì¼)
                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        lm = result.pose_landmarks[0]
                        h, w = frame_small.shape[0], frame_small.shape[1]
                        for (i, j) in POSE_CONNECTIONS:
                            if i < len(lm) and j < len(lm):
                                a = (int(lm[i].x * w), int(lm[i].y * h))
                                b = (int(lm[j].x * w), int(lm[j].y * h))
                                cv2.line(frame_small, a, b, (0, 255, 100), 2)
                        for p in lm:
                            x, y = int(p.x * w), int(p.y * h)
                            cv2.circle(frame_small, (x, y), 4, (0, 200, 255), -1)
                    cv2.imshow("Pose data collection", frame_small)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        recording_aborted = True
                        break

                if recording_aborted:
                    continue
                # í¬ì¦ˆ ì†ì‹¤ë¡œ 60í”„ë ˆìž„ ë¯¸ë§Œì´ë©´ íŒ¨ë”©(ë§ˆì§€ë§‰ í”„ë ˆìž„ ë³µì œ) ë˜ëŠ” í•´ë‹¹ íšŒì°¨ ìŠ¤í‚µ â†’ 60í”„ë ˆìž„ ë‹¨ìœ„ ìœ ì§€
                if len(frames_flat) < record_frames:
                    shortfall = record_frames - len(frames_flat)
                    if len(frames_flat) >= 50:
                        last = frames_flat[-1] if frames_flat else None
                        while len(frames_flat) < record_frames and last is not None:
                            frames_flat.append(last)
                        print(f"  [ê²½ê³ ] í¬ì¦ˆ ì†ì‹¤ë¡œ {shortfall}í”„ë ˆìž„ ë¶€ì¡± â†’ ë§ˆì§€ë§‰ í”„ë ˆìž„ìœ¼ë¡œ íŒ¨ë”©í•˜ì—¬ {record_frames}í”„ë ˆìž„ ìœ ì§€")
                    else:
                        print(f"  [ìŠ¤í‚µ] í”„ë ˆìž„ ìˆ˜ ë¶€ì¡± ({len(frames_flat)}/{record_frames}). í•´ë‹¹ íšŒì°¨ ì €ìž¥ ì•ˆ í•¨. ë‹¤ì‹œ ë…¹í™”í•´ ì£¼ì„¸ìš”.")
                        continue
                if record_frames > BASE_CHUNK_FRAMES:
                    chunks = [frames_flat[i:i+BASE_CHUNK_FRAMES] for i in range(0, record_frames, BASE_CHUNK_FRAMES)]
                    chunks = [c for c in chunks if len(c) == BASE_CHUNK_FRAMES]
                    for ci, chunk in enumerate(chunks):
                        if args.impact_labeling:
                            labeled, impact_idx = _label_recorded_frames(
                                label, chunk,
                                windup_drop_frames=args.drop_frames,
                                hold_until_end=(label in PUNCH_LIKE),
                            )
                        else:
                            labeled, impact_idx = _label_recorded_frames_uniform(label, chunk)
                        rec_entry = {"label": label, "start_index": len(data), "frame_count": len(labeled)}
                        if args.impact_labeling:
                            if label in PUNCH_LIKE and impact_idx is not None:
                                rec_entry["impact_idx"] = impact_idx
                            elif label == "guard" and impact_idx is not None:
                                rec_entry["guard_start_idx"] = impact_idx
                        recordings_meta.append(rec_entry)
                        data.extend(labeled)
                    print(f"  â†’ {len(chunks)}íšŒ ë¶„í•  ì €ìž¥ (ì „ì²´ {len(frames_flat)}í”„ë ˆìž„ â†’ {BASE_CHUNK_FRAMES}í”„ë ˆìž„ x {len(chunks)}íšŒ) | ì´ {len(data)}ê°œ")
                else:
                    if args.impact_labeling:
                        labeled, impact_idx = _label_recorded_frames(
                            label, frames_flat,
                            windup_drop_frames=args.drop_frames,
                            hold_until_end=(label in PUNCH_LIKE),
                        )
                    else:
                        labeled, impact_idx = _label_recorded_frames_uniform(label, frames_flat)
                    rec_entry = {"label": label, "start_index": len(data), "frame_count": len(labeled)}
                    if args.impact_labeling:
                        if label in PUNCH_LIKE and impact_idx is not None:
                            rec_entry["impact_idx"] = impact_idx
                        elif label == "guard" and impact_idx is not None:
                            rec_entry["guard_start_idx"] = impact_idx
                    recordings_meta.append(rec_entry)
                    data.extend(labeled)
                    print(f"  â†’ ì €ìž¥: {len(labeled)}í”„ë ˆìž„ ì „ì²´ '{label}' í†µì¼ | ì´ {len(data)}ê°œ")
                counts_str = _format_counts(_recording_counts_from_data(data, recordings_meta))
                last_data_len = len(data)
                print(f"  ë™ìž‘ë³„ ë…¹í™” íšŸìˆ˜: {counts_str}")
                if autosave_enabled:
                    ok_a, err_a = flush_pose_to_disk(
                        save_data_path, save_meta_path, data, recordings_meta
                    )
                    if ok_a:
                        print(f"  [ìžë™ì €ìž¥] ë””ìŠ¤í¬ ë°˜ì˜ ì™„ë£Œ ({save_data_path})")
                    else:
                        print(f"  [ìžë™ì €ìž¥ ì‹¤íŒ¨] {err_a}")

            # í‰ìƒì‹œ: ë¼ì´ë¸Œ ìŠ¤ì¼ˆë ˆí†¤ë§Œ í‘œì‹œ (íƒ€ìž„ìŠ¤íƒ¬í”„ëŠ” í•­ìƒ ì¦ê°€í•´ì•¼ í•¨)
            video_ts_ms += MS_PER_FRAME
            result = landmarker.detect_for_video(make_mp_image(rgb), video_ts_ms)
            lm = None
            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm = result.pose_landmarks[0]
            if lm:
                h, w = frame_small.shape[0], frame_small.shape[1]
                for (i, j) in POSE_CONNECTIONS:
                    if i < len(lm) and j < len(lm):
                        a = (int(lm[i].x * w), int(lm[i].y * h))
                        b = (int(lm[j].x * w), int(lm[j].y * h))
                        cv2.line(frame_small, a, b, (0, 255, 100), 2)
                for p in lm:
                    x, y = int(p.x * w), int(p.y * h)
                    cv2.circle(frame_small, (x, y), 4, (0, 200, 255), -1)

            key_help = " ".join(f"{chr(c)}={labels_map[c]}" for c in sorted(labels_map.keys())[:8]) + " | Q=quit"
            key_lines = _wrap_text_for_display(key_help, max_chars_per_line=50)
            for i, line in enumerate(key_lines[:2]):
                cv2.putText(frame_small, line, (10, 20 + i * 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            mode_text = f"{int(record_sec)}s {'A' if autosave_enabled else ' '} | Collected: {len(data)}"
            cv2.putText(frame_small, mode_text, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            if data and len(data) != last_data_len:
                counts_str = _format_counts(_recording_counts_from_data(data, recordings_meta))
                last_data_len = len(data)
            if counts_str:
                count_lines = _wrap_text_for_display(counts_str, max_chars_per_line=42)
                line_height = 16
                for i, line in enumerate(count_lines):
                    y = 62 + i * line_height
                    if y >= frame_small.shape[0] - 10:
                        break
                    cv2.putText(frame_small, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 255), 1)
            cv2.imshow("Pose data collection", frame_small)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if getattr(landmarker, "close", None):
            landmarker.close()

    if data or recordings_meta:
        ok_q, err_q = flush_pose_to_disk(
            save_data_path, save_meta_path, data, recordings_meta
        )
        if ok_q:
            print(f"\nì €ìž¥ ì™„ë£Œ: {save_data_path} (ì´ {len(data)}í”„ë ˆìž„)")
            print(
                f"ë…¹í™” ë©”íƒ€: {save_meta_path} ({len(recordings_meta)}ê°œ, ìœ ì§€Â·ìž¬ë¼ë²¨ìš©)"
            )
        else:
            print(f"\nì €ìž¥ ì‹¤íŒ¨: {err_q}")
    else:
        print("\nìˆ˜ì§‘ëœ ë°ì´í„° ì—†ìŒ. ì €ìž¥í•˜ì§€ ì•ŠìŒ.")


if __name__ == "__main__":
    main()
