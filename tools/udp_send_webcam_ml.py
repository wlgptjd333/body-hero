"""
웹캠 → Pose 랜드마크 → ML 추론(로컬 또는 pose_server) → Godot에 UDP로 액션 전송.

- 기본: pose_classifier_seq_len4.keras(있으면) → 없으면 pose_classifier_seq.keras + pose_classifier.keras(가드 폴백). pose_server 불필요.
- 시퀀스 모델이 없으면 HTTP로 pose_server에 요청. 서버가 없으면 pose_server.py를 자동으로 띄움 (--no-auto-server 로 끌 수 있음).

사용 순서:
  1) 데이터 수집: python collect_pose_data.py
  2) 시퀀스 학습: python train_pose_classifier_seq.py  [가드 폴백: train_pose_classifier.py]
  3) 본 스크립트: python udp_send_webcam_ml.py
  4) Godot 실행 후 플레이

펀치(punch_l/r) 라벨이 전혀 안 뜰 때: --debug-topk 5 로 시퀀스 softmax 순위 확인.
  상위가 none이면 데이터·재학습 쪽, punch가 있는데 확률만 낮으면 --punch-confidence 0.5~0.65.
  가드만 뜨면 --skip-guard-single 으로 단일 가드 모델 단축을 끄고 비교.
  어퍼 윈드업에서 직선이 먼저 나가면: `--upper-windup-punch-suppress`. 직선 잽은 어퍼보다 확정 프레임 짧게·softmax는 어퍼와 동일 하한 권장.
  한 번의 펀치·어퍼에 UDP가 여러 번 나가면: `--attack-rearm-frames`(기본 3). 0이면 끔.
  Godot UDP 액션: punch_l, punch_r, upper_l, upper_r, guard, dodge …
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
from typing import Any, List, Optional, Tuple

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

from pose_normalize import normalize_landmarks_flat, shoulder_center_and_width
from pose_class_names import GUARD_INDEX, POSE_CLASS_NAMES
from cv_capture import open_cv_video_capture

# 로컬 추론용 (pose_server와 동일). 시퀀스 길이는 로드한 모델 입력(time)에서 자동 설정.
# 기본은 seq_len=8 모델을 우선 사용(없을 때만 len4 폴백).
_MODEL_SEQ_4 = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")
_MODEL_SEQ_8 = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
MODEL_SEQ_PATH = _MODEL_SEQ_8 if os.path.isfile(_MODEL_SEQ_8) else _MODEL_SEQ_4
MODEL_SINGLE_PATH = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
SEQ_LEN = 8 if MODEL_SEQ_PATH == _MODEL_SEQ_8 else 4
CLASS_NAMES = list(POSE_CLASS_NAMES)
# ML·UDP 라벨 = POSE_CLASS_NAMES (punch_l/r …)
# 시퀀스 모델: 1등 클래스 확률이 이 값 미만이면 none. (기본은 balanced에 맞춤; --profile 로 덮어씀)
CONFIDENCE_THRESHOLD = 0.93
UPPER_CONFIDENCE_THRESHOLD = 0.88
# 직선 펀치 softmax 하한. 기본은 어퍼와 동일(0.88) — 너무 높으면 잽이 잘 안 나감. --punch-confidence 로 덮어씀.
PUNCH_CONFIDENCE_THRESHOLD = 0.88
GUARD_FALLBACK_THRESHOLD = 0.45
COOLDOWN_SEC = 0.08
MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.08
GUARD_EXIT_FRAMES = 10
FPS_TARGET = 30
# 처리 해상도: 높을수록 좌우(펀치) 구분·포즈 안정에 유리, CPU 부하 증가 (렉 시 320x240 또는 --process-w/h로 낮춤)
PROCESS_W, PROCESS_H = 480, 360
# 이 프레임 수마다만 포즈+ML 실행 (1=매프레임, 2=2프레임마다). test_pose_live처럼 인식하려면 1
PROCESS_EVERY_N_FRAMES = 1
# Godot으로 액션 전송 시에만 적용: 어깨 중심이 이 구역 안에 있을 때만 전송 (화면 표시는 zone 무관)
CENTER_ZONE_X = (0.2, 0.8)  # normalized [0,1] 기준
CENTER_ZONE_Y = (0.2, 0.8)
PUNCH_CONFIRM_FRAMES = 1
OTHER_PUNCH_CONFIRM_FRAMES = 1
UPPER_PUNCH_CONFIRM_FRAMES = 1
UPPER_MOTION_MEAN_ABS_MIN = 0.0015
UPPER_L_MOTION_RELAX = 0.6
PUNCH_HOLDOFF_AFTER_UPPER_FRAMES = 4
UPPER_LR_OPPOSITE_BLOCK_FRAMES = 6
NONE_STREAK_TO_CLEAR_PUNCH_HOLDOFF = 3
SQUAT_CONFIRM_FRAMES = 2
# 펀치·어퍼 1회 전송 후, ML이 공격 라벨이 아닌 프레임이 이 값 연속일 때만 다음 공격 전송(기본은 argparse로 덮어씀).
ACTION_REARM_OFF_ATTACK_FRAMES_DEFAULT = 1
POWER_PUNCH_LABELS = ("upper_l", "upper_r")
PUNCH_LABELS = ("punch_l", "punch_r", "upper_l", "upper_r")
# 정규화 좌표: y는 아래로 갈수록 증가. 손목이 같은쪽 어깨보다 이 값만큼 더 아래면 "낮은 준비"로 간주.
UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT = 0.08

# main()에서 argparse로 덮어씀 (추론 스레드가 읽음)
_debug_seq_topk: int = 0
_skip_guard_single: bool = False
_punch_confidence_override: Optional[float] = None

# 속도/정확도 프리셋 (런타임에서 상수들을 덮어씀)
SPEED_PROFILES = ("balanced", "fast_react", "fast_combo", "max_speed")

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


# 로컬 추론: numpy는 즉시, TensorFlow는 _load_local_models()에서만 로드(시작·스레드 분리로 체감 지연 완화)
_np = None
_tf = None
_model_seq = None
_model_single = None
_use_local_inference = False

try:
    import numpy as _np
except ImportError:
    _np = None


def _prepare_tf_import_env() -> None:
    """CUDA/GPU 프로브가 오래 걸리는 PC에서 TF 첫 임포트 시간을 줄이기 위해 CPU만 씀(환경 변수로 끌 수 있음)."""
    v = os.environ.get("BODY_HERO_TF_CPU_ONLY", "1")
    if str(v).strip().lower() not in ("0", "false", "no", "off"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"


def _keras_load_model_safe(path: str):
    """compile=False로 그래프/메트릭 컴파일 생략 → 로드 시간 단축. 구형 TF는 인자 없이 재시도."""
    if _tf is None:
        return None
    try:
        return _tf.keras.models.load_model(path, compile=False)
    except TypeError:
        return _tf.keras.models.load_model(path)


def _load_local_models():
    """동기: 시퀀스+가드 모델 전부 로드. (테스트·스크립트 호환용; 런타임은 _tf_load_worker_phased 사용)"""
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
    """백그라운드: 시퀀스 모델만 먼저 끝내고 이벤트로 알림 → 가드용 단일 모델은 그 뒤에 로드(게임 시작 대기 시간 단축)."""
    global _tf, _model_seq, _model_single, _use_local_inference, SEQ_LEN
    try:
        if _np is None:
            load_errors.append(RuntimeError("numpy가 없습니다."))
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
    except BaseException as e:
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
        print("가드 보조 모델(Keras) 추가 로드 중…", flush=True)
        _model_single = _keras_load_model_safe(MODEL_SINGLE_PATH)
        print("가드 보조 모델 로드 완료.", flush=True)
    except BaseException as e:
        print("가드 보조 모델 로드 실패(시퀀스만 사용):", e, flush=True)


def _predict_local(
    sequence: list,
    seq_topk: int = 0,
) -> Tuple[Optional[str], float, Optional[List[Tuple[str, float]]]]:
    """가드 단일(선택) → 시퀀스 softmax. (표시 라벨, 확신도, seq_topk>0일 때 상위k (이름,확률)).

    seq_topk>0이면 가드로 단축되기 전에도 시퀀스를 한 번 돌려 상위 확률을 돌려준다(원인 조사용).
    """
    none3: Tuple[Optional[str], float, Optional[List[Tuple[str, float]]]] = (None, 0.0, None)
    if _model_seq is None or _np is None or not sequence or len(sequence) != SEQ_LEN:
        return none3
    sequence = list(sequence)
    last_frame = _np.array(sequence[-1], dtype=_np.float32).reshape(1, -1)

    pred_vec: Any = None
    topk_list: Optional[List[Tuple[str, float]]] = None
    if seq_topk > 0:
        X0 = _np.array(sequence, dtype=_np.float32).reshape(1, SEQ_LEN, -1)
        pred_vec = _model_seq.predict(X0, verbose=0)[0]
        k = min(seq_topk, len(CLASS_NAMES))
        idxs = _np.argsort(pred_vec)[-k:][::-1]
        topk_list = [(CLASS_NAMES[int(i)], float(pred_vec[int(i)])) for i in idxs]

    if _model_single is not None and not _skip_guard_single:
        single_pred = _model_single.predict(last_frame, verbose=0)[0]
        single_idx = int(_np.argmax(single_pred))
        single_conf = float(single_pred[single_idx])
        if single_idx == GUARD_INDEX and single_conf >= GUARD_FALLBACK_THRESHOLD:
            return "guard", single_conf, topk_list

    if pred_vec is None:
        X = _np.array(sequence, dtype=_np.float32).reshape(1, SEQ_LEN, -1)
        pred_vec = _model_seq.predict(X, verbose=0)[0]

    idx = int(_np.argmax(pred_vec))
    conf = float(pred_vec[idx])
    label = CLASS_NAMES[idx]
    if label in ("upper_l", "upper_r"):
        need = UPPER_CONFIDENCE_THRESHOLD
    elif label in ("punch_l", "punch_r"):
        need = (
            _punch_confidence_override
            if _punch_confidence_override is not None
            else PUNCH_CONFIDENCE_THRESHOLD
        )
    else:
        need = CONFIDENCE_THRESHOLD
    if conf < need:
        label = "none"
    return label, conf, topk_list

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


# ML 예측 결과 (백그라운드 스레드에서 갱신, 메인 루프는 읽기만)
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
        return _last_pred, _last_confidence, _last_seq_topk


def _low_chamber_straight_punch_ambiguous(
    flat: List[float], pred: Optional[str], margin: float
) -> bool:
    """같은 쪽 손목이 어깨보다 충분히 아래면 직선 펀치 라벨을 UDP로 확정하지 않음(어퍼 윈드업과 구분)."""
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
        "--camera-backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windows 권장: auto(DirectShow 우선). USB가 안 잡히면 dshow + --camera-index 바꿔 보세요.",
    )
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
    parser.add_argument(
        "--allow-tf-gpu",
        action="store_true",
        help="TensorFlow가 GPU/CUDA를 탐색하게 함. 기본은 CPU만 사용해 첫 임포트가 더 빠른 경우가 많음.",
    )
    parser.add_argument(
        "--seq-model",
        default=None,
        help="시퀀스 모델 경로(기본 tools/pose_classifier_seq.keras). seq_len4/6/8 모델을 바꿔 끼워 첫 반응 속도 튜닝 가능",
    )
    parser.add_argument(
        "--profile",
        choices=list(SPEED_PROFILES),
        default="balanced",
        help="속도/정확도 프리셋 (balanced|fast_react|fast_combo|max_speed), 기본 balanced",
    )
    parser.add_argument(
        "--react",
        type=float,
        default=None,
        help="첫 반응 속도(0~1). 높을수록 확정 프레임/임계값이 공격적으로 바뀜. --profile 위에 추가로 적용",
    )
    parser.add_argument(
        "--combo",
        type=float,
        default=None,
        help="연타 속도(0~1). 높을수록 COOLDOWN/MIN_GAP이 짧아짐. --profile 위에 추가로 적용",
    )
    parser.add_argument(
        "--debug-topk",
        type=int,
        default=0,
        metavar="K",
        help="시퀀스 모델 softmax 상위 K개를 화면 왼쪽에 표시(0=끔). 펀치가 순위에만 올라오는지·확률이 얼마인지 확인.",
    )
    parser.add_argument(
        "--skip-guard-single",
        action="store_true",
        help="마지막 프레임 가드 단일 모델 단축을 끈다. 가드에 펀치가 먹히는지 비교용(시퀀스만으로 라벨 결정).",
    )
    parser.add_argument(
        "--punch-confidence",
        type=float,
        default=None,
        metavar="P",
        help="punch_l/punch_r만 채택 최소 softmax(0~1). 생략 시 프로필의 PUNCH_CONFIDENCE_THRESHOLD. 약하면 0.55~0.88로 시험.",
    )
    parser.add_argument(
        "--upper-windup-punch-suppress",
        action="store_true",
        help="낮은 준비(손목이 어깨 아래)에서 punch_l/r UDP 확정 억제(어퍼 윈드업 시 직선 먼저 나감 완화). 기본은 끔.",
    )
    parser.add_argument(
        "--upper-windup-punch-margin",
        type=float,
        default=None,
        metavar="M",
        help="억제 판정: 손목 y > 어깨 y + M 일 때 직선 펀치 미확정. 기본 %.2f (--upper-windup-punch-suppress 켰을 때만)."
        % UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT,
    )
    parser.add_argument(
        "--attack-rearm-frames",
        type=int,
        default=ACTION_REARM_OFF_ATTACK_FRAMES_DEFAULT,
        metavar="N",
        help="펀치·어퍼 UDP 1회 후, punch/upper 가 아닌 라벨이 N프레임 연속일 때만 다음 펀치·어퍼 허용. 기본 3. 0=끔.",
    )
    args = parser.parse_args()
    if args.allow_tf_gpu:
        os.environ["BODY_HERO_TF_CPU_ONLY"] = "0"

    global _debug_seq_topk, _skip_guard_single, _punch_confidence_override
    _debug_seq_topk = max(0, int(args.debug_topk))
    _skip_guard_single = bool(args.skip_guard_single)
    if args.punch_confidence is not None:
        jc = float(args.punch_confidence)
        if jc < 0.0 or jc > 1.0:
            print("--punch-confidence 는 0~1 사이여야 합니다. 무시합니다.", flush=True)
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

    if args.profile == "balanced":
        COOLDOWN_SEC = 0.22
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.22
        # 직선 잽: 어퍼보다 적은 연속 프레임으로 반응. softmax는 어퍼와 동일(너무 높이면 잽 누락).
        OTHER_PUNCH_CONFIRM_FRAMES = 3
        UPPER_PUNCH_CONFIRM_FRAMES = 3
        PUNCH_CONFIRM_FRAMES = 2
        CONFIDENCE_THRESHOLD = 0.93
        UPPER_CONFIDENCE_THRESHOLD = 0.88
        PUNCH_CONFIDENCE_THRESHOLD = UPPER_CONFIDENCE_THRESHOLD
        UPPER_MOTION_MEAN_ABS_MIN = 0.0015
        UPPER_L_MOTION_RELAX = 0.6
    elif args.profile == "fast_react":
        COOLDOWN_SEC = 0.22
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.22
        OTHER_PUNCH_CONFIRM_FRAMES = 2
        UPPER_PUNCH_CONFIRM_FRAMES = 2
        PUNCH_CONFIRM_FRAMES = 2
        CONFIDENCE_THRESHOLD = 0.93
        UPPER_CONFIDENCE_THRESHOLD = 0.88
        PUNCH_CONFIDENCE_THRESHOLD = UPPER_CONFIDENCE_THRESHOLD
        UPPER_MOTION_MEAN_ABS_MIN = 0.0012
        UPPER_L_MOTION_RELAX = 0.55
    elif args.profile == "fast_combo":
        COOLDOWN_SEC = 0.17
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.17
        OTHER_PUNCH_CONFIRM_FRAMES = 3
        UPPER_PUNCH_CONFIRM_FRAMES = 3
        PUNCH_CONFIRM_FRAMES = 2
        CONFIDENCE_THRESHOLD = 0.95
        UPPER_CONFIDENCE_THRESHOLD = 0.90
        PUNCH_CONFIDENCE_THRESHOLD = UPPER_CONFIDENCE_THRESHOLD
        UPPER_MOTION_MEAN_ABS_MIN = 0.0015
        UPPER_L_MOTION_RELAX = 0.6
    elif args.profile == "max_speed":
        # 콤보 우선: 오인식 리스크를 감수하고 반응·연타 지연 최소화
        COOLDOWN_SEC = 0.06
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = 0.06
        OTHER_PUNCH_CONFIRM_FRAMES = 1
        UPPER_PUNCH_CONFIRM_FRAMES = 1
        PUNCH_CONFIRM_FRAMES = 1
        CONFIDENCE_THRESHOLD = 0.82
        UPPER_CONFIDENCE_THRESHOLD = 0.76
        PUNCH_CONFIDENCE_THRESHOLD = UPPER_CONFIDENCE_THRESHOLD
        UPPER_MOTION_MEAN_ABS_MIN = 0.0008
        UPPER_L_MOTION_RELAX = 0.5

    if args.combo is not None:
        c = max(0.0, min(1.0, float(args.combo)))
        gap = 0.26 - 0.12 * c  # 0.26 -> 0.14 (연타 한계 소폭 완화)
        COOLDOWN_SEC = min(COOLDOWN_SEC, gap)
        MIN_GAP_BETWEEN_ANY_PUNCH_SEC = min(MIN_GAP_BETWEEN_ANY_PUNCH_SEC, gap)

    if args.react is not None:
        r = max(0.0, min(1.0, float(args.react)))
        if r >= 0.75:
            OTHER_PUNCH_CONFIRM_FRAMES = min(OTHER_PUNCH_CONFIRM_FRAMES, 2)
            UPPER_PUNCH_CONFIRM_FRAMES = min(UPPER_PUNCH_CONFIRM_FRAMES, 2)
            PUNCH_CONFIRM_FRAMES = min(PUNCH_CONFIRM_FRAMES, 2)
        elif r >= 0.7:
            OTHER_PUNCH_CONFIRM_FRAMES = min(OTHER_PUNCH_CONFIRM_FRAMES, 2)
            UPPER_PUNCH_CONFIRM_FRAMES = min(UPPER_PUNCH_CONFIRM_FRAMES, 2)
            PUNCH_CONFIRM_FRAMES = min(PUNCH_CONFIRM_FRAMES, 3)
        CONFIDENCE_THRESHOLD = min(CONFIDENCE_THRESHOLD, 0.95 - 0.03 * r)
        UPPER_CONFIDENCE_THRESHOLD = min(UPPER_CONFIDENCE_THRESHOLD, 0.90 - 0.04 * r)
        PUNCH_CONFIDENCE_THRESHOLD = min(PUNCH_CONFIDENCE_THRESHOLD, 0.94 - 0.05 * r)
        UPPER_MOTION_MEAN_ABS_MIN = min(UPPER_MOTION_MEAN_ABS_MIN, 0.0015 - 0.0005 * r)
    process_w = PROCESS_W if args.process_w is None else max(64, args.process_w)
    process_h = PROCESS_H if args.process_h is None else max(64, args.process_h)
    upper_windup_margin = UPPER_WINDUP_WRIST_BELOW_SHOULDER_DEFAULT
    if args.upper_windup_punch_margin is not None:
        upper_windup_margin = max(0.0, float(args.upper_windup_punch_margin))
    suppress_low_chamber_punch = bool(args.upper_windup_punch_suppress)
    attack_rearm_n: int = max(0, int(args.attack_rearm_frames))
    spawned_server = None
    cap = None
    landmarker = None
    sock = None

    try:
        _download_pose_model()

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
            print(f"웹캠을 열 수 없습니다. (--camera-index {args.camera_index} --camera-backend {args.camera_backend})")
            load_th.join(timeout=3.0)
            return

        print(
            f"카메라 열림: index={args.camera_index} backend={args.camera_backend} ({cap_backend_note})",
            flush=True,
        )

        BaseOptions = mp_tasks.BaseOptions
        PoseLandmarker = vision.PoseLandmarker
        PoseLandmarkerOptions = vision.PoseLandmarkerOptions
        RunningMode = vision.RunningMode
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.VIDEO,
            num_poses=1,
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
                print("모델 로딩 타임아웃(900초).", flush=True)
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
                    cv2.imshow("Body Hero — ML Pose", frame_s)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        print("로딩 중 사용자가 Q로 종료했습니다.")
                        return
                except Exception:
                    gui_load_wait = False
            else:
                time.sleep(0.05)
            if not gui_load_wait and time.time() - last_console_ping > 8.0:
                print("준비 중 (%s) %.0f초 경과" % (status_line, time.time() - t_load0), flush=True)
                last_console_ping = time.time()

        mp_th.join()
        if landmarker_holder["err"] is not None:
            raise landmarker_holder["err"]
        landmarker = landmarker_holder["lm"]
        if landmarker is None:
            print("MediaPipe PoseLandmarker 초기화에 실패했습니다.", flush=True)
            return

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

        if load_errors:
            print("모델 로드 실패:", load_errors[0], flush=True)
            raise load_errors[0]

        if _use_local_inference:
            guard_ok = (
                "가드 폴백 O"
                if _model_single is not None
                else "가드 폴백 X(시퀀스만, 보조 모델은 백그라운드 로딩 중일 수 있음)"
            )
            print("추론: 로컬 모델 (pose_server 불필요). %s (시퀀스 %d프레임)" % (guard_ok, SEQ_LEN), flush=True)
        else:
            ok, spawned_server = _ensure_pose_server(auto_spawn=not args.no_auto_server)
            if not ok:
                return

        print("로컬 가중치 준비 완료 (%.1f초)" % (time.time() - t_load0), flush=True)

        last_action_time = 0.0
        last_any_punch_send_time = -999.0
        guarding = False
        guard_exit_count = 0
        punch_l_count = 0
        punch_r_count = 0
        other_punch_pred = None
        other_punch_count = 0
        squat_count = 0
        squat_armed = True
        last_upper_sent_side = None  # "l" | "r" — upper_l/upper_r 직후 반대쪽 어퍼 확정 억제용
        upper_block_other_until_frame = 0
        punch_holdoff_until_frame = 0
        none_streak = 0
        frame_idx = 0
        sequence_buffer = []  # 최근 SEQ_LEN프레임 (test_pose_live처럼 포즈 있으면 무조건 추가)
        last_lm = None
        last_flat = None
        prev_flat_norm = None  # 직전 포즈 정규화 벡터 — 어퍼 준비(저속) vs 실제 궤적 구분용
        motion_mean_abs = 0.0
        pred_history: deque = deque(maxlen=12)
        in_zone = False  # Godot 전송 여부만 제어
        neutral_off_attack_streak: int = 0
        attack_send_armed: bool = True

        print("웹캠 + ML(시퀀스) 판정 → Godot UDP")
        print(f"카메라: index={args.camera_index} backend={args.camera_backend} → {cap_backend_note}")
        print(f"설정: 해상도 {process_w}x{process_h}, 시퀀스 {SEQ_LEN}프레임, FPS 목표 {FPS_TARGET}")
        print(
            f"펀치: 직선은 연속 {PUNCH_CONFIRM_FRAMES}프레임 확정, softmax 하한 "
            f"{PUNCH_CONFIDENCE_THRESHOLD:.2f} (어퍼 {UPPER_PUNCH_CONFIRM_FRAMES}프·{UPPER_CONFIDENCE_THRESHOLD:.2f})",
            flush=True,
        )
        if attack_rearm_n > 0:
            print(
                f"공격 재장전: 펀치·어퍼 전송 후, 비공격 라벨 {attack_rearm_n}프레임 연속 시에만 다음 공격 전송. "
                "끔: --attack-rearm-frames 0",
                flush=True,
            )
        if suppress_low_chamber_punch:
            print(
                f"어퍼 윈드업 억제 켬: 손목이 같은쪽 어깨보다 y+{upper_windup_margin:.2f} 이상 아래면 "
                "punch_l/r UDP 확정 안 함.",
                flush=True,
            )
        if _debug_seq_topk <= 0 and _punch_confidence_override is None and not _skip_guard_single:
            print(
                "팁: 상단에 punch_l/punch_r이 전혀 안 뜨면: --debug-topk 5 (시퀀스 순위·확률), "
                "또는 --punch-confidence 0.55 / --skip-guard-single",
                flush=True,
            )
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
                        in_zone = False

                pred, confidence, seq_topk_debug = get_last_pred()
                pred_history.append(pred if pred is not None else "none")
                lm = last_lm

                if attack_rearm_n > 0:
                    pred_for_rearm: str = pred if pred is not None else "none"
                    if pred_for_rearm in PUNCH_LABELS:
                        neutral_off_attack_streak = 0
                    else:
                        neutral_off_attack_streak += 1
                        if neutral_off_attack_streak >= attack_rearm_n:
                            attack_send_armed = True

                if pred in (None, "none"):
                    none_streak += 1
                    if none_streak >= NONE_STREAK_TO_CLEAR_PUNCH_HOLDOFF:
                        punch_holdoff_until_frame = 0
                else:
                    none_streak = 0
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
                        # 가드 중 ML이 펀치로 튀어도 카운트만 쌓이면 guard_end 직후 바로 펀치가 나가는 것 방지
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
                            # 어퍼: 첫 카운트는 랜드마크가 움직일 때만(준비 자세 정지 억제). 한번 쌓인 뒤는 피크에서 멈춰도 유지.
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
                            # 스쿼트 1회(짧게 내려갔다 올라오기)당 dodge 1회만 전송.
                            # 유지 자세에서 반복 전송되지 않도록 squat_armed 로 재장전.
                            punch_l_count = 0
                            punch_r_count = 0
                            other_punch_pred = None
                            other_punch_count = 0
                            if squat_armed and squat_count >= SQUAT_CONFIRM_FRAMES:
                                action = "dodge"
                                squat_armed = False
                        else:
                            # none 등: 펀치 카운트는 유지. 동작이 짧아 punch→none→punch 패턴이 흔함.
                            if pred not in (None, "none"):
                                punch_l_count = 0
                                punch_r_count = 0
                            other_punch_pred = None
                            other_punch_count = 0

                # 가드 중에는 펀치 UDP 무시 (ML이 어퍼로 튀어도 게임 가드 유지)
                if guarding and action and action in PUNCH_LABELS:
                    action = None

                if action and action in PUNCH_LABELS:
                    if (now - last_any_punch_send_time) < MIN_GAP_BETWEEN_ANY_PUNCH_SEC:
                        action = None
                        punch_l_count = 0
                        punch_r_count = 0
                        other_punch_pred = None
                        other_punch_count = 0

                if attack_rearm_n > 0 and action and action in PUNCH_LABELS and not attack_send_armed:
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
                    if attack_rearm_n > 0 and action in PUNCH_LABELS:
                        attack_send_armed = False
                        neutral_off_attack_streak = 0

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
