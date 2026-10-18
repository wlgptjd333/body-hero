# -*- coding: utf-8 -*-
"""여러 실험 회차를 촬영 조건별로 합친다. 각 회차의 analysis.json(시드별 원자료)을 더해 다시 계산한다.
- 시험 회차(폴더 이름 '_시험')와 meta.json에 "use_in_aggregate": false 인 회차는 뺀다(예: 1회차 예비 실험).
- 같은 블록끼리 지시 수·정답·오발동을 합치고, 지연은 모든 시행을 모아 중앙값을 낸다. 시드가 여러 개면 시드별로 합친 뒤 평균한다.
사용: python aggregate_sessions.py [--include-pilot]   결과: results/종합_결과.md, results/종합_결과.json"""
import argparse, glob, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--include-pilot", action="store_true")
ap.add_argument("--checked", action="store_true", help="동작 점검(check_compliance.py)에서 표시된 시행을 뺀 결과로 합친다")
a = ap.parse_args()

sessions = []
for d in sorted(glob.glob(os.path.join(L.RESULTS, "*"))):
    fn = "analysis_점검제외.json" if a.checked else "analysis.json"
    if d.endswith("_시험") or not os.path.exists(os.path.join(d, fn)):
        continue
    an = json.load(open(os.path.join(d, fn), encoding="utf-8"))
    meta = an["meta"]
    if meta.get("use_in_aggregate") is False and not a.include_pilot:
        continue
    sessions.append((d, meta, an))
if not sessions:
    print("합칠 회차가 없습니다."); sys.exit(0)


def pool(per_session_metrics):
    """[회차별 {블록: 지표}] -> 합친 {블록: 지표}"""
    out = {}
    for m in per_session_metrics:
        for b, v in m.items():
            o = out.setdefault(b, {"_n": 0, "_hit": 0, "_wrong": 0, "_dup": 0, "_lat_on": [], "_lat_cue": [], "_fa": 0, "_dur": 0.0,
                                   "_rest_fa": 0, "_rest_dur": 0.0})
            for k in ("_n", "_hit", "_wrong", "_dup", "_fa", "_dur", "_rest_fa", "_rest_dur"):
                o[k] += v.get(k, 0) or 0
            o["_lat_on"] += v.get("_lat_on", []) or []
            o["_lat_cue"] += v.get("_lat_cue", []) or []
    res = {}
    for b, o in out.items():
        if o["_dur"]:
            res[b] = {"오발동": o["_fa"], "분당 오발동": round(o["_fa"] / o["_dur"] * 60, 2), "시간(초)": round(o["_dur"])}
        else:
            n = o["_n"]
            res[b] = {"지시": n, "정답 발동(%)": round(100 * o["_hit"] / n, 1) if n else None,
                      "다른 공격 먼저(%)": round(100 * o["_wrong"] / n, 1) if n else None,
                      "중복 발동(%)": round(100 * o["_dup"] / n, 1) if n else None,
                      "동작 시작→발동 중앙값(ms)": round(float(np.median(o["_lat_on"]))) if o["_lat_on"] else None,
                      "쉬는 구간 오발동(분당)": round(o["_rest_fa"] / o["_rest_dur"] * 60, 2) if o["_rest_dur"] else None}
    return res


def avg(results):
    if len(results) == 1:
        return results[0]
    out = {}
    for b in results[0]:
        out[b] = {}
        for k in results[0][b]:
            v = [r[b][k] for r in results if b in r and r[b].get(k) is not None]
            out[b][k] = round(float(np.mean(v)), 1) if v else None
    return out


groups = {}
for d, meta, an in sessions:
    groups.setdefault(meta.get("condition", "조건 기록 없음"), []).append((d, meta, an))
groups["전체"] = sessions

report = {}; lines = ["# 실플레이 종합 결과", "", "같은 사람의 여러 회차를 합친 값입니다. 새 사용자에 대한 성능으로 쓰지 않습니다.", ""]
for g, ss in groups.items():
    rows = {"게임 파이프라인(실시간 판정)": pool([an["live_pipeline"] for _, _, an in ss])}
    keys = []
    for _, _, an in ss:
        for m in an["models"]:
            if m["key"] not in keys:
                keys.append(m["key"])
    for k in keys:
        per = [next(m for m in an["models"] if m["key"] == k) for _, _, an in ss if any(m["key"] == k for m in an["models"])]
        nseed = min(len(m["per_seed"]) for m in per)
        res = avg([pool([m["per_seed"][s] for m in per]) for s in range(nseed)])
        rows[f"{L.MODELS[k][0]}" + (f" ({nseed}시드 평균)" if nseed > 1 else "")] = res
    report[g] = {"sessions": [os.path.basename(d) for d, _, _ in ss], "results": rows}
    lines += [f"## {g}", "", "회차: " + ", ".join(os.path.basename(d) for d, _, _ in ss), ""]
    blocks = []
    for _, _, an in ss:
        for b in an["live_pipeline"]:
            if b not in blocks:
                blocks.append(b)
    for b in blocks:
        bname = L.BLOCKS.get(b, {}).get("name", b)
        first = next(r[b] for r in rows.values() if b in r)
        cols = list(first)
        lines += [f"### {bname}", "", "| 모델 | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
        for lab, r in rows.items():
            if b in r:
                lines.append(f"| {lab} | " + " | ".join("-" if r[b].get(c) is None else str(r[b][c]) for c in cols) + " |")
        lines.append("")
sfx = ("_점검제외" if a.checked else "") + ("_예비포함" if a.include_pilot else "")
json.dump(report, open(os.path.join(L.RESULTS, f"종합_결과{sfx}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(L.RESULTS, f"종합_결과{sfx}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("저장:", os.path.join(L.RESULTS, f"종합_결과{sfx}.md"))
