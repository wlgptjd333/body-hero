# -*- coding: utf-8 -*-
# v23: latency_all.py의 분류 시간 측정 부분만 3프레임 모델에 적용 (비교용으로 2·4프레임도 같은 시간대에 다시 측정)
"""처리 시간 재측정 (학습이 없는 상태): 분류 모델 11종(배치 1, 시드 3개 x 500회 중앙값)과
MediaPipe Pose Landmarker 경량 모델(비디오 모드)을 640x480, 480x360 입력에서 측정."""
import os, json, time, numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import tensorflow as tf
HERE = os.path.dirname(os.path.abspath(__file__))
R0 = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results"); R1 = os.path.join(HERE, "results")
ROOT = r"C:\Users\User\Documents\body-hero"
out = {"classifier_ms": {}, "mediapipe_ms": {}}
for k, R in [("gap_seq4", R0), ("lstm_seq4", R0), ("gap_seq3", R1), ("lstm_seq3", R1), ("gap_seq2", R0), ("lstm_seq2", R0)]:
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
json.dump(out, open(os.path.join(HERE, "eval_v23", "latency_seq3_v23.json"), "w"), indent=1)
