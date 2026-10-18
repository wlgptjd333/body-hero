# -*- coding: utf-8 -*-
"""기존 4프레임 모델에 창 안의 프레임 순서를 뒤집거나 섞은 입력을 넣어 정확도 변화를 본다. 학습 없음.
순서를 바꿔도 정확도가 같으면 모델이 순서 정보에 거의 의존하지 않는다는 뜻이다."""
import os, json, numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import tensorflow as tf
tf.config.threading.set_intra_op_parallelism_threads(2)
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results")
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X_all = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
va = json.load(open(os.path.join(R, "recording_split.json")))["validation_record_ids"]
X, y = [], []
for r in va:
    F = X_all[meta[r]["start_index"]:meta[r]["start_index"] + meta[r]["frame_count"]]
    for t in range(3, len(F)):
        X.append(F[t - 3:t + 1]); y.append(C.index(meta[r]["label"]))
X = np.asarray(X); y = np.asarray(y)
rng = np.random.default_rng(0)
perm = np.stack([rng.permutation(4) for _ in range(len(X))])
Xs = np.take_along_axis(X, perm[:, :, None], axis=1)
out = {}
for key in ["gap_seq4", "gapwide_seq4", "lstm_seq4"]:
    accs = {"원래 순서": [], "역순": [], "무작위 순서": [], "마지막 프레임 4번 복제": []}
    for s in range(42, 47):
        m = tf.keras.models.load_model(os.path.join(R, f"model_{key}_seed{s}.keras"), compile=False)
        for name, Z in [("원래 순서", X), ("역순", X[:, ::-1]), ("무작위 순서", Xs), ("마지막 프레임 4번 복제", np.repeat(X[:, -1:], 4, axis=1))]:
            accs[name].append(float((m.predict(Z, batch_size=4096, verbose=0).argmax(1) == y).mean()))
        tf.keras.backend.clear_session()
    out[key] = {k: [round(float(np.mean(v)) * 100, 2), round(float(np.std(v, ddof=1)) * 100, 2)] for k, v in accs.items()}
    print(key, out[key], flush=True)
json.dump(out, open(os.path.join(HERE, "order_test.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
