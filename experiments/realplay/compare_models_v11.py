# -*- coding: utf-8 -*-
"""게임 v1.1 후보 모델 비교(게임 규칙 재생, 펀치 확정 3프레임). 학습에 대기 프레임을 쓴 회차(180725)의 대기 블록은 시험에서 뺀다.
사용: python compare_models_v11.py   결과: results/모델후보_v11_비교.md"""
import os, sys, json
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L
import analyze_session as A
import live_sim as S
import compare_fixes as CF
import tensorflow as tf

H = os.path.dirname(os.path.abspath(__file__))
SESS = ["20261017_180725_P1", "20261017_190303_P1", "20261017_192420_P1", "20261017_160537_P1"]
TRAIN_IDLE = {"20261017_180725_P1"}
MODELS = [("v1.0 배포 모델(pose_classifier_seq_len4), 현재 규칙", L.MODELS["reference"][1][0], {}),
          ("v1.0 배포 모델 + 펀치 확정 3", L.MODELS["reference"][1][0], {"punch_confirm": 3}),
          ("GAP4 제대로 반전(시드44) + 펀치 확정 3", os.path.join(L.R0, "model_gap_seq4_seed44.keras"), {"punch_confirm": 3})]
for s in (42, 43, 44):
    MODELS.append((f"GAP4 + 실플레이 대기 추가(시드{s}) + 펀치 확정 3", os.path.join(H, "new_models", f"gap4_idle_seed{s}.keras"), {"punch_confirm": 3}))

data = []
for name in SESS:
    d = os.path.join(L.RESULTS, name)
    meta, recs, bad, blocks, cues, events = A.load_session(d)
    if name in TRAIN_IDLE:
        blocks = [b for b in blocks if b["kind"] != "idle"]   # 학습에 쓴 대기 구간은 시험에서 제외
    data.append((name, meta, recs, blocks, cues, A.onsets(recs, cues), float(meta.get("speed", 1.0))))

res = {}
for label, path, opt in MODELS:
    m = tf.keras.models.load_model(path, compile=False)
    groups = {}
    for name, meta, recs, blocks, cues, on, sp in data:
        fr, pr = S.frames_and_probs(recs, m, m.input_shape[1])
        groups.setdefault(meta.get("condition", ""), []).append(CF.per_metrics(S.run(fr, pr, opts=opt), blocks, cues, on, sp))
    res[label] = {g: CF.pool(v) for g, v in groups.items()}
    tf.keras.backend.clear_session(); print("done", label, flush=True)

lines = ["# 게임 v1.1 후보 모델 비교 (게임 규칙 재생)", "",
         "- 대기 프레임을 학습에 쓴 회차(180725)의 대기 블록은 시험에서 뺐습니다. 준비 자세 오발동은 조명 끔 회차(192420)만으로 계산됩니다.",
         "- 같은 사람(참가자 1)의 기록입니다.", ""]
conds = list(next(iter(res.values())).keys())
for g in conds:
    lines += [f"## {g}", "", "| 모델 | 지시 동작 정답 | 어퍼컷 정답 | 다른 공격 먼저 | 동작 시작→발동 | 빠른 잽 정답 | 비스듬히 정답 | 쉬는 구간 오발동/분 | 준비 자세 오발동/분 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for label, r in res.items():
        r = r[g]; cu = r.get("cued", {}); fa = r.get("fast", {}); an = r.get("angle", {})
        lines.append(f"| {label} | {cu.get('정답(%)', '-')}% | {r.get('어퍼컷 정답(%)', '-')}% | {cu.get('다른 공격 먼저(%)', '-')}% | {cu.get('지연(ms)', '-')} ms | "
                     f"{fa.get('정답(%)', '-')}% | {an.get('정답(%)', '-')}% | {cu.get('쉬는 구간 오발동/분', '-')} | {r.get('준비 자세 오발동/분', '-')} |")
    lines.append("")
json.dump(res, open(os.path.join(L.RESULTS, "모델후보_v11_비교.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(L.RESULTS, "모델후보_v11_비교.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
