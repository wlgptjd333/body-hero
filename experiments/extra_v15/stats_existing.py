# -*- coding: utf-8 -*-
"""기존 30개 모델(재실험_2x2_증강수정)의 저장 예측으로 통계 재검토. 학습 없음.
(1) 녹화본 단위 부트스트랩으로 정확도 차이의 95% 구간, (2) 오발동이 어느 녹화본에서 나는지."""
import os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "재실험_2x2_증강수정", "results")
T = r"C:\Users\User\Documents\body-hero\tools"
C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
meta = json.load(open(os.path.join(T, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
va = json.load(open(os.path.join(R, "recording_split.json")))["validation_record_ids"]
ATT = {2, 3, 4, 5}
THR = {0: .95, 1: .95, 2: .88, 3: .88, 4: .90, 5: .90, 6: .95}
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}

def sim(P, thr):
    act = None; ema = None; cand = None; cnt = 0; ev = []
    for k, p in enumerate(P):
        ema = p.copy() if ema is None else .7 * p + .3 * ema
        c = int(p.argmax())
        if act is not None:
            if not (ema[act] >= 0.60 and not (c != act and p[c] >= thr[c] and p[c] > ema[act] + 0.05)):
                act = None
        if act is None:
            if p[c] >= thr[c]:
                cnt = cnt + 1 if cand == c else 1; cand = c
                if cnt >= CONF[c]:
                    act = c; ev.append((k, c))
            else:
                cand = None; cnt = 0
    return ev

def per_rec(key, seed):
    L = int(key.split("seq")[1])
    P = np.load(os.path.join(R, f"probabilities_{key}_seed{seed}.npy"))
    out = {}; i = 0
    for r in va:
        n = meta[r]["frame_count"] - L + 1
        out[r] = P[i:i + n]; i += n
    assert i == len(P)
    return out

models = ["mlp_seq1", "gap_seq2", "gap_seq4", "gapwide_seq4", "lstm_seq2", "lstm_seq4"]
seeds = range(42, 47)
# 녹화본별 정답 비율 (시드 평균)
acc = {}
for m in models:
    a = np.zeros(len(va))
    for s in seeds:
        pr = per_rec(m, s)
        a += np.array([(pr[r].argmax(1) == C.index(meta[r]["label"])).mean() for r in va])
    acc[m] = a / 5
lab = np.array([C.index(meta[r]["label"]) for r in va])
rng = np.random.default_rng(0)
B = 10000
res = {}
def boot(diff):
    idx_by_c = [np.where(lab == c)[0] for c in range(7)]
    out = np.empty(B)
    for b in range(B):
        sel = np.concatenate([rng.choice(ix, size=len(ix), replace=True) for ix in idx_by_c])
        out[b] = diff[sel].mean()
    return out
for a_, b_ in [("lstm_seq4", "gap_seq4"), ("lstm_seq4", "gapwide_seq4"), ("gap_seq4", "gap_seq2"),
               ("lstm_seq4", "lstm_seq2"), ("mlp_seq1", "gap_seq4"), ("lstm_seq4", "mlp_seq1")]:
    d = acc[a_] - acc[b_]
    bs = boot(d) * 100
    res[f"{a_} - {b_}"] = dict(mean_pp=float(d.mean() * 100), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                               recs_better=int((d > 1e-9).sum()), recs_worse=int((d < -1e-9).sum()))
    print(a_, "-", b_, res[f"{a_} - {b_}"])
# 오발동 녹화본
none_ids = [r for r in va if meta[r]["label"] == "none"]
fa = {}
for m in models:
    cnt = {r: 0 for r in none_ids}
    for s in seeds:
        pr = per_rec(m, s)
        for r in none_ids:
            cnt[r] += sum(1 for _, c in sim(pr[r], THR) if c in ATT)
    fa[m] = {str(r): v for r, v in cnt.items() if v}
    print(m, "총", sum(cnt.values()), "녹화본별", fa[m])
# 오류가 몰린 녹화본: 시드 평균 정답 비율 90% 미만
bad = {m: {str(r): round(float(x), 3) for r, x in zip(va, acc[m]) if x < 0.9} for m in models}
print("정답률 90% 미만 녹화본", bad)
json.dump(dict(bootstrap=res, false_attack_records=fa, low_acc_records=bad,
               note="녹화본 단위 계층 부트스트랩(10,000회), 정확도는 시드 5개 평균"),
          open(os.path.join(HERE, "stats_existing.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
