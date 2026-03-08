"""
포즈 데이터 수집: 웹캠 + MediaPipe → 어깨 너비 정규화 → 2초 녹화 후 라벨별 저장.

- 번호 키 누름 → 1초 지연(손 치우는 시간) → 2초 녹화. (한 번 녹화 = 한 번의 동작만)
- 없음(none): 2초 전체를 none으로 저장.
- 가드(5): 2초 안에서 "양손이 올라가 있고 가까운" 프레임만 guard, 나머지는 none (중립이 사라지지 않음).
- 잽/어퍼컷/훅: 임팩트 3프레임 + 유지 구간 = 해당 라벨, 윈드업/회수 = drop(학습 제외).
  → 유지 시에도 같은 동작으로 인식·채터링 방지.

실행: cd tools → python collect_pose_data.py [--hold-frames 5] [--drop-frames 5]
키: 0=none, 1=guard, 2=jab_l, 3=jab_r, 4=upper_l, 5=upper_r, 6=hook_l, 7=hook_r, Q=종료 및 저장
10개 이상 동작 시: --key-map key_map.json 사용 (예: {"0":"none","1":"guard",...,"8":"extra1","a":"extra2"}).
"""
import os
import json
import time
import argparse

os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "pose_data.json")

# 라벨 매핑 (키 → 액션). 0=none, 1=guard, 2=jab_l, 3=jab_r, 4=upper_l, 5=upper_r, 6=hook_l, 7=hook_r
LABELS = {
    ord("0"): "none",
    ord("1"): "guard",
    ord("2"): "jab_l",
    ord("3"): "jab_r",
    ord("4"): "upper_l",
    ord("5"): "upper_r",
    ord("6"): "hook_l",
    ord("7"): "hook_r",
}

RECORD_SEC = 2.0
RECORD_FPS = 30
RECORD_FRAMES = int(RECORD_SEC * RECORD_FPS)  # 60
MS_PER_FRAME = 1000 // RECORD_FPS  # MediaPipe detect_for_video는 타임스탬프가 항상 증가해야 함
DELAY_AFTER_KEY_SEC = 1.0   # 키 누른 뒤 이 시간만큼 지연 후 녹화 시작 (자세 망가짐 방지)
IMPACT_WINDOW = 3           # 임팩트로 인정할 프레임 수 (중앙 ±1 = 3프레임)
HOLD_FRAMES = 5             # 임팩트 직후 유지 구간 (학습 포함)
WINDUP_DROP_FRAMES = 4      # 임팩트 전 윈드업 drop (학습 제외)
RECOVERY_DROP_FRAMES = 4    # 유지 직후 회수 drop (학습 제외), 그 다음은 none
LABEL_DROP = "drop"         # 학습 시 제외할 라벨 (모호 구간)


def _recording_counts_from_data(data):
    """60프레임 단위로 한 회차씩 보고, 그 구간에서 가장 많은 비 drop 라벨을 해당 회차 라벨로 셈."""
    from collections import Counter
    counts = {}
    for i in range(0, len(data), RECORD_FRAMES):
        chunk = data[i : i + RECORD_FRAMES]
        if not chunk:
            break
        labels = [x.get("label") for x in chunk]
        c = Counter(l for l in labels if l and l != LABEL_DROP)
        label = c.most_common(1)[0][0] if c else "none"
        counts[label] = counts.get(label, 0) + 1
    return counts


def _format_counts(counts):
    """동작별 녹화 횟수 문자열 (가독성)."""
    order = ["none", "guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
    parts = [f"{l}:{counts[l]}" for l in order if counts.get(l)]
    for k, v in counts.items():
        if k not in order:
            parts.append(f"{k}:{v}")
    return "  ".join(parts) if parts else "(없음)"

# 정규화된 flat 랜드마크에서 인덱스 (33점 * 3 = 99)
# 0=코, 11=왼쪽어깨, 12=오른쪽어깨, 15=왼쪽손목, 16=오른쪽손목
IDX = {"nose_y": 1, "l_sh_x": 33, "l_sh_y": 34, "r_sh_x": 36, "r_sh_y": 37, "l_wr_x": 45, "r_wr_x": 48, "l_wr_y": 46, "r_wr_y": 49}

# 가드 판정: 양손이 코 위(또는 비슷한 높이)이고, 양손이 가까울 때만 guard
GUARD_WRIST_ABOVE_NOSE_MARGIN = 0.25   # 손목 y가 코보다 이만큼 위여도 OK (y 작을수록 위)
GUARD_WRIST_X_DIFF_MAX = 0.85          # 양 손목 x 차이가 이하면 "가까이 모음" (정규화 좌표)


def _impact_frame_jab_l(frames_flat):
    """왼손 잽: 손목이 어깨보다 앞으로 가장 나간 프레임 (x 차이 최대)"""
    if not frames_flat:
        return 0
    ext = [f[IDX["l_wr_x"]] - f[IDX["l_sh_x"]] for f in frames_flat]
    return max(range(len(ext)), key=lambda i: ext[i])


def _impact_frame_jab_r(frames_flat):
    ext = [f[IDX["r_wr_x"]] - f[IDX["r_sh_x"]] for f in frames_flat]
    return max(range(len(ext)), key=lambda i: ext[i])


def _impact_frame_upper_l(frames_flat):
    """왼손 어퍼: 손목 y가 가장 위(작은 값)인 프레임"""
    ys = [f[IDX["l_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i])


def _impact_frame_upper_r(frames_flat):
    ys = [f[IDX["r_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i])


def _impact_frame_hook_l(frames_flat):
    """왼손 훅: 손목이 어깨 높이 근처에서 몸 안쪽(오른쪽)으로 가장 들어온 프레임."""
    if not frames_flat:
        return 0
    # 어깨 높이와 비슷한 프레임 중에서 손목 x가 최대(몸 중앙/오른쪽 방향으로 가장 들어온 구간)
    candidates = [
        i for i in range(len(frames_flat))
        if abs(frames_flat[i][IDX["l_wr_y"]] - frames_flat[i][IDX["l_sh_y"]]) < 0.35
    ]
    if not candidates:
        return max(range(len(frames_flat)), key=lambda i: frames_flat[i][IDX["l_wr_x"]])
    return max(candidates, key=lambda i: frames_flat[i][IDX["l_wr_x"]])


def _impact_frame_hook_r(frames_flat):
    """오른손 훅: 손목이 어깨 높이 근처에서 몸 안쪽(왼쪽)으로 가장 들어온 프레임."""
    if not frames_flat:
        return 0
    candidates = [
        i for i in range(len(frames_flat))
        if abs(frames_flat[i][IDX["r_wr_y"]] - frames_flat[i][IDX["r_sh_y"]]) < 0.35
    ]
    if not candidates:
        return min(range(len(frames_flat)), key=lambda i: frames_flat[i][IDX["r_wr_x"]])
    return min(candidates, key=lambda i: frames_flat[i][IDX["r_wr_x"]])


def _is_guard_pose(flat):
    """정규화된 랜드마크 1프레임이 '가드 자세'(양손 올리고 가까이)인지 판별."""
    nose_y = flat[IDX["nose_y"]]
    l_wr_y, r_wr_y = flat[IDX["l_wr_y"]], flat[IDX["r_wr_y"]]
    l_wr_x, r_wr_x = flat[IDX["l_wr_x"]], flat[IDX["r_wr_x"]]
    # 양손이 코 높이보다 위(또는 비슷)
    both_high = (l_wr_y < nose_y + GUARD_WRIST_ABOVE_NOSE_MARGIN and
                 r_wr_y < nose_y + GUARD_WRIST_ABOVE_NOSE_MARGIN)
    # 양손이 가까이 모여 있음
    both_close = abs(l_wr_x - r_wr_x) < GUARD_WRIST_X_DIFF_MAX
    return both_high and both_close


def _label_recorded_frames(label, frames_flat, hold_frames=None, windup_drop_frames=None, recovery_drop_frames=None):
    """
    녹화된 60프레임에 라벨: 윈드업=drop, 임팩트3+유지=동작, 회수=drop, 그 외=none.
    """
    if not frames_flat:
        return [], None
    hf = hold_frames if hold_frames is not None else HOLD_FRAMES
    wdf = windup_drop_frames if windup_drop_frames is not None else WINDUP_DROP_FRAMES
    rdf = recovery_drop_frames if recovery_drop_frames is not None else RECOVERY_DROP_FRAMES
    n = len(frames_flat)
    if label == "none":
        return [{"label": "none", "landmarks": flat} for flat in frames_flat], None
    if label == "guard":
        out = [
            {"label": "guard" if _is_guard_pose(flat) else "none", "landmarks": flat}
            for flat in frames_flat
        ]
        return out, None

    if label == "jab_l":
        idx = _impact_frame_jab_l(frames_flat)
    elif label == "jab_r":
        idx = _impact_frame_jab_r(frames_flat)
    elif label == "upper_l":
        idx = _impact_frame_upper_l(frames_flat)
    elif label == "upper_r":
        idx = _impact_frame_upper_r(frames_flat)
    elif label == "hook_l":
        idx = _impact_frame_hook_l(frames_flat)
    elif label == "hook_r":
        idx = _impact_frame_hook_r(frames_flat)
    else:
        return [{"label": "none", "landmarks": flat} for flat in frames_flat], None

    half = IMPACT_WINDOW // 2
    action_low = max(0, idx - half)
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


try:
    import cv2
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core import image as mp_core_image
except ImportError:
    print("pip install mediapipe opencv-python")
    raise SystemExit(1)

from pose_normalize import normalize_landmarks_flat

MODEL_PATH = os.path.join(SCRIPT_DIR, "pose_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker/lite/1/pose_landmarker_lite.task"
MODEL_URL_FALLBACK = "https://huggingface.co/AndorML/Public/resolve/02ef083b988890f7444aa40afad3a2029d3b9faa/pose_landmarker_lite.task"

POSE_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19), (16, 18), (16, 20), (16, 22), (18, 20),
    (23, 24), (11, 23), (12, 24), (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30), (29, 31), (30, 32),
)


def _download_pose_model():
    if os.path.isfile(MODEL_PATH):
        return
    print("Pose Landmarker 모델 다운로드 중...")
    import urllib.request
    for url in (MODEL_URL, MODEL_URL_FALLBACK):
        try:
            urllib.request.urlretrieve(url, MODEL_PATH)
            print("다운로드 완료:", MODEL_PATH)
            return
        except Exception as e:
            print("  시도 실패:", url[:50], "...", e)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="포즈 데이터 수집 (기존 데이터 이어서 저장)")
    parser.add_argument("--hold-frames", type=int, default=5, help="임팩트 직후 유지 구간 프레임 수 (기본 5)")
    parser.add_argument("--drop-frames", type=int, default=4, help="윈드업 drop 구간 프레임 수 (기본 4)")
    parser.add_argument("--recovery-frames", type=int, default=4, help="유지 직후 회수 drop 구간 프레임 수 (기본 4)")
    parser.add_argument("--key-map", type=str, default=None, help="키→라벨 JSON (예: {\"0\":\"none\",\"1\":\"guard\",\"8\":\"extra1\",\"a\":\"extra2\"}). 10개 이상 동작 시 사용.")
    args = parser.parse_args()

    labels_map = dict(LABELS)
    if args.key_map and os.path.isfile(args.key_map):
        try:
            with open(args.key_map, "r", encoding="utf-8") as f:
                km = json.load(f)
            for k, v in km.items():
                if isinstance(k, str) and len(k) == 1 and isinstance(v, str):
                    labels_map[ord(k)] = v
            print(f"키맵 로드: {args.key_map} ({len(km)}개)")
        except Exception as e:
            print(f"키맵 로드 실패: {e}")

    _download_pose_model()
    BaseOptions = mp_tasks.BaseOptions
    PoseLandmarker = vision.PoseLandmarker
    PoseLandmarkerOptions = vision.PoseLandmarkerOptions
    RunningMode = vision.RunningMode
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
    )
    landmarker = PoseLandmarker.create_from_options(options)

    def make_mp_image(rgb):
        return mp_core_image.Image(image_format=mp_core_image.ImageFormat.SRGB, data=rgb.copy(order="C"))

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("웹캠을 열 수 없습니다.")
        return

    out_path = os.environ.get("POSE_DATA_OUTPUT", DEFAULT_OUTPUT)
    data = []
    recordings_meta = []
    load_ok = True  # 기존 파일을 정상 로드했으면 True
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
    if os.path.isfile(meta_path) and data:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            recs = meta.get("recordings", [])
            if isinstance(recs, list) and len(recs) <= len(data):
                recordings_meta = recs
        except Exception:
            recordings_meta = []

    PUNCH_LIKE = ("jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r")
    process_w, process_h = 640, 480
    cooldown = 0.0
    RECORD_COOLDOWN_SEC = 2.5  # 녹화 끝난 뒤 다음 키 입력까지 여유
    video_ts_ms = 0  # MediaPipe에 넘기는 타임스탬프 (전체에서 단조 증가 필수)

    counts_str = ""
    last_data_len = -1
    if data:
        counts_str = _format_counts(_recording_counts_from_data(data))
        last_data_len = len(data)
        print(f"기존 데이터 불러옴: {out_path} ({len(data)}프레임, 메타 {len(recordings_meta)}개). 추가 녹화 후 Q 시 이어서 저장됩니다.")
        print(f"동작별 녹화 횟수: {counts_str}")
    print(f"현재 설정: 유지={args.hold_frames}, 윈드업 drop={args.drop_frames}, 회수 drop={args.recovery_frames}")
    print("=" * 60)
    print("포즈 데이터 수집 (2초 녹화 + 임팩트/가드 구간 라벨링)")
    key_line = "  " + "  ".join(f"[{chr(c)}]{labels_map[c]}" for c in sorted(labels_map.keys()))
    print(key_line)
    print()
    print("  사용법: 동작을 한 뒤 → 해당 번호 키를 누르세요.")
    print("  → 1초 지연 후 2초 녹화 (키 누르는 순간은 녹화에 안 들어감).")
    print("  - none/가드: 해당 구간만 라벨; 잽/어퍼/훅: 임팩트+유지=라벨, 윈드업/회수=drop(학습 제외).")
    print("  한 번 녹화 = 한 번의 동작만 (연속 2번 잽 등 하지 말 것).")
    print()
    print("  Q: 종료 후 pose_data.json 저장")
    print()
    print("  [참고] 학습 데이터 권장: 동작당 40~60회 녹화(실용), 60~100회(졸업작품 권장). none은 30회만 해도 됨.")
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

            if cooldown > 0:
                cooldown -= 0.05

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                break
            if key in labels_map and cooldown <= 0:
                label = labels_map[key]
                cooldown = RECORD_COOLDOWN_SEC
                print(f"  [{label}] 1초 지연 후 2초 녹화 시작...")

                # ── 1초 지연 구간: 화면에 가독성 있게 표시 ──
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
                    # 지연 진행률 바 (상단)
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
                while len(frames_flat) < RECORD_FRAMES:
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
                    # 녹화 구간: 프레임 단위 진행률
                    n_frame = len(frames_flat)
                    progress = n_frame / RECORD_FRAMES if RECORD_FRAMES else 0
                    bar_w = process_w - 40
                    fill = int(bar_w * progress)
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (60, 60, 60), -1)
                    cv2.rectangle(frame_small, (20, 18), (20 + fill, 38), (0, 255, 100), -1)
                    cv2.rectangle(frame_small, (20, 18), (process_w - 20, 38), (200, 200, 200), 2)
                    # 10프레임 단위 눈금 (20, 30, 40, 50, 60)
                    for t in range(10, RECORD_FRAMES, 10):
                        x = 20 + int(bar_w * t / RECORD_FRAMES)
                        if 20 < x < process_w - 20:
                            cv2.line(frame_small, (x, 22), (x, 34), (180, 180, 180), 1)
                    cv2.putText(frame_small, f"RECORD {RECORD_FRAMES} frames", (20, 52), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 200), 2)
                    cv2.putText(frame_small, f"{n_frame}/{RECORD_FRAMES}", (process_w // 2 - 45, 90), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 100), 3)
                    cv2.putText(frame_small, label, (20, 120), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2)
                    # 녹화 중에도 뼈대 표시 (평상시와 동일)
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
                # 포즈 손실로 60프레임 미만이면 패딩(마지막 프레임 복제) 또는 해당 회차 스킵 → 60프레임 단위 유지
                if len(frames_flat) < RECORD_FRAMES:
                    shortfall = RECORD_FRAMES - len(frames_flat)
                    if len(frames_flat) >= 50:
                        last = frames_flat[-1] if frames_flat else None
                        while len(frames_flat) < RECORD_FRAMES and last is not None:
                            frames_flat.append(last)
                        print(f"  [경고] 포즈 손실로 {shortfall}프레임 부족 → 마지막 프레임으로 패딩하여 {RECORD_FRAMES}프레임 유지")
                    else:
                        print(f"  [스킵] 프레임 수 부족 ({len(frames_flat)}/{RECORD_FRAMES}). 해당 회차 저장 안 함. 다시 녹화해 주세요.")
                        continue
                labeled, impact_idx = _label_recorded_frames(
                    label, frames_flat,
                    hold_frames=args.hold_frames,
                    windup_drop_frames=args.drop_frames,
                    recovery_drop_frames=args.recovery_frames,
                )
                if label in PUNCH_LIKE and impact_idx is not None:
                    recordings_meta.append({
                        "label": label,
                        "impact_idx": impact_idx,
                        "start_index": len(data),
                        "frame_count": len(labeled),
                    })
                data.extend(labeled)
                action_count = sum(1 for x in labeled if x["label"] == label)
                drop_count = sum(1 for x in labeled if x.get("label") == LABEL_DROP)
                if label in PUNCH_LIKE and impact_idx is not None:
                    end_action = min(impact_idx + 2 + args.hold_frames, len(labeled))
                    print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                    print(f"     임팩트 추정: 프레임 {impact_idx + 1}/{len(labeled)}  (동작 구간: {impact_idx + 1}~{end_action} = 임팩트+유지)")
                else:
                    print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                counts_str = _format_counts(_recording_counts_from_data(data))
                last_data_len = len(data)
                print(f"  동작별 녹화 횟수: {counts_str}")

            # 평상시: 라이브 스켈레톤만 표시 (타임스탬프는 항상 증가해야 함)
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

            key_help = " ".join(f"{chr(c)}={labels_map[c]}" for c in sorted(labels_map.keys())[:12])
            if len(key_help) > 55:
                key_help = key_help[:52] + "..."
            cv2.putText(frame_small, key_help + " | Q=quit", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.putText(frame_small, f"Collected: {len(data)}", (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            if data and len(data) != last_data_len:
                counts_str = _format_counts(_recording_counts_from_data(data))
                last_data_len = len(data)
            if counts_str:
                line2 = counts_str if len(counts_str) <= 55 else counts_str[:52] + "..."
                cv2.putText(frame_small, line2, (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 255), 1)
            cv2.imshow("Pose data collection", frame_small)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if getattr(landmarker, "close", None):
            landmarker.close()

    if data:
        # 기존 파일이 있는데 로드에 실패했으면 덮어쓰지 않고 별도 파일로 저장
        if not load_ok and os.path.isfile(out_path):
            base, ext = os.path.splitext(out_path)
            save_path = base + "_new_session" + ext
            print(f"\n기존 파일 형식 오류로 불러오지 못했습니다. 이번 세션만 별도 저장: {save_path}")
        else:
            save_path = out_path
        tmp_path = save_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, save_path)
            print(f"\n저장 완료: {save_path} (총 {len(data)}개)")
        except Exception as e:
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            print(f"\n저장 실패: {e}")
        if recordings_meta:
            if save_path != out_path:
                base, ext = os.path.splitext(meta_path)
                meta_save_path = base + "_new_session" + ext
            else:
                meta_save_path = meta_path
            meta_tmp = meta_save_path + ".tmp"
            try:
                with open(meta_tmp, "w", encoding="utf-8") as f:
                    json.dump({"recordings": recordings_meta}, f, ensure_ascii=False, indent=2)
                os.replace(meta_tmp, meta_save_path)
                print(f"녹화 메타: {meta_save_path} ({len(recordings_meta)}개, 유지 N 변경 시 재라벨용)")
            except Exception as e:
                if os.path.isfile(meta_tmp):
                    try:
                        os.remove(meta_tmp)
                    except Exception:
                        pass
                print(f"메타 저장 실패: {e}")
    else:
        print("\n수집된 데이터 없음. 저장하지 않음.")


if __name__ == "__main__":
    main()
