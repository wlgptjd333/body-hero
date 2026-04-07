"""
웹캠 → Pose 랜드마크 → ML 추론(로컬 또는 pose_server) → Godot에 UDP로 액션 전송.

- 기본: pose_classifier_seq.keras + pose_classifier.keras(가드 폴백)를 로드해 로컬에서 추론. pose_server 불필요.
- 시퀀스 모델이 없으면 HTTP로 pose_server에 요청. 서버가 없으면 pose_server.py를 자동으로 띄움 (--no-auto-server 로 끌 수 있음).

사용 순서:
  1) 데이터 수집: python collect_pose_data.py
  2) 시퀀스 학습: python train_pose_classifier_seq.py  [가드 폴백: train_pose_classifier.py]
  3) 본 스크립트: python udp_send_webcam_ml.py
  4) Godot 실행 후 플레이
"""
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

# 로그: MediaPipe·TensorFlow가 각각 C++ 쪽 absl/oneDNN을 켜서 비슷한 영어 문구가 2번 나올 수 있음(정상).
# TF 쪽 INFO/WARN 줄이기(3=ERROR만). oneDNN 안내 1회 분량도 끔.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 4242
PREDICT_URL = "http://127.0.0.1:5000/predict"
POSE_SERVER_HEALTH_URL = "http://127.0.0.1:5000/health"
POSE_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "pose_server.py")

# 로컬 추론용 (pose_server와 동일). 시퀀스 길이는 학습한 모델과 반드시 일치해야 함.
MODEL_SEQ_PATH = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
MODEL_SINGLE_PATH = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
SEQ_LEN = 8
CLASS_NAMES = ["none", "guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
GUARD_INDEX = 1
# 시퀀스 모델: 1등 클래스 확률이 이 값 미만이면 none (높을수록 오인 감소·진짜 애매한 타는 감소)
CONFIDENCE_THRESHOLD = 0.95
GUARD_FALLBACK_THRESHOLD = 0.45
COOLDOWN_SEC = 0.45
# 어떤 펀치든 UDP 1회 보낸 뒤, 다음 펀치(잽↔잽·잽↔어퍼 등)까지 최소 대기. ML이 프레임마다 라벨이 바뀌며 연속 전송되는 것 방지
MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.48
# 가드 해제: non-guard가 이 프레임 연속이면 guard_end (ML이 잽/훅으로 잠깐 튈 때 가드가 너무 빨리 풀리지 않게 여유)
GUARD_EXIT_FRAMES = 18
FPS_TARGET = 24
# 처리 해상도: 높을수록 좌우(잽) 구분·포즈 안정에 유리, CPU 부하 증가 (렉 시 320x240 또는 --process-w/h로 낮춤)
PROCESS_W, PROCESS_H = 480, 360
# 이 프레임 수마다만 포즈+ML 실행 (1=매프레임, 2=2프레임마다). test_pose_live처럼 인식하려면 1
PROCESS_EVERY_N_FRAMES = 1
# Godot으로 액션 전송 시에만 적용: 어깨 중심이 이 구역 안에 있을 때만 전송 (화면 표시는 zone 무관)
CENTER_ZONE_X = (0.2, 0.8)  # normalized [0,1] 기준
CENTER_ZONE_Y = (0.2, 0.8)
# 잽: pred가 잽으로 연속 나온 프레임 수 (한 줄 [액션] = 전송 1회, 이 N프레임 채워야 1회 전송)
# 훅 준비 구간이 잽으로 잡히는 경우 4프레임이면 잽→훅 연속 전송되므로 1프레임 여유
JAB_CONFIRM_FRAMES = 5
# 어퍼/훅: 같은 라벨 연속 프레임 (너무 짧으면 upper_l↔upper_r 깜빡임으로 둘 다 전송됨)
OTHER_PUNCH_CONFIRM_FRAMES = 3
# 어퍼만: 준비 자세(거의 정지)에서 ML이 upper로 고정되는 것 억제 — 살짝 더 많은 프레임 필요
UPPER_PUNCH_CONFIRM_FRAMES = 5
# 정규화 랜드마크 프레임 간 평균 |Δ|가 이 값 미만이면 "정지에 가깝다"고 보고 어퍼 카운트 시작 안 함(이미 쌓인 뒤에는 피크 정지 허용)
UPPER_MOTION_MEAN_ABS_MIN = 0.0022
# ML이 어퍼/훅으로 분류한 프레임이 있으면, 이후 이 프레임 동안 잽 카운트 안 함 (값이 크면 어퍼 예측이 튈 때 잽이 안 나감)
JAB_HOLDOFF_AFTER_POWER_PRED_FRAMES = 14
# upper_l 전송 직후 upper_r(반대) 확정 무시 — 짧게만(빠른 반대손 어퍼는 허용, 회수 시 1~2프레임 깜빡임만 억제)
UPPER_LR_OPPOSITE_BLOCK_FRAMES = 15
# pred가 none에 가깝게 이 프레임 연속이면 잽 홀드오프 해제 (다시 잽 치기 가능)
NONE_STREAK_TO_CLEAR_JAB_HOLDOFF = 6
POWER_PUNCH_LABELS = ("upper_l", "upper_r", "hook_l", "hook_r")
PUNCH_LABELS = ("jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r")

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
        "OpenCV(cv2)에 VideoCapture가 없습니다. headless 제거 후 패키지가 꼬였거나 잘못된 cv2가 로드된 경우입니다.\n"
        f"  cv2 로드 경로: {getattr(cv2, '__file__', '?')}\n"
        "  (venv_ml)에서 아래를 실행한 뒤 다시 시도하세요:\n"
        "    pip uninstall opencv-python opencv-python-headless opencv-contrib-python -y\n"
        "    pip install --force-reinstall \"opencv-python>=4.9,<5\""
    )
    raise SystemExit(1)

from pose_normalize import normalize_landmarks_flat, shoulder_center_and_width

# 로컬 추론: tensorflow, numpy (모델 로드 실패 시 HTTP 폴백)
_np = None
_tf = None
_model_seq = None
_model_single = None
_use_local_inference = False

try:
    import numpy as _np
    import tensorflow as _tf
except ImportError:
    pass


def _load_local_models():
    """시퀀스 모델 필수, 단일 프레임(가드) 모델 선택. 성공 시 True. SEQ_LEN은 모델 입력(time) 차원으로 맞춤."""
    global _model_seq, _model_single, _use_local_inference, SEQ_LEN
    if _tf is None or _np is None:
        return False
    if not os.path.isfile(MODEL_SEQ_PATH):
        return False
    try:
        _model_seq = _tf.keras.models.load_model(MODEL_SEQ_PATH)
        inp = _model_seq.input_shape
        if isinstance(inp, (list, tuple)) and len(inp) >= 2 and inp[1] is not None:
            SEQ_LEN = int(inp[1])
        if os.path.isfile(MODEL_SINGLE_PATH):
            _model_single = _tf.keras.models.load_model(MODEL_SINGLE_PATH)
        _use_local_inference = True
        return True
    except Exception:
        _model_seq = None
        _model_single = None
        _use_local_inference = False
        return False


def _predict_local(sequence):
    """pose_server와 동일 로직: 가드 폴백 → 시퀀스 예측. (label, confidence) 또는 (None, 0.0)."""
    if _model_seq is None or _np is None or not sequence or len(sequence) != SEQ_LEN:
        return None, 0.0
    sequence = list(sequence)
    last_frame = _np.array(sequence[-1], dtype=_np.float32).reshape(1, -1)
    if _model_single is not None:
        single_pred = _model_single.predict(last_frame, verbose=0)[0]
        single_idx = int(_np.argmax(single_pred))
        single_conf = float(single_pred[single_idx])
        if single_idx == GUARD_INDEX and single_conf >= GUARD_FALLBACK_THRESHOLD:
            return "guard", single_conf
    X = _np.array(sequence, dtype=_np.float32).reshape(1, SEQ_LEN, -1)
    pred = _model_seq.predict(X, verbose=0)[0]
    idx = int(_np.argmax(pred))
    conf = float(pred[idx])
    label = CLASS_NAMES[idx]
    if conf < CONFIDENCE_THRESHOLD:
        label = "none"
    return label, conf

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


def predict_action(sequence):
    """로컬 모델이 있으면 로컬 추론, 없으면 HTTP로 pose_server 요청. (액션, 확신도) 반환. 스레드에서만 호출."""
    if not sequence or len(sequence) != SEQ_LEN:
        return None, 0.0
    if _use_local_inference:
        return _predict_local(sequence)
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


# ML 예측 결과 (백그라운드 스레드에서 갱신, 메인 루프는 읽기만)
_pred_lock = threading.Lock()
_last_pred = None
_last_confidence = 0.0
_predict_busy = False


def _predict_worker(sequence):
    global _last_pred, _last_confidence, _predict_busy
    res, conf = predict_action(sequence)
    with _pred_lock:
        _last_pred = res
        _last_confidence = conf
        _predict_busy = False


def start_predict_async(sequence):
    """시퀀스를 백그라운드에서 예측하도록 요청. 이미 예측 중이면 무시."""
    global _predict_busy
    with _pred_lock:
        if _predict_busy or not sequence or len(sequence) != SEQ_LEN:
            return
        _predict_busy = True
    t = threading.Thread(target=_predict_worker, args=(sequence.copy(),), daemon=True)
    t.start()


def get_last_pred():
    with _pred_lock:
        return _last_pred, _last_confidence


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
            print("pose_server가 바로 종료되었습니다 (코드 %s)." % proc.returncode)
            if err:
                print(err.decode(errors="replace")[-1200:])
            return False
        if _pose_server_health_ok():
            return True
        time.sleep(0.25)
    print("pose_server 헬스 체크 타임아웃 (%s초)." % int(timeout_sec))
    return False


def _ensure_pose_server(auto_spawn: bool):
    """HTTP 추론용 pose_server. (성공 여부, 이 스크립트가 띄운 Popen 또는 None)."""
    if _pose_server_health_ok():
        print("추론: pose_server (HTTP, 이미 실행 중)")
        return True, None
    if not auto_spawn:
        print("추론: pose_server 필요. 수동 실행: cd tools && python pose_server.py")
        print("      (자동 시작을 쓰려면 --no-auto-server 옵션을 빼세요)")
        return False, None
    if not os.path.isfile(MODEL_SEQ_PATH):
        print("로컬 추론 불가 + pose_classifier_seq.keras 없음 → pose_server를 시작할 수 없습니다.")
        return False, None
    if not os.path.isfile(POSE_SERVER_SCRIPT):
        print("pose_server.py를 찾을 수 없습니다:", POSE_SERVER_SCRIPT)
        return False, None
    print("로컬 추론 불가 → pose_server 자동 시작 중...")
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
    print("pose_server 준비 완료 (http://127.0.0.1:5000)")
    return True, proc


def main():
    parser = argparse.ArgumentParser(description="Webcam -> ML -> UDP for Body Hero")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index (기본 0, 외부 웹캠은 1/2일 수 있음)")
    parser.add_argument(
        "--no-auto-server",
        action="store_true",
        help="로컬 추론 불가 시 pose_server를 자동으로 띄우지 않음 (별도 터미널에서 수동 실행)",
    )
    parser.add_argument(
        "--process-w",
        type=int,
        default=None,
        metavar="W",
        help=f"MediaPipe/ML 입력 너비 (기본 {PROCESS_W}, 가벼우려면 320)",
    )
    parser.add_argument(
        "--process-h",
        type=int,
        default=None,
        metavar="H",
        help=f"MediaPipe/ML 입력 높이 (기본 {PROCESS_H})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="미리보기 창 없이 실행 (opencv-python-headless·원격 터미널 등). 종료: Ctrl+C",
    )
    args = parser.parse_args()
    process_w = PROCESS_W if args.process_w is None else max(64, args.process_w)
    process_h = PROCESS_H if args.process_h is None else max(64, args.process_h)
    spawned_server = None
    cap = None
    landmarker = None
    sock = None

    try:
        _download_pose_model()
        if _load_local_models():
            guard_ok = "가드 폴백 O" if _model_single is not None else "가드 폴백 X"
            print("추론: 로컬 모델 (pose_server 불필요). %s (시퀀스 %d프레임)" % (guard_ok, SEQ_LEN))
        else:
            ok, spawned_server = _ensure_pose_server(auto_spawn=not args.no_auto_server)
            if not ok:
                return

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

        def letterbox_square_bgr(bgr, side: int):
            """비정사각 입력 시 MediaPipe NORM_RECT 경고 완화(정사각 ROI)."""
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

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cap = cv2.VideoCapture(args.camera_index)
        if not cap.isOpened():
            print(f"웹캠을 열 수 없습니다. (--camera-index {args.camera_index})")
            return

        last_action_time = 0.0
        last_any_punch_send_time = -999.0
        guarding = False
        guard_exit_count = 0
        jab_l_count = 0
        jab_r_count = 0
        other_punch_pred = None
        other_punch_count = 0
        last_upper_sent_side = None  # "l" | "r" — upper_l/upper_r 직후 반대쪽 어퍼 확정 억제용
        upper_block_other_until_frame = 0
        # 같은 펀치를 자세 유지 동안 연속 UDP 하지 않음 (none/가드로 리셋)
        punch_repeat_block = None
        jab_holdoff_until_frame = 0
        none_streak = 0
        frame_idx = 0
        sequence_buffer = []  # 최근 SEQ_LEN프레임 (test_pose_live처럼 포즈 있으면 무조건 추가)
        last_lm = None
        last_flat = None
        prev_flat_norm = None  # 직전 포즈 정규화 벡터 — 어퍼 준비(저속) vs 실제 궤적 구분용
        motion_mean_abs = 0.0
        pred_history: deque = deque(maxlen=12)
        in_zone = False  # Godot 전송 여부만 제어

        print("웹캠 + ML(시퀀스) 판정 → Godot UDP")
        print(f"카메라 인덱스: {args.camera_index}")
        print(f"설정: 해상도 {process_w}x{process_h}, 시퀀스 {SEQ_LEN}프레임, FPS 목표 {FPS_TARGET}")
        gui_enabled: bool = not args.headless
        if args.headless:
            print("헤드리스 모드: 미리보기 창 없음. 종료: Ctrl+C")
        else:
            print("종료: Q 키 또는 Ctrl+C")
        print("※ [액션] 한 줄 = UDP로 게임에 전송 1회입니다. 같은 줄이 연속이면 그만큼 여러 번 나간 것입니다.\n")

        def send(action: str):
            sock.sendto(action.encode("utf-8"), (GODOT_HOST, GODOT_PORT))
            print(f"  [액션] {action}")

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

                # test_pose_live와 동일: 포즈 있으면 버퍼에 추가, SEQ_LEN개 차면 예측 요청 (zone 무관)
                run_pose_this_frame = (frame_idx % PROCESS_EVERY_N_FRAMES == 0)
                if run_pose_this_frame:
                    result = landmarker.detect_for_video(make_mp_image(rgb), ts_ms)
                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        last_lm = result.pose_landmarks[0]
                        (cx, cy), _ = shoulder_center_and_width(last_lm)
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
                    else:
                        last_lm = None
                        sequence_buffer.clear()
                        prev_flat_norm = None
                        motion_mean_abs = 0.0

                pred, confidence = get_last_pred()
                pred_history.append(pred if pred is not None else "none")
                lm = last_lm

                # 동일 펀치 연타 방지: none/가드로 돌아왔을 때만 풀림 (jab↔upper 깜빡임으로 서로 리셋되지 않게)
                if pred in (None, "none", "guard"):
                    punch_repeat_block = None

                if pred in (None, "none"):
                    none_streak += 1
                    if none_streak >= NONE_STREAK_TO_CLEAR_JAB_HOLDOFF:
                        jab_holdoff_until_frame = 0
                else:
                    none_streak = 0
                if pred in POWER_PUNCH_LABELS:
                    jab_holdoff_until_frame = max(
                        jab_holdoff_until_frame,
                        frame_idx + JAB_HOLDOFF_AFTER_POWER_PRED_FRAMES,
                    )

                action = None
                now = time.time()
                if pred == "guard":
                    guard_exit_count = 0
                    jab_l_count = 0
                    jab_r_count = 0
                    other_punch_pred = None
                    other_punch_count = 0
                    if not guarding and (now - last_action_time) >= 0.15:
                        action = "guard"
                        guarding = True
                else:
                    if guarding:
                        # 가드 중 ML이 잽/훅으로 튀어도 카운트만 쌓이면 guard_end 직후 바로 펀치가 나가는 것 방지
                        jab_l_count = 0
                        jab_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0
                        guard_exit_count += 1
                        if guard_exit_count >= GUARD_EXIT_FRAMES:
                            action = "guard_end"
                            guarding = False
                    if action is None and (now - last_action_time) >= COOLDOWN_SEC:
                        jab_allowed = frame_idx >= jab_holdoff_until_frame
                        recent_preds = list(pred_history)
                        hook_recent = any(
                            p in ("hook_l", "hook_r") for p in recent_preds[-8:]
                        )
                        if pred == "jab_l":
                            other_punch_pred = None
                            other_punch_count = 0
                            jab_r_count = 0
                            if hook_recent:
                                jab_l_count = 0
                            elif jab_allowed:
                                jab_l_count += 1
                            else:
                                jab_l_count = 0
                            if jab_l_count >= JAB_CONFIRM_FRAMES:
                                action = "jab_l"
                                jab_l_count = 0
                        elif pred == "jab_r":
                            other_punch_pred = None
                            other_punch_count = 0
                            jab_l_count = 0
                            if hook_recent:
                                jab_r_count = 0
                            elif jab_allowed:
                                jab_r_count += 1
                            else:
                                jab_r_count = 0
                            if jab_r_count >= JAB_CONFIRM_FRAMES:
                                action = "jab_r"
                                jab_r_count = 0
                        elif pred in ("upper_l", "upper_r", "hook_l", "hook_r"):
                            jab_l_count = 0
                            jab_r_count = 0
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
                            # 어퍼: 첫 카운트는 랜드마크가 움직일 때만(준비 자세 정지 억제). 한번 쌓인 뒤는 피크에서 멈춰도 유지.
                            upper_motion_ok: bool = (not is_upper) or (
                                motion_mean_abs >= UPPER_MOTION_MEAN_ABS_MIN
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
                        else:
                            jab_l_count = 0
                            jab_r_count = 0
                            other_punch_pred = None
                            other_punch_count = 0

                # 가드 중에는 펀치 UDP 무시 (ML이 어퍼로 튀어도 게임 가드 유지)
                if guarding and action and action in PUNCH_LABELS:
                    action = None

                if action and action in PUNCH_LABELS and punch_repeat_block == action:
                    action = None

                if action and action in PUNCH_LABELS:
                    if (now - last_any_punch_send_time) < MIN_GAP_BETWEEN_ANY_PUNCH_SEC:
                        action = None
                        jab_l_count = 0
                        jab_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0

                if action and in_zone:
                    send(action)
                    last_action_time = time.time()
                    if action in PUNCH_LABELS:
                        last_any_punch_send_time = time.time()
                        punch_repeat_block = action
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
                        jab_holdoff_until_frame = max(
                            jab_holdoff_until_frame,
                            frame_idx + JAB_HOLDOFF_AFTER_POWER_PRED_FRAMES,
                        )

                # 상단 중앙에 현재 동작 표시
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

                if lm:
                    h, w = frame_small.shape[0], frame_small.shape[1]
                    for (i, j) in POSE_CONNECTIONS:
                        if i < len(lm) and j < len(lm):
                            a = (int(lm[i].x * w), int(lm[i].y * h))
                            b = (int(lm[j].x * w), int(lm[j].y * h))
                            cv2.line(frame_small, a, b, (0, 255, 100), 2)
                    for p in lm:
                        x, y = int(p.x * w), int(p.y * h)
                        cv2.circle(frame_small, (x, y), 3, (0, 200, 255), -1)

                if gui_enabled:
                    try:
                        cv2.imshow("Body Hero — ML Pose", frame_small)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    except Exception:
                        gui_enabled = False
                        print(
                            "OpenCV highgui 없음 → 헤드리스로 전환했습니다 (종료: Ctrl+C).\n"
                            "  창이 필요하면: pip uninstall opencv-python-headless -y && pip install opencv-python"
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
            print("pose_server 자동 시작 프로세스를 종료했습니다.")
    print("종료.")


if __name__ == "__main__":
    main()
