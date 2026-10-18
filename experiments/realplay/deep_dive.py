# -*- coding: utf-8 -*-
"""실플레이 세션 심층 분석: 지시 창(응답 구간)과 쉬는 구간을 나눠 클래스별 오발동, 다른 공격이 먼저 나간 조합,
게임 파이프라인과 재생 평가의 지연 차이를 본다. 사용: python deep_dive.py <세션 폴더> [모델 키...]"""
import json, os, sys
from collections import Counter, defaultdict
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L
import analyze_session as A

d = sys.argv[1]
keys = sys.argv[2:] or ["deployed", "gap4", "lstm3", "lstm2", "mlp1"]
meta, recs, bad, blocks, cues, events = A.load_session(d)
bk = {b["key"]: b for b in blocks}
on = A.onsets(recs, cues)


def analyze(ev):
    out = {"rest_fa": Counter(), "resp_wrong_pairs": Counter(), "miss": Counter(), "lat_on": defaultdict(list), "n": Counter()}
    for c in cues:
        b = L.BLOCKS[c["block"]]
        if b["kind"] not in ("cue", "flash"):
            continue
        t_resp_end = min(c["t_cue"] + b["window"], c["t_end"])
        resp = [(t, x) for t, x in ev if c["t_cue"] <= t < t_resp_end]
        rest = [(t, x) for t, x in ev if t_resp_end <= t < c["t_end"]]
        out["n"][c["cue"]] += 1
        good = [t for t, x in resp if x == c["cue"]]
        if not good:
            out["miss"][c["cue"]] += 1
        elif on.get(c["idx"]) is not None and good[0] >= on[c["idx"]]:
            out["lat_on"][c["cue"]].append((good[0] - on[c["idx"]]) * 1000)
        att = [x for _, x in resp if x in L.ATTACK]
        if att and att[0] != c["cue"] and c["cue"] in L.ATTACK:
            out["resp_wrong_pairs"][f"{c['cue']}→{att[0]}"] += 1
        for _, x in rest:
            if x in L.ATTACK:
                out["rest_fa"][x] += 1
    out["lat_on"] = {k: round(float(np.median(v))) for k, v in out["lat_on"].items()}
    return out


res = {"게임 파이프라인": analyze(events)}
cache = {}
for k in keys:
    label, files, _ = L.MODELS[k]
    per = []
    for p in files:
        ev, _ = A.eval_model(p, recs, cache); per.append(analyze(ev))
    agg = {"rest_fa": sum((x["rest_fa"] for x in per), Counter()), "resp_wrong_pairs": sum((x["resp_wrong_pairs"] for x in per), Counter()),
           "miss": sum((x["miss"] for x in per), Counter()), "n": per[0]["n"],
           "lat_on": {c: round(float(np.mean([x["lat_on"].get(c) for x in per if x["lat_on"].get(c) is not None]))) for c in per[0]["lat_on"]},
           "seeds": len(per)}
    res[label] = agg
rest_sec = sum((min(c["t_cue"] + L.BLOCKS[c["block"]]["window"], c["t_end"]), c["t_end"]) [1] - min(c["t_cue"] + L.BLOCKS[c["block"]]["window"], c["t_end"])
               for c in cues if L.BLOCKS[c["block"]]["kind"] in ("cue", "flash"))
out = {"rest_seconds_total": round(rest_sec, 1), "results": {k: {kk: (dict(vv) if isinstance(vv, Counter) else vv) for kk, vv in v.items()} for k, v in res.items()}}
json.dump(out, open(os.path.join(d, "deep_dive.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
