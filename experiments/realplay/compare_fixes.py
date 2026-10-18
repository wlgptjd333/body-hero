# -*- coding: utf-8 -*-
"""어퍼컷이 펀치에 막히는 문제의 보완 후보를 기록 재생으로 비교한다(게임 코드는 바꾸지 않음).
1) 게임 규칙 재현 정확도: live_sim(현재 규칙, 배포 모델)으로 만든 입력과 실험 중 실제로 나간 입력의 일치율
2) 후보별 지표: 지시 동작·빠른 잽·비스듬히의 정답 발동, 어퍼컷 정답, 다른 공격 먼저, 쉬는 구간·준비 자세 오발동, 동작 시작→발동
사용: python compare_fixes.py <세션 폴더> [...]   결과: results/보완안_비교.md, .json"""
import json, os, sys
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L
import analyze_session as A
import live_sim as S
import tensorflow as tf

CANDS = [
    ("실제 배포본 v1.0.0 모델(pose_classifier_seq_len4) + 현재 규칙", {}, "reference"),
    ("실제 배포본 모델 + 펀치 확정 3프레임", {"punch_confirm": 3}, "reference"),
    ("현재 게임 규칙 (실험에 쓴 gap_g_seed44)", {}, "deployed"),
    ("A. 손목-어깨 보류 켜기(코드 그대로)", {"windup": "as_coded"}, "deployed"),
    ("B. 손목-어깨 보류 켜기(손 대응 수정)", {"windup": "fixed"}, "deployed"),
    ("C. 펀치 확정 3프레임", {"punch_confirm": 3}, "deployed"),
    ("D. 펀치 2프레임 늦추고 어퍼컷 오면 취소", {"punch_delay": 2}, "deployed"),
    ("E. 펀치 직후 같은 손 어퍼컷 허용", {"upper_after_punch": True}, "deployed"),
    ("F. 모델 교체: GAP 4프레임(제대로 반전, 시드44)", {}, "gap4_44"),
    ("G. F + B", {"windup": "fixed"}, "gap4_44"),
    ("H. F + C (모델 교체 + 펀치 확정 3프레임)", {"punch_confirm": 3}, "gap4_44"),
]
MODEL_FILES = {"deployed": L.MODELS["deployed"][1][0], "gap4_44": os.path.join(L.R0, "model_gap_seq4_seed44.keras"),
               "reference": L.MODELS["reference"][1][0]}


def per_metrics(ev, blocks, cues, on, speed):
    m = A.metrics(ev, blocks, cues, on, speed)
    up_n = up_hit = 0
    for c in cues:
        if c["cue"] in ("upper_l", "upper_r") and not c.get("flag") and not c.get("auto") and L.BLOCKS.get(c["block"], {}).get("kind") == "cue":
            win = L.BLOCKS[c["block"]]["window"] / speed
            up_n += 1; up_hit += any(x == c["cue"] for t, x in ev if c["t_cue"] <= t < min(c["t_cue"] + win, c["t_end"]))
    m["_upper"] = (up_hit, up_n)
    return m


def pool(ms):
    out = {}
    for key in ("cued", "fast", "angle"):
        n = sum(m[key]["_n"] for m in ms if key in m)
        if not n:
            continue
        out[key] = {"정답(%)": round(100 * sum(m[key]["_hit"] for m in ms if key in m) / n, 1),
                    "다른 공격 먼저(%)": round(100 * sum(m[key]["_wrong"] for m in ms if key in m) / n, 1),
                    "지연(ms)": round(float(np.median(sum((m[key]["_lat_on"] for m in ms if key in m), [])))) if any(m.get(key, {}).get("_lat_on") for m in ms) else None,
                    "쉬는 구간 오발동/분": round(sum(m[key]["_rest_fa"] for m in ms if key in m) / max(1e-6, sum(m[key]["_rest_dur"] for m in ms if key in m)) * 60, 2)}
    uh = sum(m["_upper"][0] for m in ms); un = sum(m["_upper"][1] for m in ms)
    out["어퍼컷 정답(%)"] = round(100 * uh / un, 1) if un else None
    fa = sum(m[k]["_fa"] for m in ms for k in ("idle_ready_l", "idle_ready_r") if k in m)
    du = sum(m[k]["_dur"] for m in ms for k in ("idle_ready_l", "idle_ready_r") if k in m)
    out["준비 자세 오발동/분"] = round(fa / du * 60, 2) if du else None
    return out


def main():
    sess = sys.argv[1:]
    loaded = {k: tf.keras.models.load_model(p, compile=False) for k, p in MODEL_FILES.items()}
    data = []
    for d in sess:
        meta, recs, bad, blocks, cues, events = A.load_session(d)
        on = A.onsets(recs, cues); sp = float(meta.get("speed", 1.0))
        fp = {k: S.frames_and_probs(recs, m, m.input_shape[1]) for k, m in loaded.items()}
        data.append((d, meta, recs, blocks, cues, events, on, sp, fp))
    # 1) 재현 정확도
    rep = []
    for d, meta, recs, blocks, cues, events, on, sp, fp in data:
        sim = S.run(*fp["deployed"])
        live = [(t, x) for t, x in events if x in L.ATTACK or x in ("guard", "squat")]
        simv = [(t, x) for t, x in sim if x in L.ATTACK or x in ("guard", "squat")]
        used = set(); match = 0
        for t, x in live:
            for j, (ts, xs) in enumerate(simv):
                if j not in used and xs == x and abs(ts - t) <= 0.15:
                    used.add(j); match += 1; break
        rep.append({"회차": os.path.basename(d), "실제 입력": len(live), "재현 입력": len(simv), "일치(±0.15초)": match})
    # 2) 후보 비교
    groups = {}
    for d, meta, recs, blocks, cues, events, on, sp, fp in data:
        groups.setdefault(meta.get("condition", ""), []).append((d, blocks, cues, events, on, sp, fp))
    res = {}
    for g, items in groups.items():
        res[g] = {"실제 게임 입력(기록)": pool([per_metrics(ev, b, c, on, sp) for d, b, c, ev, on, sp, fp in items])}
        for name, opt, mk in CANDS:
            res[g][name] = pool([per_metrics(S.run(*fp[mk], opts=opt), b, c, on, sp) for d, b, c, ev, on, sp, fp in items])
    out = {"재현 정확도": rep, "결과": res}
    json.dump(out, open(os.path.join(L.RESULTS, "보완안_비교.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = ["# 어퍼컷이 펀치에 막히는 문제: 보완안 재생 비교", "", "## 게임 규칙 재현 정확도 (현재 규칙 + 배포 모델)", "",
             "| 회차 | 실제 입력 | 재현 입력 | 일치(±0.15초) |", "|---|---|---|---|"]
    lines += [f"| {r['회차']} | {r['실제 입력']} | {r['재현 입력']} | {r['일치(±0.15초)']} ({100 * r['일치(±0.15초)'] / max(1, r['실제 입력']):.0f}%) |" for r in rep]
    for g, rows in res.items():
        lines += ["", f"## {g}", "", "| 방법 | 지시 동작 정답 | 어퍼컷 정답 | 다른 공격 먼저 | 동작 시작→발동 | 빠른 잽 정답 | 비스듬히 정답 | 쉬는 구간 오발동/분 | 준비 자세 오발동/분 |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for name, r in rows.items():
            cu = r.get("cued", {}); fa = r.get("fast", {}); an = r.get("angle", {})
            lines.append(f"| {name} | {cu.get('정답(%)', '-')}% | {r.get('어퍼컷 정답(%)', '-')}% | {cu.get('다른 공격 먼저(%)', '-')}% | {cu.get('지연(ms)', '-')} ms | "
                         f"{fa.get('정답(%)', '-')}% | {an.get('정답(%)', '-')}% | {cu.get('쉬는 구간 오발동/분', '-')} | {r.get('준비 자세 오발동/분', '-')} |")
    open(os.path.join(L.RESULTS, "보완안_비교.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
