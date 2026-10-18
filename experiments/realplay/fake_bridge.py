# -*- coding: utf-8 -*-
"""웹캠 없이 실험 도구를 시험하기 위한 가짜 인식 모듈.
실험 화면이 state 파일에 적는 현재 지시(대기/동작)에 맞춰, 수집 데이터(pose_data.json)의 녹화본 좌표를
실제 인식 모듈과 같은 형식으로 기록하고, 배포 모델과 Precise 후처리로 판정해 UDP 4242로 보낸다.
시험용이며 실험 결과로 쓰지 않는다."""
import argparse, json, os, random, socket, sys, time
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--log", required=True)
ap.add_argument("--state", required=True)
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--model", default=L.MODELS["deployed"][1][0])
a = ap.parse_args()

import tensorflow as tf
model = tf.keras.models.load_model(a.model, compile=False)
SEQ = model.input_shape[1]
pose = json.load(open(os.path.join(L.TOOLS, "pose_data.json"), encoding="utf8"))
X = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(L.TOOLS, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
by = {}
for r in meta:
    by.setdefault(r["label"], []).append(X[r["start_index"]:r["start_index"] + r["frame_count"]])
rng = random.Random(7)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
log = open(a.log, "a", encoding="utf-8")


def w(k, i, d=None):
    rec = {"k": k, "t": time.perf_counter(), "i": i}
    if d is not None:
        rec["d"] = d
    log.write(json.dumps(rec, separators=(",", ":")) + "\n")


class Sim:  # lab_common.sim과 같은 규칙을 한 프레임씩 적용
    def __init__(self):
        self.act = None; self.ema = None; self.cand = None; self.cnt = 0

    def step(self, p):
        self.ema = p.copy() if self.ema is None else .7 * p + .3 * self.ema
        c = int(p.argmax()); out = None
        if self.act is not None:
            if not (self.ema[self.act] >= 0.60 and not (c != self.act and p[c] >= L.PRECISE[c] and p[c] > self.ema[self.act] + 0.05)):
                self.act = None
        if self.act is None:
            if p[c] >= L.PRECISE[c]:
                self.cnt = self.cnt + 1 if self.cand == c else 1; self.cand = c
                if self.cnt >= L.CONF[c]:
                    self.act = c; out = c
            else:
                self.cand = None; self.cnt = 0
        return out


print("가짜 인식 모듈 시작 (시험용)", flush=True)
time.sleep(1.0 / a.speed)
sim = Sim(); buf = []; i = 0; cur_label = None; src = None; pos = 0; combo_n = 0; prev_raw = None
dt = 1.0 / (30.0 * a.speed)
nxt = time.perf_counter()
while True:
    try:
        st = json.load(open(a.state, encoding="utf-8"))
    except Exception:
        st = {"label": "none"}
    if st.get("quit"):
        break
    lab = st.get("label", "none")
    if lab == "combo":
        combo_n = combo_n + 1 if prev_raw == "combo" else 0
        lab = "punch_l" if combo_n < 12 else ("punch_r" if combo_n < 24 else "none")
    prev_raw = st.get("label", "none")
    if lab != cur_label:
        cur_label = lab; src = rng.choice(by[lab if lab in by else "none"]); pos = 0
    f = src[pos % len(src)]; pos += 1
    i += 1; w("f", i)
    w("a", i, [round(float(v), 5) for v in f])
    buf.append(f); buf = buf[-SEQ:]
    if len(buf) == SEQ:
        p = model(np.asarray(buf, np.float32)[None], training=False).numpy()[0]
        c = sim.step(p)
        if c is not None and c != 0:
            name = L.C[c]
            sock.sendto(name.encode("utf-8"), ("127.0.0.1", 4242)); w("s", -1, name)
    if i % 30 == 0:
        log.flush()
    nxt += dt
    time.sleep(max(0.0, nxt - time.perf_counter()))
log.close()
