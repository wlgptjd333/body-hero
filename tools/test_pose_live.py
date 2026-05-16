"""
학습된 시퀀스 포즈 분류 모델로 웹캠 실시간 테스트.
연속 시퀀스 버퍼로 예측. 뼈대 + 현재 동작 표시 (none=하얀색, 그 외=초록색).

실행: cd tools → python test_pose_live.py [--camera-index 1] [--camera-backend dshow]
종료: Q
"""
import argparse
import os
import time

os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
from pose_class_names import POSE_CLASS_NAMES

_MODEL_SEQ_4 = os.path.join(SCRIPT_DIR, "pose_classifier_seq_len4.keras")
_MODEL_SEQ_8 = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
DEFAULT_MODEL = _MODEL_SEQ_4 if os.path.isfile(_MODEL_SEQ_4) else _MODEL_SEQ_8
SEQ_LEN = 4 if DEFAULT_MODEL == _MODEL_SEQ_4 else 8
CLASS_NAMES = list(POSE_CLASS_NAMES)
PROCESS_W, PROCESS_H = 640, 480
FPS_TARGET = 30
CONFIDENCE_THRESHOLD = 0.93
UPPER_AND_PUNCH_CONFIDENCE_THRESHOLD = 0.88

try:
    import cv2
    import numpy as np
    import tensorflow as tf
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core import image as mp_core_image
except ImportError as e:
    print("pip install opencv-python numpy tensorflow mediapipe")
    raise SystemExit(1) from e

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
    parser = argparse.ArgumentParser(description="학습된 시퀀스 모델로 웹캠 실시간 테스트")
    parser.add_argument("--camera-index", type=int, default=0, metavar="N", help="OpenCV 카메라 인덱스 (기본 0)")
    parser.add_argument(
        "--camera-backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windows USB 인식 문제 시 dshow 권장",
    )
    args = parser.parse_args()

    _download_pose_model()

    if not os.path.isfile(DEFAULT_MODEL):
        print("모델 파일 없음. 먼저 python train_pose_classifier_seq.py 로 학습하세요.")
        raise SystemExit(1)
    model = tf.keras.models.load_model(DEFAULT_MODEL)
    inp = model.input_shape
    if isinstance(inp, (list, tuple)) and len(inp) >= 2 and inp[1] is not None:
        SEQ_LEN = int(inp[1])
    print(f"시퀀스 모델 로드: {DEFAULT_MODEL} (seq_len={SEQ_LEN})")

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
        print("웹캠을 열 수 없습니다. --camera-index / --camera-backend 를 조정해 보세요.")
        return
    print(f"카메라: index={args.camera_index}, backend={args.camera_backend} → {cap_backend_label}")

    frame_idx = 0
    sequence_buffer = []
    print(f"실시간 포즈 테스트 (시퀀스 {SEQ_LEN}프레임) — 뼈대 + 현재 동작 표시")
    print("none = 하얀색, 그 외 = 초록색 | 종료: Q\n")

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
            pred_label = "none"
            confidence = 0.0
            lm = None

            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm = result.pose_landmarks[0]
                flat = normalize_landmarks_flat(lm)
                sequence_buffer.append(flat)
                if len(sequence_buffer) > SEQ_LEN:
                    sequence_buffer.pop(0)
                if len(sequence_buffer) == SEQ_LEN:
                    X = np.array(sequence_buffer, dtype=np.float32).reshape(1, SEQ_LEN, -1)
                    pred = model.predict(X, verbose=0)[0]
                    idx = int(np.argmax(pred))
                    conf = float(pred[idx])
                    lbl = CLASS_NAMES[idx]
                    need = (
                        UPPER_AND_PUNCH_CONFIDENCE_THRESHOLD
                        if lbl in ("upper_l", "upper_r", "punch_l", "punch_r")
                        else CONFIDENCE_THRESHOLD
                    )
                    if conf >= need:
                        pred_label = lbl
                        confidence = conf
                    else:
                        pred_label = "none"
            else:
                sequence_buffer.clear()

            # 상단에 현재 동작 크게 표시: none=하얀색, 그 외=초록색
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 1.8
            thickness = 4
            (tw, th), _ = cv2.getTextSize(pred_label, font, font_scale, thickness)
            x_label = (frame_small.shape[1] - tw) // 2
            y_label = 55
            if pred_label == "none":
                color = (255, 255, 255)  # BGR 하얀색
            else:
                color = (0, 255, 0)  # BGR 초록색
            cv2.putText(frame_small, pred_label, (x_label, y_label), font, font_scale, color, thickness)
            if pred_label != "none":
                cv2.putText(frame_small, f"{confidence:.0%}", (x_label + tw + 15, y_label), font, 0.7, color, 2)

            # 뼈대 그리기 (녹화할 때와 동일)
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

            cv2.imshow("Pose Test — Live", frame_small)
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
    print("종료.")


if __name__ == "__main__":
    main()
