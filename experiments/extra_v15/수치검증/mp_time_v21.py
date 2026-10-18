# -*- coding: utf-8 -*-
"""포즈 추정 처리 시간 재측정(결과를 파일로 남김). 사람이 검출되는 640x480 이미지(docs/figures/PUNCH_L.png)를
MediaPipe Pose Landmarker 경량 모델(비디오 모드)에 120회 연속 입력, 처음 20회 제외. 같은 절차를 3번 반복."""
import os, json, time, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
ROOT = r"C:\Users\User\Documents\body-hero"
img = cv2.resize(cv2.imread(os.path.join(ROOT, "docs", "figures", "PUNCH_L.png")), (640, 480))
mi = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
runs = []
for rep in range(3):
    det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpp.BaseOptions(model_asset_path=os.path.join(ROOT, "tools", "pose_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_poses=1))
    ts = []; found = []
    for i in range(120):
        t = time.perf_counter(); r = det.detect_for_video(mi, (i + 1) * 33); ts.append((time.perf_counter() - t) * 1000)
        found.append(len(r.pose_landmarks) > 0)
    det.close()
    t = np.array(ts[20:]); f = np.array(found[20:])
    runs.append(dict(median_all=float(np.median(t)), p95_all=float(np.percentile(t, 95)), found=int(f.sum()),
                     median_found=float(np.median(t[f])) if f.any() else None))
    print(rep, runs[-1], flush=True)
allm = [r["median_all"] for r in runs]
out = dict(mediapipe=mp.__version__, image="PUNCH_L.png 640x480", runs=runs, median_of_runs=float(np.median(allm)),
           p95_of_runs=float(np.median([r["p95_all"] for r in runs])))
print(out); json.dump(out, open("mp_time_v21.json", "w"), indent=1)
