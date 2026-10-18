# -*- coding: utf-8 -*-
"""v24: 반응 속도 비교. GAP 4프레임과 LSTM 3프레임(그리고 GAP 3프레임)에 대해, 공격 확인 프레임을 2(Precise)와 1(Rapid와 같은 값)로
두었을 때 대기 오발동과 공격 발동 지연을 잰다. 진입 임계값은 Precise 값. 고정 분할(5시드)과 교차검증(5겹). 학습 없음."""
import os, json
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stress_test_v24.py"), encoding="utf8").read()
exec(src[:src.index("rng0 = 2024")])
HERE = os.path.dirname(os.path.abspath(__file__))
R0 = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results"); R1 = os.path.join(HERE, "results"); RC = os.path.join(HERE, "results_groupcv")
VA = json.load(open(os.path.join(R1, "recording_split.json")))["validation_record_ids"]
CONF2 = dict(CONF); CONF1 = dict(CONF); CONF1.update({2: 1, 3: 1, 4: 1, 5: 1})


def simc(P, L, conf):
    act = None; ema = None; cand = None; cnt = 0; ev = []
    for k, p in enumerate(P):
        t = k + L - 1
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= PRECISE[c] and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= PRECISE[c]:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= conf[c]:
                    act = c; ev.append((t, c))
            else:
                cand = None; cnt = 0
    return ev


res = {}
for label, arch, L in [("GAP 4프레임", "gap", 4), ("GAP 3프레임", "gap", 3), ("LSTM 3프레임", "lstm", 3)]:
    for setting in ("fixed", "cv"):
        acc = {"conf2": [0, [], 0, 0], "conf1": [0, [], 0, 0]}
        for f in range(5):
            if setting == "fixed":
                m = tf.keras.models.load_model(os.path.join(R1 if L == 3 else R0, f"model_{arch}_seq{L}_seed{42 + f}.keras"), compile=False); te = VA
            else:
                name = f"{arch}_seq{L}_fold{f}"; te = json.load(open(os.path.join(RC, f"result_{name}.json")))["test_record_ids"]
                m = tf.keras.models.load_model(os.path.join(RC, f"model_{name}.keras"), compile=False)
            none_ids = [x for x in te if meta[x]["label"] == "none"]
            act_ids = [x for x in te if meta[x]["label"] in ("punch_l", "punch_r", "upper_l", "upper_r")]
            Pi = predict_many(m, [frames(x) for x in none_ids], L)
            seqs = [np.concatenate([frames(none_ids[i % len(none_ids)])[-30:], frames(a)[:30]]) for i, a in enumerate(act_ids)]
            Pt = predict_many(m, seqs, L); ys = [C.index(meta[a]["label"]) for a in act_ids]
            for key, conf in (("conf2", CONF2), ("conf1", CONF1)):
                acc[key][0] += sum(1 for Q in Pi for _, c in simc(Q, L, conf) if c in ATT)
                for Q, y in zip(Pt, ys):
                    e = [t for t, c in simc(Q, L, conf) if t >= 30 and c == y]
                    acc[key][3] += 1
                    if e: acc[key][1].append(e[0] - 30)
                    else: acc[key][2] += 1
            tf.keras.backend.clear_session()
        for key in acc:
            fa, on, miss, n = acc[key]
            res[f"{label}|{setting}|{key}"] = {"idle_fa": fa if setting == "cv" else round(fa / 5, 1), "onset_ms": round(float(np.mean(on)) * 1000 / 30, 1),
                                               "onset_frames": round(float(np.mean(on)), 2), "miss_pct": round(100 * miss / n, 1)}
            print(label, setting, key, res[f"{label}|{setting}|{key}"], flush=True)
json.dump(res, open(os.path.join(HERE, "stress_v24", "confirm_latency_v24.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
