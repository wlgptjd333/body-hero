# -*- coding: utf-8 -*-
"""v24: GAP 4프레임의 공격 확인 프레임을 1로 줄였을 때(빠른 반응), 실전형 변형(1~2프레임 끼어듦, 중간 자세)에 대한 강건성이
LSTM 3프레임(확인 2프레임)과 비교해 어떤지 본다. confirm_latency_v24.py와 stress_test_v24.py의 정의를 그대로 사용. 학습 없음."""
import os, json
H0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H0, "confirm_latency_v24.py"), encoding="utf8").read()
exec(src[:src.index("res = {}")])
res = {}
for label, arch, L, conf in [("GAP 4프레임, 확인 2", "gap", 4, CONF2), ("GAP 4프레임, 확인 1", "gap", 4, CONF1),
                             ("LSTM 3프레임, 확인 2", "lstm", 3, CONF2), ("LSTM 3프레임, 확인 1", "lstm", 3, CONF1)]:
    for setting in ("fixed", "cv"):
        a = {"intrude1": 0, "intrude2": 0, "interp4": [0, 0, 0], "interp8": [0, 0, 0]}
        for f in range(5):
            if setting == "fixed":
                m = tf.keras.models.load_model(os.path.join(R1 if L == 3 else R0, f"model_{arch}_seq{L}_seed{42 + f}.keras"), compile=False); te = VA
            else:
                name = f"{arch}_seq{L}_fold{f}"; te = json.load(open(os.path.join(RC, f"result_{name}.json")))["test_record_ids"]
                m = tf.keras.models.load_model(os.path.join(RC, f"model_{name}.keras"), compile=False)
            none_ids = [x for x in te if meta[x]["label"] == "none"]
            act_ids = [x for x in te if meta[x]["label"] in ("punch_l", "punch_r", "upper_l", "upper_r")]
            for k in (1, 2):
                g = []
                for i, x in enumerate(none_ids):
                    q = frames(x).copy(); q[30:30 + k] = frames(act_ids[i % len(act_ids)])[30:30 + k]; g.append(q)
                a[f"intrude{k}"] += sum(1 for Q in predict_many(m, g, L) for _, c in simc(Q, L, conf) if c in ATT)
            for mm in (4, 8):
                seqs = []; ys = []
                for i, x in enumerate(act_ids):
                    n0 = frames(none_ids[i % len(none_ids)]); A = frames(x)
                    al = (np.arange(1, mm + 1) / (mm + 1))[:, None]
                    seqs.append(np.concatenate([n0[-30:], (1 - al) * n0[-1] + al * A[0], A[:20], (1 - al) * A[19] + al * n0[0], n0[:30]]).astype(np.float32))
                    ys.append(C.index(meta[x]["label"]))
                for Q, y in zip(predict_many(m, seqs, L), ys):
                    ev = [(t, c) for t, c in simc(Q, L, conf) if t >= 30 and c in ATT]
                    a[f"interp{mm}"][2] += 1
                    if ev and ev[0][1] == y: a[f"interp{mm}"][0] += 1
                    elif ev: a[f"interp{mm}"][1] += 1
            tf.keras.backend.clear_session()
        d = 5 if setting == "fixed" else 1
        out = {k: round(a[k] / d, 1) for k in ("intrude1", "intrude2")}
        for mm in (4, 8):
            h, w, n = a[f"interp{mm}"]; out[f"interp{mm}_hit_pct"] = round(100 * h / n, 1); out[f"interp{mm}_wrong_pct"] = round(100 * w / n, 1)
        res[f"{label}|{setting}"] = out; print(label, setting, out, flush=True)
json.dump(res, open(os.path.join(H0, "stress_v24", "confirm_stress_v24.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
