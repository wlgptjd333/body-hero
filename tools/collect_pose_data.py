"""
포즈 데이터 수집: 웹캠 + MediaPipe → 어깨 너비 정규화 → 2초 녹화 후 라벨별 저장.

- 번호 키 누름 → 1초 지연(손 치우는 시간) → 2초 녹화. (한 번 녹화 = 한 번의 동작만)
- 기본: 녹화된 모든 프레임을 **누른 키와 동일한 라벨**로 저장(none/가드/펀치 공통). 학습 타임라인이 단순해짐.
- 옵션 `--impact-labeling`: 예전 방식 — none/drop 분할, 펀치·어퍼는 임팩트 추정 후 구간 라벨,
  가드는 21프레임 이후 첫 가드 자세부터 guard(그 전은 none).

실행: cd tools → python collect_pose_data.py [--impact-labeling] [--drop-frames 4] [--camera-index 1] [--camera-backend dshow]
키: 0=none, 1=guard, 2=punch_l, 3=punch_r, 4=upper_l, 5=upper_r, 6=squat, Q=종료 및 저장
(기본) 각 녹화·백스페이스 직후 pose_data.json + pose_recordings_meta.json 자동 저장 — Q 전 크래시에도 디스크와 동기화.
10개 이상 동작 시: --key-map key_map.json 사용.
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
    pose_data + 메타를 한 세트로 저장.
    1) 두 파일 모두 .tmp 에 쓴 뒤 2) pose_data.json 교체 3) 메타 교체.
    (메타를 먼저 교체하면 데이터보다 메타만 길어지는 불일치가 생기기 쉬워 data 먼저.)
    성공 시 (True, ""), 실패 시 (False, 에러문자열).
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

# 라벨 매핑 (키 → 액션). 0=none, 1=guard, 2=punch_l, 3=punch_r, 4=upper_l, 5=upper_r, 6=squat
LABELS = {
    ord("0"): "none",
    ord("1"): "guard",
    ord("2"): "punch_l",
    ord("3"): "punch_r",
    ord("4"): "upper_l",
    ord("5"): "upper_r",
    ord("6"): "squat",
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


def _recording_counts_from_data(data, recordings_meta=None):
    """
    동작별 녹화 횟수. recordings_meta가 있으면 펀치류는 '누른 키' 기준으로 셈(늦게 펀치해도 punch_l로 집계).
    나머지(none/가드) 구간은 60프레임 단위로 다수 라벨로 집계.
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
    for i in range(0, len(data), RECORD_FRAMES):
        if i in meta_starts:
            continue
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
    order = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
    parts = [f"{l}:{counts[l]}" for l in order if counts.get(l)]
    for k, v in counts.items():
        if k not in order:
            parts.append(f"{k}:{v}")
    return "  ".join(parts) if parts else "(없음)"


def _wrap_text_for_display(text, max_chars_per_line=42):
    """문자열을 공백 단위로 잘라 최대 max_chars_per_line 글자씩 여러 줄로. OpenCV putText용."""
    if not text or len(text) <= max_chars_per_line:
        return [text] if text else []
    parts = text.split()
    lines = []
    current = []
    current_len = 0
    for p in parts:
        need = len(p) + (2 if current else 0)  # 공백 2칸
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

# 정규화된 flat 랜드마크에서 인덱스 (33점 * 3 = 99, 각 랜드마크 x,y,z 순)
# 11=왼쪽어깨, 12=오른쪽어깨, 15=왼쪽손목, 16=오른쪽손목
IDX = {"nose_x": 0, "nose_y": 1, "l_sh_x": 33, "l_sh_y": 34, "r_sh_x": 36, "r_sh_y": 37,
       "l_wr_x": 45, "l_wr_y": 46, "l_wr_z": 47, "r_wr_x": 48, "r_wr_y": 49, "r_wr_z": 50}

# 0~20프레임(인덱스 0~20)은 임팩트/가드 시작 후보에서 제외. 21번째 프레임(인덱스 21)부터만 허용.
MIN_IMPACT_FRAME = 21

# 어퍼컷: 손이 얼굴(코) 높이 근처에 도달한 순간을 임팩트로 씀. 이만큼 아래여도 "얼굴 주변"으로 인정.
UPPER_FACE_LEVEL_MARGIN = 0.06

# 펀치 임팩트: 구간 내 손목 z 최소에 처음 도달한 프레임(앞으로 뻗음).
PUNCH_Z_NEAR_MARGIN = 0.02  # z가 이만큼 이상이면 "아직 뻗기 전"으로 봄

# 가드 판정 (펀치·어퍼와 별도)
GUARD_WRIST_ABOVE_SHOULDER_MARGIN = 0.06
GUARD_WRIST_X_DIFF_MAX = 0.80


def _valid_impact_indices(n: int):
    """임팩트 후보로 쓸 수 있는 인덱스 (MIN_IMPACT_FRAME 이상). 비면 마지막 프레임만 반환."""
    start = min(MIN_IMPACT_FRAME, n)
    r = list(range(start, n))
    return r if r else [n - 1]


def _impact_frame_punch_l(frames_flat):
    """왼손 펀치: 21프레임 이후 중 왼손목(l_wr) z 최소에 처음 도달한 프레임."""
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
    """오른손 펀치: 21프레임 이후 중 오른손목(r_wr) z 최소에 처음 도달한 프레임."""
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
    """왼손 어퍼: 21프레임 이후 중 왼손이 얼굴(코) 높이 근처에 처음 도달한 프레임."""
    if not frames_flat:
        return 0
    n = len(frames_flat)
    indices = list(_valid_impact_indices(n))
    for i in indices:
        nose_y = frames_flat[i][IDX["nose_y"]]
        wr_y = frames_flat[i][IDX["l_wr_y"]]
        if wr_y <= nose_y + UPPER_FACE_LEVEL_MARGIN:
            return i
    # 도달한 프레임이 없으면 기존처럼 가장 위(y 최소)인 프레임
    return min(indices, key=lambda i: frames_flat[i][IDX["l_wr_y"]])


def _impact_frame_upper_r(frames_flat):
    """오른손 어퍼: 21프레임 이후 중 오른손이 얼굴(코) 높이 근처에 처음 도달한 프레임."""
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
    """정규화된 랜드마크 1프레임이 '가드 자세'(양손 올리고 가까이)인지 판별.
    얼굴을 가리면 코가 흔들리므로, 높이 기준을 어깨선으로 함."""
    sh_y = (flat[IDX["l_sh_y"]] + flat[IDX["r_sh_y"]]) * 0.5  # 어깨 중심 높이
    l_wr_y, r_wr_y = flat[IDX["l_wr_y"]], flat[IDX["r_wr_y"]]
    l_wr_x, r_wr_x = flat[IDX["l_wr_x"]], flat[IDX["r_wr_x"]]
    # 양손이 어깨선보다 위(또는 비슷) → 얼굴 가려도 안정
    both_high = (l_wr_y < sh_y + GUARD_WRIST_ABOVE_SHOULDER_MARGIN and
                 r_wr_y < sh_y + GUARD_WRIST_ABOVE_SHOULDER_MARGIN)
    # 양손이 가까이 모여 있음
    both_close = abs(l_wr_x - r_wr_x) < GUARD_WRIST_X_DIFF_MAX
    return both_high and both_close


def _label_recorded_frames(label, frames_flat, hold_frames=None, windup_drop_frames=None, recovery_drop_frames=None, hold_until_end=False):
    """
    녹화된 60프레임에 라벨 부여. 임팩트/가드 시작은 21프레임(인덱스 21) 이후에서만 인정.
    - none: 전부 none.
    - guard: 21프레임 이후 첫 _is_guard_pose 프레임부터 끝까지 guard.
    - 펀치(punch_l/r): 21프레임 이후 손목 z 최소(앞으로 뻗음) = 임팩트.
    - 어퍼: 21프레임 이후 중 해당 손이 얼굴(코) 높이 근처에 처음 도달한 프레임 = 임팩트.
    윈드업=drop, 임팩트 전후 3프레임+끝까지=해당 동작. hold_until_end=True면 끝까지 동작.
    """
    if not frames_flat:
        return [], None
    hf = hold_frames if hold_frames is not None else HOLD_FRAMES
    wdf = windup_drop_frames if windup_drop_frames is not None else WINDUP_DROP_FRAMES
    rdf = recovery_drop_frames if recovery_drop_frames is not None else RECOVERY_DROP_FRAMES
    n = len(frames_flat)
    if label == "none":
        return [{"label": "none", "landmarks": flat} for flat in frames_flat], None
    # 가드: 21프레임 이후에서만 가드 시작 탐색. 한 번 인식되면 그 프레임부터 끝까지 전부 guard.
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
        action_high = n  # 임팩트 이후 남은 프레임 전부 해당 동작
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
    """녹화 N프레임 전부를 누른 키(label)로 통일. 메타에는 impact_idx를 넣지 않음(학습이 전 구간 사용)."""
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
    parser = argparse.ArgumentParser(
        description="포즈 데이터 수집 (기존 데이터 이어서 저장). 기본은 60프레임 전부 누른 키 라벨."
    )
    parser.add_argument(
        "--impact-labeling",
        action="store_true",
        help="임팩트/none/drop 분할 라벨(구 방식). 기본은 녹화 전 프레임을 누른 키로 통일.",
    )
    parser.add_argument(
        "--drop-frames",
        type=int,
        default=4,
        help="--impact-labeling 일 때만 사용: 윈드업 drop 프레임 수 (기본 4)",
    )
    parser.add_argument("--key-map", type=str, default=None, help="키→라벨 JSON (예: {\"0\":\"none\",\"1\":\"guard\",\"8\":\"extra1\",\"a\":\"extra2\"}). 10개 이상 동작 시 사용.")
    parser.add_argument(
        "--no-autosave",
        action="store_true",
        help="녹화/백스페이스 직후 디스크 자동 저장 끔 (기본: 매 녹화·삭제 후 저장)",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        metavar="N",
        help="OpenCV 카메라 인덱스 (기본 0). USB가 안 보이면 1·2 또는 목록 새로고침으로 확인.",
    )
    parser.add_argument(
        "--camera-backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windows에서 USB 웹캠 인식 문제 시 dshow 권장 (게임 설정과 동일 옵션).",
    )
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

    cap, cap_backend_label = open_cv_video_capture(args.camera_index, args.camera_backend)
    if not cap.isOpened():
        print(
            "웹캠을 열 수 없습니다. --camera-index 또는 --camera-backend dshow 를 바꿔 보세요. "
            "(python list_cameras.py)"
        )
        return
    print(
        f"카메라: index={args.camera_index}, backend={args.camera_backend} → 실제: {cap_backend_label}"
    )

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
    # Q 종료 시·자동 저장 시 동일 경로 사용 (기존 파일 형식 오류 시 _new_session)
    save_data_path = out_path
    save_meta_path = meta_path
    if not load_ok and os.path.isfile(out_path):
        base, ext = os.path.splitext(out_path)
        save_data_path = base + "_new_session" + ext
        mb, me = os.path.splitext(meta_path)
        save_meta_path = mb + "_new_session" + me
        print(f"[참고] 기존 pose_data 형식 오류 → 이번 세션 저장 경로: {save_data_path}")

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
    RECORD_COOLDOWN_SEC = 2.5  # 녹화 끝난 뒤 다음 키 입력까지 여유
    video_ts_ms = 0  # MediaPipe에 넘기는 타임스탬프 (전체에서 단조 증가 필수)

    counts_str = ""
    last_data_len = -1
    if data:
        counts_str = _format_counts(_recording_counts_from_data(data, recordings_meta))
        last_data_len = len(data)
        print(f"기존 데이터 불러옴: {out_path} ({len(data)}프레임, 메타 {len(recordings_meta)}개). 추가 녹화 후 Q로 종료 시 저장됩니다.")
        if not args.no_autosave:
            print("  (자동 저장 켬: 녹화·백스페이스마다 디스크에 반영 — Q 전 크래시 대비)")
        print(f"동작별 녹화 횟수(메타·키 누른 회차): {counts_str}")
        print(
            "  ※ 위 숫자는 pose_recordings_meta.json 의 녹화 횟수입니다. "
            + (
                "프레임마다 찍힌 라벨(임팩트·drop)과 다를 수 있습니다. "
                if args.impact_labeling
                else "전체 통일 모드에서는 프레임 라벨이 키와 같아 횟수가 맞습니다. "
            )
            + "데이터 점검: python report_pose_lr_balance.py / 라벨 재생성: python relabel_pose_with_collect.py"
        )
    if args.impact_labeling:
        print(f"현재 설정: 라벨=임팩트 분할 | 윈드업 drop={args.drop_frames}프레임 (펀치/어퍼는 끝까지 유지)")
    else:
        print("현재 설정: 라벨=60프레임 전부 누른 키로 통일 (메타에 impact_idx 없음 → 학습이 전 구간 사용)")
    print("=" * 60)
    if not args.no_autosave:
        print(f"자동 저장: 켬 → {save_data_path} + 메타 (녹화·백스페이스마다)")
    if args.impact_labeling:
        print("포즈 데이터 수집 (2초 녹화 + 임팩트/가드 구간 라벨링) — 좌우 펀치 통합")
    else:
        print("포즈 데이터 수집 (2초 녹화 + 전 프레임 단일 라벨) — 좌우 펀치 통합")
    key_line = "  " + "  ".join(f"[{chr(c)}]{labels_map[c]}" for c in sorted(labels_map.keys()))
    print(key_line)
    print()
    print("  사용법: 동작을 한 뒤 → 해당 번호 키를 누르세요.")
    print("  → 1초 지연 후 2초 녹화 (키 누르는 순간은 녹화에 안 들어감).")
    if args.impact_labeling:
        print("  - 펀치/어퍼: 동작을 뻗은 채로 끝까지 유지하며 녹화 (회수하지 마세요). 임팩트 이후 끝까지 해당 라벨, 윈드업만 drop.")
        print("  - none/가드: 해당 구간만 라벨(가드는 자세 인식 후 guard).")
        print("  한 번 녹화 = 한 번의 동작만 (연속으로 같은 펀치만 반복하지 말 것).")
        print()
        print("  [팁] 펀치/어퍼: 처음 1초는 살짝 움직이다가 늦게 펀치하면(예: 마지막 20프레임만 펀치)")
        print("       none 다양성↑, 펀치 구간 길이 자연 조절 → 학습에 도움.")
    else:
        print("  - 각 녹화의 모든 프레임이 누른 키와 같은 라벨로 저장됩니다 (none/가드/펀치 공통).")
        print("  - 구 방식(임팩트·drop·가드 시작 탐색): python collect_pose_data.py --impact-labeling")
        print("  한 번 녹화 = 한 번의 동작만 (연속으로 같은 펀치만 반복하지 말 것).")
    print()
    print("  Q: 종료(저장 확인) | Backspace: 방금 녹화 1회 삭제" + ("" if args.no_autosave else " (자동 저장)"))
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
            # Backspace: 방금 녹화한 1회분 삭제 (저장 전이므로 Q 누르면 반영됨)
            if key == 8 and data and recordings_meta and cooldown <= 0:
                rec = recordings_meta[-1]
                start = rec["start_index"]
                count = rec.get("frame_count", RECORD_FRAMES)
                data = data[:start]
                recordings_meta = recordings_meta[:-1]
                print(f"  [삭제] 마지막 녹화 1회 제거 ({rec.get('label', '?')}, {count}프레임). 총 {len(data)}개.")
                last_data_len = len(data)
                cooldown = 1.0
                if not args.no_autosave:
                    ok_a, err_a = flush_pose_to_disk(
                        save_data_path, save_meta_path, data, recordings_meta
                    )
                    if ok_a:
                        print("  [자동저장] 디스크 반영 완료 (백스페이스)")
                    else:
                        print(f"  [자동저장 실패] {err_a}")
                continue
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
                if args.impact_labeling:
                    labeled, impact_idx = _label_recorded_frames(
                        label,
                        frames_flat,
                        windup_drop_frames=args.drop_frames,
                        hold_until_end=(label in PUNCH_LIKE),
                    )
                else:
                    labeled, impact_idx = _label_recorded_frames_uniform(label, frames_flat)
                # 모든 라벨을 메타에 넣어 '누른 횟수'로 카운트 (가드/none 포함)
                rec_entry = {"label": label, "start_index": len(data), "frame_count": len(labeled)}
                if args.impact_labeling:
                    if label in PUNCH_LIKE and impact_idx is not None:
                        rec_entry["impact_idx"] = impact_idx
                    elif label == "guard" and impact_idx is not None:
                        rec_entry["guard_start_idx"] = impact_idx
                recordings_meta.append(rec_entry)
                data.extend(labeled)
                action_count = sum(1 for x in labeled if x["label"] == label)
                drop_count = sum(1 for x in labeled if x.get("label") == LABEL_DROP)
                if args.impact_labeling:
                    if label in PUNCH_LIKE and impact_idx is not None:
                        print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                        print(f"     임팩트 추정: 프레임 {impact_idx + 1}/{len(labeled)}  (동작 구간: {impact_idx + 1}~{len(labeled)} = 임팩트~끝)")
                    elif label == "guard":
                        if impact_idx is not None:
                            sec = (impact_idx + 1) / RECORD_FPS
                            print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                            print(f"     가드 인식 시작: 프레임 {impact_idx + 1}/{len(labeled)}  ({sec:.2f}초) → 끝까지 guard 유지")
                        else:
                            print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                            print(f"     [참고] 이 회차에서 가드 자세가 한 프레임도 없어 전부 none으로 저장됨. 손을 더 올리고 모아서 다시 녹화해 보세요.")
                    else:
                        print(f"  → 저장: {len(labeled)}프레임 (그중 '{label}' {action_count}, drop {drop_count}) | 총 {len(data)}개")
                else:
                    print(f"  → 저장: {len(labeled)}프레임 전체 '{label}' 통일 | 총 {len(data)}개")
                counts_str = _format_counts(_recording_counts_from_data(data, recordings_meta))
                last_data_len = len(data)
                print(f"  동작별 녹화 횟수: {counts_str}")
                if not args.no_autosave:
                    ok_a, err_a = flush_pose_to_disk(
                        save_data_path, save_meta_path, data, recordings_meta
                    )
                    if ok_a:
                        print(f"  [자동저장] 디스크 반영 완료 ({save_data_path})")
                    else:
                        print(f"  [자동저장 실패] {err_a}")

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

            key_help = " ".join(f"{chr(c)}={labels_map[c]}" for c in sorted(labels_map.keys())[:12]) + " | Q=quit"
            key_lines = _wrap_text_for_display(key_help, max_chars_per_line=50)
            for i, line in enumerate(key_lines[:2]):
                cv2.putText(frame_small, line, (10, 20 + i * 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.putText(frame_small, f"Collected: {len(data)}", (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
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
            print(f"\n저장 완료: {save_data_path} (총 {len(data)}프레임)")
            print(
                f"녹화 메타: {save_meta_path} ({len(recordings_meta)}개, 유지·재라벨용)"
            )
        else:
            print(f"\n저장 실패: {err_q}")
    else:
        print("\n수집된 데이터 없음. 저장하지 않음.")


if __name__ == "__main__":
    main()
