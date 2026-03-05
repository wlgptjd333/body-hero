"""
웹캠 + MediaPipe Pose (Tasks API)로 어깨·손목 동작을 감지해 Godot에 액션만 UDP로 전송합니다.
0.10.30+ 표준 Tasks API 사용, RunningMode.VIDEO로 안정적 트래킹.

설치: pip install mediapipe opencv-python

실행: Godot 실행 후, cd tools → python udp_send_webcam.py
액션: jab_l, jab_r, upper_l, upper_r, hook_l, hook_r, guard, guard_end, dodge_l, dodge_r, jog

판정: 가드=양손이 코보다 높고 가까울 때, 잽=팔 뻗음, 어퍼컷=손목이 어깨보다 위.
회피=고개+어깨가 함께 좌/우로 충분히 이동할 때. 제자리걸음=어깨 위아래 진동(진폭+요동 횟수).
"""

import os
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import socket
import time
from collections import deque

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Godot UDP ────────────────────────────────────────────────
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 4242

# ── 타이밍 ───────────────────────────────────────────────────
COOLDOWN_SEC   = 0.30   # 같은 액션 재발동 최소 간격
DEADZONE_SEC   = 0.15   # 액션 후 무시 구간
FPS_TARGET     = 30
PROCESS_W      = 640
PROCESS_H      = 480

# ── Pose 랜드마크 인덱스 (MediaPipe Pose 33점) ───────────────
NOSE = 0
LEFT_SHOULDER  = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW     = 13
RIGHT_ELBOW    = 14
LEFT_WRIST     = 15
RIGHT_WRIST    = 16

# ── 가드: 양손이 코보다 높고 가까울 때 (지혜성 제안: 코 기준 + 0.15) ──
GUARD_X_CLOSE     = 0.15   # 양 손목 x 거리 < 이 값이면 "가드 자세" (조정: 가드가 잽으로 튀면 낮춤)
GUARD_Y_THRESH    = 0.55   # 코 없을 때 폴백: 손목 Y가 이하면 위쪽
GUARD_USE_NOSE    = True   # True면 손목이 코(nose) 높이보다 위일 때만 가드 구간
GUARD_ENTER_FRAMES = 3
GUARD_EXIT_FRAMES  = 4

# ── 어퍼컷: 한 손만 위로 (손목이 어깨보다 위) ─────────────────
UPPER_DY_THRESH   = -0.025  # 위로 빠르게 (dy 음수)
UPPER_Y_THRESH    = 0.55    # 손목 Y 상한
UPPER_Y_MARGIN    = 0.25    # 어퍼컷: 손목이 어깨보다 이만큼 위 (y: shoulder.y - margin)
UPPER_HISTORY     = 4

# ── 잽: 팔 뻗음 (손목이 어깨보다 앞/밖으로, 지혜성 제안 0.22) ──
JAB_EXTEND_X      = 0.22   # 손목-어깨 x 차이 (팔 길이에 맞게 0.18~0.25 조정)
JAB_VELOCITY_MIN  = 0.02   # 최소 속도
JAB_HISTORY       = 4

# ── 회피 (dodge): 고개와 어깨가 함께 확실히 좌/우로 움직일 때만 ─────────────────
DODGE_DX_THRESH   = 0.135   # 코 x가 이만큼 이상 이동 (작으면 펀치/고개만 살짝 움직여도 오인)
DODGE_SHOULDER_MIN = 0.065  # 어깨 중심 x도 같은 방향으로 이만큼 이상 이동해야 회피 (몸이 따라와야 함)
DODGE_HISTORY     = 6       # 몇 프레임 구간으로 이동량 계산
DODGE_COOLDOWN    = 0.85    # 회피 쿨다운 (초)

# ── 제자리걸음 (jog): 어깨가 위아래로 “진동”할 때만 (숨쉬기/가만히 서기 제외) ─────
JOG_Y_RANGE_MIN   = 0.050   # 어깨 y 범위(최대-최소)가 이 이상 — 확실한 위아래 움직임
JOG_SIGN_CHANGES_MIN = 2    # 최근 구간에서 y 변화 방향이 이 횟수 이상 바뀌어야 “요동”으로 인정
JOG_HISTORY       = 22      # 약 0.7초 @ 30fps
JOG_THROTTLE      = 0.24    # jog 패킷 전송 간격

# ── 기타 ─────────────────────────────────────────────────────
SWAP_LEFT_RIGHT   = False   # False = 화면 그대로 (이미 cv2.flip으로 거울처럼 보임 → 왼손=왼쪽, 오른손=오른쪽)
DEBUG_PRINT_ACTION = True

try:
    import cv2
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
except ImportError as e:
    print("pip install mediapipe opencv-python")
    raise SystemExit(1) from e

# Pose Landmarker .task 모델 (0.10.30+ Tasks API). 없으면 아래 URL에서 자동 다운로드
MODEL_PATH = os.path.join(SCRIPT_DIR, "pose_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker/lite/1/pose_landmarker_lite.task"
)
# 위 URL이 404면 HuggingFace 미러 사용
MODEL_URL_FALLBACK = "https://huggingface.co/AndorML/Public/resolve/02ef083b988890f7444aa40afad3a2029d3b9faa/pose_landmarker_lite.task"


def _download_pose_model():
    if os.path.isfile(MODEL_PATH):
        return
    print("Pose Landmarker 모델 다운로드 중... (처음 한 번만)")
    import urllib.request
    for url in (MODEL_URL, MODEL_URL_FALLBACK):
        try:
            urllib.request.urlretrieve(url, MODEL_PATH)
            print("다운로드 완료:", MODEL_PATH)
            return
        except Exception as e:
            print("  시도 실패:", url[:50], "...", e)
    print("직접 받아 tools 폴더에 pose_landmarker.task 넣어주세요.")
    print("  또는:", MODEL_URL_FALLBACK)
    raise SystemExit(1)


# 스켈레톤 그리기용 연결 (상체 위주). Tasks API에 POSE_CONNECTIONS 없을 수 있어 직접 정의
POSE_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19), (16, 18), (16, 20), (16, 22), (18, 20),
    (23, 24), (11, 23), (12, 24), (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30), (29, 31), (30, 32),
)


# ── 손목/어깨 히스토리 (Pose용, 좌/우 각각) ───────────────────
class ArmHistory:
    def __init__(self, n=10):
        self.wrist_xy = deque(maxlen=n)   # (x, y)
        self.shoulder_xy = deque(maxlen=n)
        self.seen = False
        self.missing_frames = 0
        self.grace_frames = 3   # 끊긴 후 이 프레임까지는 마지막 값으로 판정

    def update(self, wrist_xy, shoulder_xy):
        self.wrist_xy.append(wrist_xy)
        self.shoulder_xy.append(shoulder_xy)
        self.seen = True
        self.missing_frames = 0

    def mark_missing(self):
        self.missing_frames = min(10, self.missing_frames + 1)
        if self.missing_frames > self.grace_frames:
            self.seen = False

    def current_wrist(self):
        return self.wrist_xy[-1] if self.wrist_xy else (0.5, 0.5)

    def current_shoulder(self):
        return self.shoulder_xy[-1] if self.shoulder_xy else (0.5, 0.5)

    def avg_delta_wrist(self, axis, frames):
        if len(self.wrist_xy) < 2:
            return 0.0
        vals = [p[axis] for p in self.wrist_xy]
        n = min(frames, len(vals) - 1)
        if n <= 0:
            return 0.0
        deltas = [vals[-(i)] - vals[-(i+1)] for i in range(1, n + 1)]
        return sum(deltas) / len(deltas)

    def velocity(self, frames):
        dx = self.avg_delta_wrist(0, frames)
        dy = self.avg_delta_wrist(1, frames)
        return (dx*dx + dy*dy) ** 0.5


def _get_lm_xy(lm):
    return (lm.x, lm.y)


def main():
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
    # MediaPipe 버전에 따라 Image/ImageFormat 위치가 다름 (한 번만 import)
    _ImageCls = None
    _ImageFmt = None
    try:
        from mediapipe.tasks.python.vision.core import image as _img
        _ImageCls, _ImageFmt = _img.Image, _img.ImageFormat
    except ImportError:
        try:
            from mediapipe.python import ImageFormat as _ImageFmt
            from mediapipe.python._framework_bindings import image as _img
            _ImageCls, _ImageFmt = _img.Image, _ImageFmt
        except (ImportError, AttributeError) as e:
            print("MediaPipe Image를 찾을 수 없습니다:", e)
            print("  pip install --upgrade mediapipe  후 다시 시도하세요.")
            return
    def make_mp_image(rgb):
        return _ImageCls(image_format=_ImageFmt.SRGB, data=rgb.copy(order="C"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("웹캠을 열 수 없습니다.")
        return

    print("웹캠 + MediaPipe Pose (Tasks) → Godot 액션 전송")
    print("Godot 실행 후 사용. 종료: Q 키 또는 Ctrl+C\n")
    print("  잽/어퍼컷/가드: 기존대로")
    print("  회피: 고개+어깨를 확실히 좌/우로")
    print("  제자리걸음: 어깨가 위아래로 요동 (스태미너 회복)\n")

    hist_l = ArmHistory()
    hist_r = ArmHistory()
    nose_x_hist = deque(maxlen=12)
    shoulder_center_x_hist = deque(maxlen=12)
    shoulder_y_hist = deque(maxlen=28)
    last_sent = {}
    last_any_action = 0.0
    last_jog_sent = 0.0
    guarding = False
    guard_enter_count = 0
    guard_exit_count = 0
    frame_idx = 0

    def send(action: str):
        sock.sendto(action.encode("utf-8"), (GODOT_HOST, GODOT_PORT))
        if DEBUG_PRINT_ACTION:
            print(f"  [액션]  {action}")

    def game_side(base: str) -> str:
        if not SWAP_LEFT_RIGHT:
            return base
        return base.replace("_l", "_TMP").replace("_r", "_l").replace("_TMP", "_r")

    try:
        while True:
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                time.sleep(1 / FPS_TARGET)
                continue

            frame = cv2.flip(frame, 1)
            frame_small = cv2.resize(frame, (PROCESS_W, PROCESS_H))
            rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            ts_ms = int(frame_idx * 1000 / FPS_TARGET)
            frame_idx += 1
            mp_image = make_mp_image(rgb)
            result = landmarker.detect_for_video(mp_image, ts_ms)

            lm = None
            nose_y = GUARD_Y_THRESH  # 코 없을 때 폴백
            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm = result.pose_landmarks[0]
                nose_y = lm[NOSE].y if GUARD_USE_NOSE else GUARD_Y_THRESH
                nose_x_hist.append(lm[NOSE].x)
                l_sh = _get_lm_xy(lm[LEFT_SHOULDER])
                r_sh = _get_lm_xy(lm[RIGHT_SHOULDER])
                shoulder_center_x_hist.append((l_sh[0] + r_sh[0]) * 0.5)
                shoulder_y_hist.append((l_sh[1] + r_sh[1]) * 0.5)
                l_wr = _get_lm_xy(lm[LEFT_WRIST])
                r_wr = _get_lm_xy(lm[RIGHT_WRIST])
                hist_l.update(l_wr, l_sh)
                hist_r.update(r_wr, r_sh)
            else:
                hist_l.mark_missing()
                hist_r.mark_missing()

            now = time.time()
            action = None

            # ── 1) 가드 (최우선): 양손이 코보다 높고 가까울 때 ──
            guard_y_ref = nose_y if GUARD_USE_NOSE else GUARD_Y_THRESH
            left_high  = hist_l.seen and hist_l.current_wrist()[1] < guard_y_ref
            right_high = hist_r.seen and hist_r.current_wrist()[1] < guard_y_ref
            lwx, rwx = hist_l.current_wrist()[0], hist_r.current_wrist()[0]
            both_close = abs(lwx - rwx) < GUARD_X_CLOSE
            both_up = left_high and right_high and both_close

            if both_up:
                guard_enter_count += 1
                guard_exit_count = 0
                if guard_enter_count >= GUARD_ENTER_FRAMES and not guarding and (now - last_any_action) >= DEADZONE_SEC:
                    action = "guard"
                    guarding = True
                    last_any_action = now
            else:
                guard_exit_count += 1
                guard_enter_count = 0
                if guard_exit_count >= GUARD_EXIT_FRAMES and guarding:
                    action = "guard_end"
                    guarding = False

            # ── 2) 어퍼컷 / 잽 (가드 중·양손 동시 올림이 아닐 때만) ──
            if action is None and not guarding and not both_up and (now - last_any_action) >= DEADZONE_SEC:

                # 어퍼컷: 한 손만 위로 빠르게 (손목이 어깨보다 위)
                l_dy = hist_l.avg_delta_wrist(1, UPPER_HISTORY)
                r_dy = hist_r.avg_delta_wrist(1, UPPER_HISTORY)
                l_wy = hist_l.current_wrist()[1]
                r_wy = hist_r.current_wrist()[1]
                l_shy = hist_l.current_shoulder()[1]
                r_shy = hist_r.current_shoulder()[1]

                left_upper  = hist_l.seen and l_dy < UPPER_DY_THRESH and l_wy < UPPER_Y_THRESH and l_wy < l_shy - UPPER_Y_MARGIN
                right_upper = hist_r.seen and r_dy < UPPER_DY_THRESH and r_wy < UPPER_Y_THRESH and r_wy < r_shy - UPPER_Y_MARGIN
                both_moving_up = left_upper and right_upper

                for (hist, upper_ok, base) in [(hist_l, left_upper, "upper_l"), (hist_r, right_upper, "upper_r")]:
                    if action is not None:
                        break
                    if not upper_ok or both_moving_up:
                        continue
                    act = game_side(base)
                    if (now - last_sent.get(act, 0)) >= COOLDOWN_SEC:
                        action = act
                        last_sent[act] = now
                        last_any_action = now

                # 잽: 팔 뻗음 (손목이 어깨보다 앞/밖으로) + 속도
                if action is None:
                    l_sx, l_wx = hist_l.current_shoulder()[0], hist_l.current_wrist()[0]
                    r_sx, r_wx = hist_r.current_shoulder()[0], hist_r.current_wrist()[0]
                    left_extend  = hist_l.seen and (l_sx - l_wx) >= JAB_EXTEND_X  # 왼손이 왼쪽으로 뻗음
                    right_extend = hist_r.seen and (r_wx - r_sx) >= JAB_EXTEND_X   # 오른손이 오른쪽으로 뻗음
                    vl = hist_l.velocity(JAB_HISTORY)
                    vr = hist_r.velocity(JAB_HISTORY)

                    if left_extend and vl >= JAB_VELOCITY_MIN:
                        act = game_side("jab_l")
                        if (now - last_sent.get(act, 0)) >= COOLDOWN_SEC:
                            action = act
                            last_sent[act] = now
                            last_any_action = now
                    elif right_extend and vr >= JAB_VELOCITY_MIN and action is None:
                        act = game_side("jab_r")
                        if (now - last_sent.get(act, 0)) >= COOLDOWN_SEC:
                            action = act
                            last_sent[act] = now
                            last_any_action = now

            # ── 3) 회피 (dodge): 고개와 어깨가 함께 확실히 좌/우로 움직일 때만 ──
            if action is None and not guarding and (now - last_any_action) >= DEADZONE_SEC:
                if len(nose_x_hist) >= DODGE_HISTORY and len(shoulder_center_x_hist) >= DODGE_HISTORY:
                    dx_nose = nose_x_hist[-1] - nose_x_hist[-DODGE_HISTORY]
                    dx_shoulder = shoulder_center_x_hist[-1] - shoulder_center_x_hist[-DODGE_HISTORY]
                    if dx_nose < -DODGE_DX_THRESH and dx_shoulder < -DODGE_SHOULDER_MIN:
                        act = game_side("dodge_l")
                        if (now - last_sent.get(act, 0)) >= DODGE_COOLDOWN:
                            action = act
                            last_sent[act] = now
                            last_any_action = now
                    elif dx_nose > DODGE_DX_THRESH and dx_shoulder > DODGE_SHOULDER_MIN:
                        act = game_side("dodge_r")
                        if (now - last_sent.get(act, 0)) >= DODGE_COOLDOWN:
                            action = act
                            last_sent[act] = now
                            last_any_action = now

            # ── 4) 제자리걸음 (jog): 어깨가 위아래로 진동할 때만 (진폭 + 요동 횟수) ──
            if action is None and len(shoulder_y_hist) >= JOG_HISTORY and (now - last_jog_sent) >= JOG_THROTTLE:
                recent_y = list(shoulder_y_hist)[-JOG_HISTORY:]
                y_range = max(recent_y) - min(recent_y)
                deltas = [recent_y[i + 1] - recent_y[i] for i in range(len(recent_y) - 1)]
                sign_changes = sum(
                    1 for i in range(1, len(deltas))
                    if (deltas[i] >= 0) != (deltas[i - 1] >= 0)
                )
                if y_range >= JOG_Y_RANGE_MIN and sign_changes >= JOG_SIGN_CHANGES_MIN:
                    action = "jog"
                    last_jog_sent = now

            if action:
                send(action)

            # ── Pose 스켈레톤 그리기 ───────────────────────────
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

            cv2.imshow("Health Fighter — Pose", frame_small)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            elapsed = time.time() - t0
            time.sleep(max(0.0, 1 / FPS_TARGET - elapsed))

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if getattr(landmarker, "close", None):
            landmarker.close()
        sock.close()
    print("종료.")


if __name__ == "__main__":
    main()
