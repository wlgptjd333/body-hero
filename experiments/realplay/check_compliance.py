# -*- coding: utf-8 -*-
"""지시대로 했는지 관절 좌표로 점검한다(모델 판정과 무관하게 사람의 동작만 본다).
- 다른 손 먼저: 공격 지시 뒤 반대쪽 손목이 지시한 손보다 먼저 움직임(어깨 너비 30% 이상)
- 동작 종류 애매: 지시한 손의 최대 이동 자세가 학습 데이터의 펀치/어퍼컷 평균 중 지시와 다른 쪽에 더 가까움
- 앞발 반대: 비스듬히 서기(왼발 앞 지시)에서 발목 깊이 차로 본 앞발이 오른발
결과는 cues.csv의 check 열에 이유를 적고(분석 제외 여부와 별개), compliance.json에 요약한다.
손 대응: 학습 데이터에서 왼손 공격은 관절 16번, 오른손 공격은 15번 손목이 크게 움직인다(좌우 반전 영상 기준).
사용: python check_compliance.py <세션 폴더> [...]"""
import csv, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

HAND = {"punch_l": 16, "upper_l": 16, "punch_r": 15, "upper_r": 15}
THR = 0.30
pose = json.load(open(os.path.join(L.TOOLS, "pose_data.json"), encoding="utf8"))
X = np.asarray([p["landmarks"] for p in pose], np.float32)
meta_tr = json.load(open(os.path.join(L.TOOLS, "pose_recordings_meta.json"), encoding="utf8"))["recordings"]
CENT = {lab: np.concatenate([X[r["start_index"]:r["start_index"] + r["frame_count"]] for r in meta_tr if r["label"] == lab]).mean(0)
        for lab in ("none", "punch_l", "punch_r", "upper_l", "upper_r")}


def wxy(v, w):
    return v[..., 3 * w:3 * w + 2]


def check_session(d):
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    cues = list(csv.DictReader(open(os.path.join(d, "cues.csv"), encoding="utf-8")))
    recs, _ = L.load_jsonl(os.path.join(d, "frames.jsonl"))
    ta = np.array([r["t"] for r in recs if r["k"] == "a"]); D = np.array([r["d"] for r in recs if r["k"] == "a"], np.float32)
    summ = {"다른 손 먼저": 0, "동작 종류 애매": 0, "앞발 반대": 0, "점검한 공격 지시": 0}
    for c in cues:
        reasons = []
        cue = c["cue"]; blk = c["block"]
        if cue in HAND and blk != "practice":
            t0 = float(c["t_cue"]); win = L.BLOCKS.get(blk, {}).get("window", 2.0)
            pre = (ta >= t0 - 0.3) & (ta < t0); post = np.where((ta >= t0) & (ta < t0 + win))[0]
            if pre.sum() >= 2 and len(post):
                summ["점검한 공격 지시"] += 1
                base = D[pre].mean(0); w_ok = HAND[cue]; w_ot = 31 - w_ok
                mv = lambda j, w: float(np.hypot(*(wxy(D[j], w) - wxy(base, w))))
                first = {}
                for w in (w_ok, w_ot):
                    for j in post:
                        if mv(j, w) >= THR:
                            first[w] = j; break
                if w_ot in first and (w_ok not in first or first[w_ot] < first[w_ok] - 1):
                    reasons.append("다른 손 먼저"); summ["다른 손 먼저"] += 1
                # 최대 이동 프레임의 손 자세를 펀치/어퍼컷 평균과 비교
                jm = max(post, key=lambda j: mv(j, w_ok))
                side = cue[-1]
                dp = np.linalg.norm(wxy(D[jm], w_ok) - wxy(CENT["punch_" + side], w_ok))
                du = np.linalg.norm(wxy(D[jm], w_ok) - wxy(CENT["upper_" + side], w_ok))
                kind = "punch" if dp < du else "upper"
                if not cue.startswith(kind):
                    reasons.append("동작 종류 애매"); summ["동작 종류 애매"] += 1
        if blk == "angle":
            m = (ta >= float(c["t_cue"]) - 1.0) & (ta < float(c["t_cue"]))
            if m.sum():
                dz = float(np.median(D[m, 28 * 3 + 2] - D[m, 27 * 3 + 2]))
                if dz > 0.8:
                    reasons.append("앞발 반대"); summ["앞발 반대"] += 1
        c["check"] = "; ".join(reasons)
    # 준비 자세 대기 블록: 지시와 다른 앞발 비율
    stance = {}
    for b in csv.DictReader(open(os.path.join(d, "blocks.csv"), encoding="utf-8")):
        if b["key"] in ("idle_ready_l", "idle_ready_r"):
            m = (ta >= float(b["t_start"])) & (ta < float(b["t_end"]))
            dz = D[m, 28 * 3 + 2] - D[m, 27 * 3 + 2]
            wrong = (dz > 0.8) if b["key"] == "idle_ready_l" else (dz < -0.8)
            stance[b["key"]] = round(float(wrong.mean() * 100), 1)
    summ["준비 자세 대기에서 지시와 다른 앞발(프레임 %)"] = stance
    fields = list(cues[0].keys())
    if "check" not in fields:
        fields.append("check")
    with open(os.path.join(d, "cues.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(cues)
    json.dump(summ, open(os.path.join(d, "compliance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return summ


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(os.path.basename(d.rstrip("/\\")), json.dumps(check_session(d), ensure_ascii=False))
