# -*- coding: utf-8 -*-
"""Precise의 직선 펀치 확정 프레임(1·2·3)을 게임 규칙 재생으로 비교한다(v1.1 모델, 비교용 v1.0 모델).
사용: python compare_confirm.py   결과: results/확정프레임_비교.md, .json"""
import os, sys, json
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L
import analyze_session as A
import live_sim as S
import compare_fixes as CF
import tensorflow as tf

SESS = ["20261017_180725_P1", "20261017_190303_P1", "20261017_192420_P1", "20261017_160537_P1", "20261018_212037_P1"]
MODELS = [("v1.1 모델", L.MODELS["v11"][1][0]), ("v1.0 모델", L.MODELS["reference"][1][0])]
data = []
for name in SESS:
    d = os.path.join(L.RESULTS, name)
    meta, recs, bad, blocks, cues, events = A.load_session(d)
    cond = meta.get("condition", "") + (" (10/18, v1.1 실시간)" if name.startswith("20261018") else "")
    data.append((name, cond, recs, blocks, cues, A.onsets(recs, cues), float(meta.get("speed", 1.0)), events))
res = {}
for mlabel, path in MODELS:
    m = tf.keras.models.load_model(path, compile=False)
    fps = {n: S.frames_and_probs(recs, m, m.input_shape[1]) for n, c, recs, *_ in data}
    for k in (1, 2, 3):
        groups = {}
        for name, cond, recs, blocks, cues, on, sp, ev in data:
            groups.setdefault(cond, []).append(CF.per_metrics(S.run(*fps[name], opts={"punch_confirm": k}), blocks, cues, on, sp))
        res[f"{mlabel}, 펀치 확정 {k}프레임"] = {g: CF.pool(v) for g, v in groups.items()}
    tf.keras.backend.clear_session()
# 10/18 실제 게임 입력(v1.1, 확정 3프레임)
name, cond, recs, blocks, cues, on, sp, ev = data[-1]
res["실제 게임 입력 (v1.1, 확정 3프레임)"] = {cond: CF.pool([CF.per_metrics(ev, blocks, cues, on, sp)])}
json.dump(res, open(os.path.join(L.RESULTS, "확정프레임_비교.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
conds = []
for v in res.values():
    for g in v:
        if g not in conds:
            conds.append(g)
lines = ["# 직선 펀치 확정 프레임 비교 (게임 규칙 재생)", ""]
for g in conds:
    lines += [f"## {g}", "", "| 설정 | 지시 동작 정답 | 어퍼컷 정답 | 다른 공격 먼저 | 동작 시작→발동 | 빠른 잽 정답 | 비스듬히 정답 | 쉬는 구간 오발동/분 | 준비 자세 오발동/분 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for label, rr in res.items():
        if g not in rr:
            continue
        r = rr[g]; cu = r.get("cued", {}); fa = r.get("fast", {}); an = r.get("angle", {})
        lines.append(f"| {label} | {cu.get('정답(%)', '-')}% | {r.get('어퍼컷 정답(%)', '-')}% | {cu.get('다른 공격 먼저(%)', '-')}% | {cu.get('지연(ms)', '-')} ms | "
                     f"{fa.get('정답(%)', '-')}% | {an.get('정답(%)', '-')}% | {cu.get('쉬는 구간 오발동/분', '-')} | {r.get('준비 자세 오발동/분', '-')} |")
    lines.append("")
open(os.path.join(L.RESULTS, "확정프레임_비교.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
