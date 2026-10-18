# -*- coding: utf-8 -*-
"""v24: 실전 조건을 흉내 낸 강건성 시험 (학습 없음).
묶음 단위 5겹 교차검증의 저장 모델로, 각 겹의 '처음 보는' 시험 녹화본에 실제 플레이에서 생길 수 있는 변형을 가한다.
  1) 순간 튐: 대기 녹화본 중간 1~2프레임에 큰 잡음(σ=0.3)을 더함 (포즈 추정 순간 오류)
  2) 순간 끼어듦: 대기 녹화본 중간 1~2프레임을 공격 자세로 바꿈 (짧은 팔 움직임·오검출)
  3) 좌표 흔들림: 모든 프레임에 가우시안 잡음 σ=0.03, 0.06, 0.10 (빠른 동작·화질 저하로 추정이 흔들림)
  4) 몸 돌림: x 좌표에 cos(20°), cos(40°)를 곱한 뒤 어깨 너비로 다시 정규화
  5) 프레임률 저하: 프레임을 하나 걸러 사용 (15 FPS)
  6) 짧은 공격: 대기 → 공격 자세 k프레임(k=3,4,5,6,8) → 대기 (정점 자세가 짧게만 유지되는 실제 펀치)
  7) 중간 자세: 대기와 공격 자세 사이를 m프레임(m=4, 8) 선형 보간으로 이어 붙임 (실제 동작의 궤적 근사)
후처리는 게임 기본값(Precise)과, 모든 동작에 같은 진입 임계값 0.95를 쓰는 경우를 함께 본다."""
import os, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"; os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import tensorflow as tf
tf.config.threading.set_intra_op_parallelism_threads(4)

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results_groupcv")
OUT = os.path.join(HERE, "stress_v24"); os.makedirs(OUT, exist_ok=True)
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
ATT = {2, 3, 4, 5}
PRECISE = {0: .95, 1: .95, 2: .88, 3: .88, 4: .90, 5: .90, 6: .95}
U95 = {k: .95 for k in range(7)}
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}
pose = json.load(open(os.path.join(T, "pose_data.json"), encoding="utf8"))
X_all = np.asarray([p["landmarks"] for p in pose], np.float32)
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
MODELS = [("GAP 4프레임", "gap", 4), ("GAP 3프레임", "gap", 3), ("LSTM 3프레임", "lstm", 3),
          ("LSTM 4프레임", "lstm", 4), ("LSTM 2프레임", "lstm", 2), ("MLP 1프레임", "mlp", 1)]


def frames(rid):
    r = meta[rid]; return X_all[r["start_index"]:r["start_index"] + r["frame_count"]]


def windows(seq, L):
    return np.stack([seq[t - L + 1:t + 1] for t in range(L - 1, len(seq))])


def sim(P, L, thr):
    act = None; ema = None; cand = None; cnt = 0; ev = []
    for k, p in enumerate(P):
        t = k + L - 1
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= thr[c] and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= thr[c]:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= CONF[c]:
                    act = c; ev.append((t, c))
            else:
                cand = None; cnt = 0
    return ev


def renorm(seq):
    s = seq.copy()
    dx = s[:, 36] - s[:, 33]; dy = s[:, 37] - s[:, 34]
    w = np.maximum(np.hypot(dx, dy), 1e-5)[:, None]
    cx = (s[:, 33] + s[:, 36]) / 2; cy = (s[:, 34] + s[:, 37]) / 2
    s[:, 0::3] -= cx[:, None]; s[:, 1::3] -= cy[:, None]
    return s / w


def yaw(seq, deg):
    s = seq.copy(); s[:, 0::3] *= np.cos(np.radians(deg)); return renorm(s)


def predict_many(m, seqs, L):
    ws = [windows(q, L) for q in seqs]
    P = m.predict(np.concatenate(ws), batch_size=4096, verbose=0)
    out = []; i = 0
    for w in ws:
        out.append(P[i:i + len(w)]); i += len(w)
    return out


def idle_fa(m, L, seqs):
    P = predict_many(m, seqs, L)
    return {name: sum(1 for Q in P for _, c in sim(Q, L, thr) if c in ATT) for name, thr in [("precise", PRECISE), ("u95", U95)]}


def win_acc(m, L, seqs, labels):
    P = predict_many(m, seqs, L)
    ok = sum(int((Q.argmax(1) == y).sum()) for Q, y in zip(P, labels)); n = sum(len(Q) for Q in P)
    return ok / n


def trans(m, L, seqs, ys, start, fps=30):
    """seqs: 대기 → 공격 → 대기 시퀀스. start: 공격 구간이 시작하는 프레임 번호.
    적중 = 공격 시작 이후 정답 공격이 발동, 오답 = 공격 시작 이후 다른 공격이 정답보다 먼저 발동."""
    P = predict_many(m, seqs, L)
    res = {}
    for name, thr in [("precise", PRECISE), ("u95", U95)]:
        hit = 0; wrong = 0; lat = []; n = 0
        for Q, y in zip(P, ys):
            if y not in ATT: continue
            n += 1
            ev = [(t, c) for t, c in sim(Q, L, thr) if t >= start and c in ATT]
            if ev and ev[0][1] == y:
                hit += 1; lat.append(ev[0][0] - start)
            elif ev:
                wrong += 1
        res[name] = {"hit_pct": round(100 * hit / n, 1), "wrong_first_pct": round(100 * wrong / n, 1),
                     "onset_ms": round(float(np.mean(lat)) * 1000 / fps, 1) if lat else None, "n": n}
    return res


rng0 = 2024
result = {}
for label, arch, L in MODELS:
    agg = {}
    for f in range(5):
        name = f"{arch}_seq{L}_fold{f}"
        r = json.load(open(os.path.join(R, f"result_{name}.json"))); te = r["test_record_ids"]
        m = tf.keras.models.load_model(os.path.join(R, f"model_{name}.keras"), compile=False)
        rng = np.random.default_rng(rng0 + f)
        none_ids = [x for x in te if meta[x]["label"] == "none"]
        act_ids = [x for x in te if meta[x]["label"] in ("punch_l", "punch_r", "upper_l", "upper_r")]
        idle = [frames(x) for x in none_ids]
        allrec = [frames(x) for x in te]; alllab = [C.index(meta[x]["label"]) for x in te]
        cur = {}
        cur["clean_idle_fa"] = idle_fa(m, L, idle)
        # 1) 순간 튐, 2) 순간 끼어듦
        for k in (1, 2):
            g = []
            for q in idle:
                q = q.copy(); q[30:30 + k] += rng.normal(0, 0.3, q[30:30 + k].shape).astype(np.float32); g.append(q)
            cur[f"glitch{k}_idle_fa"] = idle_fa(m, L, g)
            g = []
            for i, q in enumerate(idle):
                a = frames(act_ids[i % len(act_ids)]); q = q.copy(); q[30:30 + k] = a[30:30 + k]; g.append(q)
            cur[f"intrude{k}_idle_fa"] = idle_fa(m, L, g)
        # 3) 좌표 흔들림
        for s in (0.03, 0.06, 0.10):
            jit = [q + rng.normal(0, s, q.shape).astype(np.float32) for q in allrec]
            cur[f"jitter{s}_acc"] = win_acc(m, L, jit, alllab)
            cur[f"jitter{s}_idle_fa"] = idle_fa(m, L, [q + rng.normal(0, s, q.shape).astype(np.float32) for q in idle])
            seqs = [np.concatenate([frames(none_ids[i % len(none_ids)])[-30:], frames(a)[:30], frames(none_ids[i % len(none_ids)])[:30]]) for i, a in enumerate(act_ids)]
            seqs = [q + rng.normal(0, s, q.shape).astype(np.float32) for q in seqs]
            cur[f"jitter{s}_trans"] = trans(m, L, seqs, [C.index(meta[a]["label"]) for a in act_ids], 30)
        # 4) 몸 돌림
        for d in (20, 40):
            cur[f"yaw{d}_acc"] = win_acc(m, L, [yaw(q, d) for q in allrec], alllab)
            cur[f"yaw{d}_idle_fa"] = idle_fa(m, L, [yaw(q, d) for q in idle])
        # 5) 15 FPS
        cur["fps15_acc"] = win_acc(m, L, [q[::2] for q in allrec], alllab)
        cur["fps15_idle_fa"] = idle_fa(m, L, [q[::2] for q in idle])
        seqs = [np.concatenate([frames(none_ids[i % len(none_ids)])[-30:], frames(a)[:30], frames(none_ids[i % len(none_ids)])[:30]])[::2] for i, a in enumerate(act_ids)]
        cur["fps15_trans"] = trans(m, L, seqs, [C.index(meta[a]["label"]) for a in act_ids], 15, fps=15)
        # 기준: 계단식 전환 (깨끗한 입력)
        seqs = [np.concatenate([frames(none_ids[i % len(none_ids)])[-30:], frames(a)[:30], frames(none_ids[i % len(none_ids)])[:30]]) for i, a in enumerate(act_ids)]
        cur["step_trans"] = trans(m, L, seqs, [C.index(meta[a]["label"]) for a in act_ids], 30)
        # 6) 짧은 공격
        for k in (3, 4, 5, 6, 8):
            seqs = [np.concatenate([frames(none_ids[i % len(none_ids)])[-30:], frames(a)[:k], frames(none_ids[i % len(none_ids)])[:30]]) for i, a in enumerate(act_ids)]
            cur[f"brief{k}_trans"] = trans(m, L, seqs, [C.index(meta[a]["label"]) for a in act_ids], 30)
        # 7) 중간 자세(선형 보간)
        for mm in (4, 8):
            seqs = []
            for i, a in enumerate(act_ids):
                n0 = frames(none_ids[i % len(none_ids)]); A = frames(a)
                al = (np.arange(1, mm + 1) / (mm + 1))[:, None]
                up = (1 - al) * n0[-1] + al * A[0]; down = (1 - al) * A[19] + al * n0[0]
                seqs.append(np.concatenate([n0[-30:], up, A[:20], down, n0[:30]]).astype(np.float32))
            cur[f"interp{mm}_trans"] = trans(m, L, seqs, [C.index(meta[a]["label"]) for a in act_ids], 30)
        tf.keras.backend.clear_session()
        agg[f] = cur
        print(label, f, flush=True)
    result[label] = agg
json.dump(result, open(os.path.join(OUT, "stress_v24_raw.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("done")
