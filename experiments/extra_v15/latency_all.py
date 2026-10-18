# -*- coding: utf-8 -*-
"""처리 시간 재측정 (학습이 없는 상태): 분류 모델 11종(배치 1, 시드 3개 x 500회 중앙값)과
MediaPipe Pose Landmarker 경량 모델(비디오 모드)을 640x480, 480x360 입력에서 측정."""
import os, json, time, numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import tensorflow as tf
HERE = os.path.dirname(os.path.abspath(__file__))
R0 = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results"); R1 = os.path.join(HERE, "results")
ROOT = r"C:\Users\User\Documents\body-hero"
out = {"classifier_ms": {}, "mediapipe_ms": {}}
for k, R in [("mlp_seq1", R0), ("gap_seq2", R0), ("gap_seq4", R0), ("gapwide_seq4", R0), ("lstm_seq2", R0), ("lstm_seq4", R0),
             ("gru_seq4", R1), ("gap_seq6", R1), ("gap_seq8", R1), ("lstm_seq6", R1), ("lstm_seq8", R1)]:
    ms = []
    for s in [42, 43, 44]:
        m = tf.keras.models.load_model(os.path.join(R, f"model_{k}_seed{s}.keras"), compile=False); L = m.input_shape[1]
        x = np.random.rand(1, L, 99).astype("float32"); f = tf.function(lambda a: m(a, training=False)); f(x)
        for _ in range(50): f(x)
        ts = []
        for _ in range(500):
            t = time.perf_counter(); f(x); ts.append((time.perf_counter() - t) * 1000)
        ms.append(np.median(ts)); tf.keras.backend.clear_session()
    out["classifier_ms"][k] = round(float(np.median(ms)), 3); print(k, out["classifier_ms"][k], flush=True)
import mediapipe as mp, cv2
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
out["mediapipe_version"] = mp.__version__
for W, Hh in [(640, 480), (480, 360)]:
    opts = vision.PoseLandmarkerOptions(base_options=mpp.BaseOptions(model_asset_path=os.path.join(ROOT, "tools", "pose_landmarker.task")),
                                        running_mode=vision.RunningMode.VIDEO, num_poses=1)
    det = vision.PoseLandmarker.create_from_options(opts); k = 0; allt = []
    for fimg in ["PUNCH_L.png", "GUARD.png"]:
        img = cv2.resize(cv2.imread(os.path.join(ROOT, "docs", "figures", fimg)), (W, Hh))
        mi = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ts = []; found = 0
        for i in range(120):
            t = time.perf_counter(); k += 1; r = det.detect_for_video(mi, k * 33); ts.append((time.perf_counter() - t) * 1000); found += len(r.pose_landmarks) > 0
        allt += ts[20:]; print(W, Hh, fimg, "found", found, flush=True)
    det.close()
    out["mediapipe_ms"][f"{W}x{Hh}"] = {"median": round(float(np.median(allt)), 2), "p95": round(float(np.percentile(allt, 95)), 2)}
    print(W, Hh, out["mediapipe_ms"][f"{W}x{Hh}"], flush=True)
json.dump(out, open(os.path.join(HERE, "latency_all.json"), "w"), indent=1)
