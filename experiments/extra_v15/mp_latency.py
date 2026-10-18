# -*- coding: utf-8 -*-
"""MediaPipe Pose Landmarker(경량, 비디오 모드) 처리 시간: 사람이 검출되는 이미지만 써서 640x480과 480x360을 번갈아 측정."""
import os, json, time, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
ROOT = r"C:\Users\User\Documents\body-hero"; HERE = os.path.dirname(os.path.abspath(__file__))
imgs = ["NONE.png", "GUARD.png", "PUNCH_L.png", "PUNCH_R.png", "UPPER_L.png", "UPPER_R.png", "SQUAT.png"]
res = {}
for rep in range(2):
    for W, Hh in [(640, 480), (480, 360)]:
        det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=os.path.join(ROOT, "tools", "pose_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO, num_poses=1))
        k = 0
        for f in imgs:
            img = cv2.resize(cv2.imread(os.path.join(ROOT, "docs", "figures", f)), (W, Hh))
            mi = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            ts = []; found = 0
            for i in range(120):
                t = time.perf_counter(); k += 1; r = det.detect_for_video(mi, k * 33); ts.append((time.perf_counter() - t) * 1000); found += len(r.pose_landmarks) > 0
            if found == 120:
                res.setdefault(f"{W}x{Hh}", []).extend(ts[20:])
            print(rep, W, Hh, f, "found", found, "median %.2f" % np.median(ts[20:]), flush=True)
        det.close()
out = {k: {"median": round(float(np.median(v)), 2), "p95": round(float(np.percentile(v, 95)), 2), "n": len(v)} for k, v in res.items()}
out["mediapipe_version"] = mp.__version__
print(out); json.dump(out, open(os.path.join(HERE, "mp_latency.json"), "w"), indent=1)
