# -*- coding: utf-8 -*-
"""게임 배포 모델(gap_g_seed44.keras, 릴리스 v1.0.0과 동일 파일)을 학습 때와 같은 분할(시드 44)의 검증 녹화본으로 평가해 결과를 파일로 남긴다."""
import os, sys, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np, tensorflow as tf
from sklearn.metrics import f1_score, confusion_matrix
TOOLS = r"C:\Users\User\Documents\body-hero\tools"
sys.path.insert(0, os.path.join(TOOLS, "thesis_experiments")); sys.path.insert(0, TOOLS)
from pose_class_names import POSE_CLASS_NAMES
from train_recording_holdout_experiment import split_recordings_stratified, extract_sequences_from_recordings
C = list(POSE_CLASS_NAMES)
data = json.load(open(os.path.join(TOOLS, "pose_data.json"), encoding="utf8"))
rec = json.load(open(os.path.join(TOOLS, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
tr, va = split_recordings_stratified(rec, C, .2, 44)
xv, yv = extract_sequences_from_recordings(data, va, C, 4, skip_labels=["drop"])
V = np.asarray(xv, np.float32); y = np.asarray([C.index(z) for z in yv])
m = tf.keras.models.load_model(os.path.join(TOOLS, "game_model_test", "gap_g_seed44.keras"), compile=False)
p = m.predict(V, batch_size=4096, verbose=0).argmax(1)
cm = confusion_matrix(y, p, labels=range(7))
punch = [C.index("punch_l"), C.index("punch_r")]
out = dict(classes=C, val_recordings=len(va), val_sequences=int(len(y)), accuracy=float((p == y).mean()),
           macro_f1=float(f1_score(y, p, average="macro")), confusion=cm.tolist(),
           punch_to_none=int(sum(cm[k, C.index("none")] for k in punch)), params=int(m.count_params()))
print(json.dumps({k: v for k, v in out.items() if k != "confusion"}, ensure_ascii=False))
json.dump(out, open("eval_deployed.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
