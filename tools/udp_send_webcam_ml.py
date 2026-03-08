"""
웹캠 + MediaPipe Pose → 어깨 너비 정규화 → Flask ML 서버 판정 → Godot에 UDP 액션 전송.
기존 threshold 방식(udp_send_webcam.py) 대신 딥러닝 모델로 jab_l, jab_r, upper_l, upper_r, guard 판정.

사용 순서:
  1) 데이터 수집: python collect_pose_data.py
  2) 학습: python train_pose_classifier.py
  3) 서버 실행: python pose_server.py  (백그라운드)
  4) 본 스크립트 실행: python udp_send_webcam_ml.py
  5) Godot 실행 후 플레이
"""
import os
import time
import socket
import urllib.request
import urllib.error
import json

os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 4242
PREDICT_URL = "http://127.0.0.1:5000/predict"
COOLDOWN_SEC = 0.35
GUARD_EXIT_FRAMES = 4
FPS_TARGET = 30
PROCESS_W, PROCESS_H = 640, 480
# 어깨 중심이 이 구역 안에 있을 때만 액션 인정 (시연 시 다른 사람 무시)
CENTER_ZONE_X = (0.2, 0.8)  # normalized [0,1] 기준
CENTER_ZONE_Y = (0.2, 0.8)
# 연속 이 프레임 수만큼 중앙 구역에 있어야 게임 입력 사용 (지나가는 사람 1~2프레임만 잡히면 무시)
CENTER_ZONE_FRAMES = 5

try:
    import cv2
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core import image as mp_core_image
except ImportError:
    print("pip install mediapipe opencv-python")
    raise SystemExit(1)

from pose_normalize import normalize_landmarks_flat, shoulder_center_and_width

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


def predict_action(landmarks_flat):
    """Flask 서버에 랜드마크 전송 후 (액션, 확신도) 반환. 실패 시 (None, 0.0)."""
    try:
        req = urllib.request.Request(
            PREDICT_URL,
            data=json.dumps({"landmarks": landmarks_flat}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result"), float(data.get("confidence", 0.0))
    except Exception:
        return None, 0.0


def main():
    _download_pose_model()
    from mediapipe.tasks import python as mp_tasks
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

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("웹캠을 열 수 없습니다.")
        return

    last_action_time = 0.0
    guarding = False
    guard_exit_count = 0
    frame_idx = 0
    consecutive_in_zone = 0

    print("웹캠 + ML 판정 → Godot UDP")
    print("pose_server.py 가 먼저 실행 중이어야 합니다 (포트 5000).")
    print("종료: Q 키 또는 Ctrl+C\n")

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
            frame_small = cv2.resize(frame, (PROCESS_W, PROCESS_H))
            rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            ts_ms = int(frame_idx * 1000 / FPS_TARGET)
            frame_idx += 1
            result = landmarker.detect_for_video(make_mp_image(rgb), ts_ms)

            action = None
            lm = None
            pred = None
            confidence = 0.0
            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm = result.pose_landmarks[0]
                (cx, cy), _ = shoulder_center_and_width(lm)
                in_zone = (CENTER_ZONE_X[0] <= cx <= CENTER_ZONE_X[1] and
                           CENTER_ZONE_Y[0] <= cy <= CENTER_ZONE_Y[1])
                if in_zone:
                    consecutive_in_zone += 1
                    if consecutive_in_zone >= CENTER_ZONE_FRAMES:
                        flat = normalize_landmarks_flat(lm)
                        pred, confidence = predict_action(flat)
                else:
                    consecutive_in_zone = 0
                # 구역 밖이거나 연속 N프레임 미달이면 pred 없음 → 지나가는 사람 1~2프레임만 잡혀도 무시
                now = time.time()

                if pred == "guard":
                    guard_exit_count = 0
                    if not guarding and (now - last_action_time) >= 0.15:
                        action = "guard"
                        guarding = True
                        last_action_time = now
                else:
                    if guarding:
                        guard_exit_count += 1
                        if guard_exit_count >= GUARD_EXIT_FRAMES:
                            action = "guard_end"
                            guarding = False
                            last_action_time = now
                    if action is None and pred in ("jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"):
                        if (now - last_action_time) >= COOLDOWN_SEC:
                            action = pred
                            last_action_time = now

            if action:
                send(action)

            # 화면에 현재 판정 + 확신도 표시 (졸업 시연 시 가독성)
            pred_display = pred if pred else "none"
            conf_display = confidence if pred else 0.0
            cv2.putText(frame_small, f"ML: {pred_display} ({conf_display:.0%})", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 2)

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

            cv2.imshow("Body Hero — ML Pose", frame_small)
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
