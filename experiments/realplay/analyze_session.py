# -*- coding: utf-8 -*-
"""실플레이 세션 분석.
1) 기록 점검(check.json): 프레임률, 사람 인식률, 프레임 끊김, 지시 수, 시계 정렬, 좌표 형식
2) 게임 파이프라인 결과: 실험 중 실제로 UDP로 들어온 입력(배포 모델, 게임과 같은 전체 후처리)
3) 모델 재생 평가: 기록한 관절 좌표를 고른 모델에 그대로 넣고 논문과 같은 후처리 시뮬레이션(Precise)을 적용
사용: python analyze_session.py [세션 폴더] [--models deployed,gap4,lstm3 | --models all] [--seeds 5|1]
세션 폴더를 생략하면 가장 최근 세션을 분석한다."""
import argparse, csv, glob, json, os, sys, time
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

ONSET_THR = 0.30   # 손목이 지시 직전 위치에서 어깨 너비의 30% 이상 움직인 첫 프레임을 동작 시작으로 본다
WRISTS = (15, 16)


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_session(d):
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    recs, bad = L.load_jsonl(os.path.join(d, "frames.jsonl"))
    blocks = [dict(b, t_start=float(b["t_start"]), t_end=float(b["t_end"])) for b in read_csv(os.path.join(d, "blocks.csv"))]
    cues = [dict(c, t_cue=float(c["t_cue"]), t_end=float(c["t_end"]), flag=int(c.get("flag") or 0)) for c in read_csv(os.path.join(d, "cues.csv"))]
    events = [(float(e["t"]), e["action"]) for e in read_csv(os.path.join(d, "events.csv"))]
    q = L.trial_quality(recs, cues, float(meta.get("speed", 1.0)))
    for c in cues:
        c["auto"] = 1 if L.is_auto_bad(q[c["idx"]]) else 0
    return meta, recs, bad, blocks, cues, events


# ------------------------------------------------------------------ 1. 기록 점검
def check(meta, recs, bad, blocks, cues, events):
    out = []

    def add(level, msg, **kv):
        out.append(dict(level=level, msg=msg, **kv))

    f = np.array([r["t"] for r in recs if r["k"] == "f"]); a = [r for r in recs if r["k"] == "a"]
    s = [r for r in recs if r["k"] == "s"]
    if bad:
        add("경고", f"읽지 못한 기록 줄 {bad}개 (실험이 강제로 끝났을 때 마지막 줄이 잘릴 수 있음)")
    if len(f) < 30:
        add("실패", "프레임 기록이 거의 없습니다. 인식 모듈이 시작되지 않았을 수 있습니다.")
        return out
    if np.any(np.diff(f) < 0):
        add("실패", "프레임 시각이 거꾸로 가는 곳이 있습니다.")
    dims = {len(r["d"]) for r in a}
    finite = all(np.isfinite(r["d"]).all() for r in a[:: max(1, len(a) // 500)])
    add("통과" if dims == {99} and finite else "실패", f"좌표 형식: 프레임당 {sorted(dims)}개 값, 유한값 {'예' if finite else '아니오'}")
    speed = float(meta.get("speed", 1.0))
    for b in blocks:
        m = (f >= b["t_start"]) & (f < b["t_end"]); n = int(m.sum()); dur = b["t_end"] - b["t_start"]
        if dur <= 0:
            continue
        fps = n / dur / speed
        ta = np.array([r["t"] for r in a]); det = ((ta >= b["t_start"]) & (ta < b["t_end"])).sum() / max(1, n)
        gaps = np.diff(f[m]) * speed if n > 1 else np.array([0.0])
        lvl = "통과" if fps >= 25 and det >= 0.95 and gaps.max() < 0.2 else ("경고" if fps >= 15 and det >= 0.8 else "실패")
        add(lvl, f"[{b['name']}] 프레임률 {fps:.1f} FPS, 사람 인식 {det * 100:.1f}%, 최대 프레임 간격 {gaps.max() * 1000:.0f} ms",
            block=b["key"], fps=round(fps, 2), detect=round(float(det), 4), max_gap_ms=round(float(gaps.max() * 1000), 1))
    plan = meta.get("plan_counts", {})
    for b in blocks:
        got = sum(1 for c in cues if c["block"] == b["key"])
        want = plan.get(b["key"])
        if want is not None and b.get("completed", "1") == "1":
            add("통과" if got == want else "경고", f"[{b['name']}] 지시 {got}개 / 계획 {want}개")
        elif b.get("completed", "1") != "1":
            add("경고", f"[{b['name']}] 중간에 멈춘 블록입니다(지시 {got}개). 분석에는 완료된 지시만 씁니다.")
    # 시계 정렬: 인식 모듈이 보낸 시각(s)과 실험 화면이 받은 시각(events)
    if s and events:
        ts = np.array([r["t"] for r in s]); te = np.array([t for t, _ in events])
        k = min(len(ts), len(te)); d = (te[:k] - ts[:k]) * 1000
        lvl = "통과" if len(ts) == len(te) and np.abs(d).max() < 50 else "경고"
        add(lvl, f"입력 전송 {len(ts)}건 / 수신 {len(te)}건, 전송→수신 시간차 중앙값 {np.median(d):.1f} ms (최대 {np.abs(d).max():.1f} ms)")
    elif not events:
        add("경고", "실험 중 받은 입력이 0건입니다. 인식 모듈이 UDP를 보내지 못했을 수 있습니다.")
    return out


# ------------------------------------------------------------------ 2·3. 지표
def onsets(recs, cues):
    """지시마다 손목 이동으로 본 동작 시작 시각(없으면 None)."""
    ta = np.array([r["t"] for r in recs if r["k"] == "a"]); D = np.array([r["d"] for r in recs if r["k"] == "a"], np.float32)
    out = {}
    for c in cues:
        pre = (ta >= c["t_cue"] - 0.3) & (ta < c["t_cue"])
        post = np.where((ta >= c["t_cue"]) & (ta < c["t_end"]))[0]
        if pre.sum() < 2 or len(post) == 0:
            out[c["idx"]] = None; continue
        base = D[pre].mean(0)
        best = None
        for j in post:
            mv = max(np.hypot(D[j, 3 * w] - base[3 * w], D[j, 3 * w + 1] - base[3 * w + 1]) for w in WRISTS)
            if mv >= ONSET_THR:
                best = float(ta[j]); break
        out[c["idx"]] = best
    return out


def metrics(ev, blocks, cues, on, speed=1.0):
    """ev: [(시각, 동작)]. 블록별 지표."""
    res = {}
    for b in blocks:
        if b["kind"] == "practice":
            continue
        cs_all = [c for c in cues if c["block"] == b["key"]]
        cs = [c for c in cs_all if not c.get("flag") and not c.get("auto")]
        e = [(t, x) for t, x in ev if b["t_start"] <= t < b["t_end"]]
        if b["kind"] == "idle":
            dur = (b["t_end"] - b["t_start"]) * speed
            fa = sum(1 for _, x in e if x in L.ATTACK)
            res[b["key"]] = {"오발동": fa, "분당 오발동": round(fa / dur * 60, 2), "시간(초)": round(dur, 1), "_fa": fa, "_dur": dur}
            continue
        n = hit = wrong = dup = 0; lat_cue = []; lat_on = []; rest_fa = 0; rest_dur = 0.0
        win = L.BLOCKS.get(b["key"], {}).get("window", 2.0) / speed
        for c in cs:
            t_resp = min(c["t_cue"] + win, c["t_end"])
            rest_fa += sum(1 for t, x in e if t_resp <= t < c["t_end"] and x in L.ATTACK)
            rest_dur += (c["t_end"] - t_resp) * speed
            w = [(t, x) for t, x in e if c["t_cue"] <= t < c["t_end"]]
            att = [(t, x) for t, x in w if x in L.ATTACK]
            n += 1
            if c["cue"] == "combo":
                ok = any(x == "punch_l" for _, x in w) and any(x == "punch_r" for _, x in w)
                hit += ok
                continue
            good = [t for t, x in w if x == c["cue"]]
            if good:
                hit += 1; lat_cue.append((good[0] - c["t_cue"]) * 1000 * speed)
                if on.get(c["idx"]) is not None and good[0] >= on[c["idx"]]:
                    lat_on.append((good[0] - on[c["idx"]]) * 1000 * speed)
                if len(good) > 1:
                    dup += 1
            if att and att[0][1] != c["cue"] and c["cue"] in L.ATTACK:
                wrong += 1
        r = {"지시": n, "제외(표시/자동)": f"{sum(1 for c in cs_all if c.get('flag'))}/{sum(1 for c in cs_all if c.get('auto') and not c.get('flag'))}", "정답 발동(%)": round(100 * hit / n, 1) if n else None,
             "쉬는 구간 오발동(분당)": round(rest_fa / rest_dur * 60, 2) if rest_dur else None,
             "_n": n, "_hit": hit, "_wrong": wrong, "_dup": dup, "_lat_cue": lat_cue, "_lat_on": lat_on, "_rest_fa": rest_fa, "_rest_dur": rest_dur}
        if b["kind"] != "combo":
            r.update({"다른 공격 먼저(%)": round(100 * wrong / n, 1) if n else None, "중복 발동(%)": round(100 * dup / n, 1) if n else None,
                      "지시→발동 중앙값(ms)": round(float(np.median(lat_cue))) if lat_cue else None,
                      "동작 시작→발동 중앙값(ms)": round(float(np.median(lat_on))) if lat_on else None,
                      "동작 시작 검출 지시 수": len(lat_on)})
        res[b["key"]] = r
    return res


def replay_windows(recs, L_):
    """게임과 같은 버퍼 규칙(사람이 사라지면 비움)으로 창을 만든다. 반환: 구간별 (창 배열, 창 끝 시각)."""
    segs = []; buf = []; tbuf = []; cur_w = []; cur_t = []
    for r in recs:
        if r["k"] == "c":
            if cur_w:
                segs.append((np.asarray(cur_w, np.float32), np.asarray(cur_t))); cur_w = []; cur_t = []
            buf = []; continue
        if r["k"] != "a":
            continue
        buf.append(r["d"]); buf = buf[-L_:]
        if len(buf) == L_:
            cur_w.append(list(buf)); cur_t.append(r["t"])
    if cur_w:
        segs.append((np.asarray(cur_w, np.float32), np.asarray(cur_t)))
    return segs


def eval_model(path, recs, cache):
    import tensorflow as tf
    m = tf.keras.models.load_model(path, compile=False)
    L_ = m.input_shape[1]
    if L_ not in cache:
        cache[L_] = replay_windows(recs, L_)
    ev = []
    for W, T in cache[L_]:
        P = m.predict(W, batch_size=4096, verbose=0)
        ev += [(float(T[k]), L.C[c]) for k, c in L.sim(P)]
    tf.keras.backend.clear_session()
    return ev, L_


def mean_metrics(rs):
    """시드별 결과를 평균한다(숫자 항목만)."""
    if len(rs) == 1:
        return rs[0]
    out = {}
    for b in rs[0]:
        out[b] = {}
        for k in rs[0][b]:
            if k.startswith("_"):
                continue
            v = [r[b][k] for r in rs if r[b].get(k) is not None]
            if v and isinstance(v[0], (int, float)):
                mv = float(np.mean(v)); out[b][k] = int(mv) if all(x == v[0] for x in v) and float(v[0]).is_integer() else round(mv, 1)
            else:
                out[b][k] = v[0] if v else None
    return out


def write_md(d, meta, chk, live, models, blocks, cues, suffix=""):
    lines = [f"# 실플레이 실험 결과 ({meta['name']}, {meta['started']})", "",
             "같은 사람 1명의 실플레이 기록입니다. 새 사용자에 대한 성능으로 쓰지 않습니다.", "",
             "## 기록 점검", ""]
    lines += [f"- **{c['level']}** {c['msg']}" for c in chk]
    kind = {b["key"]: b["kind"] for b in blocks}
    name = {b["key"]: b["name"] for b in blocks}
    keys = [b["key"] for b in blocks if b["kind"] != "practice"]
    idle_keys = [k for k in keys if kind[k] == "idle"]
    lines += ["", f"- 조건: {meta.get('condition', '기록 없음')} / 메모: {meta.get('memo', '') or '-'} / 학습 데이터 녹화 참여자: {meta.get('in_training_data', '기록 없음')}",
              f"- 실시간 판정 게임 버전: {meta.get('game_version', 'v1.0.0 코드 + gap_g_seed44 모델(1~3회차)')}, 실시간 모델: {os.path.basename(meta.get('live_model', ''))}",
              f"- 제외한 시행: 직접 표시(X 키·시행 편집) {sum(1 for c in cues if c.get('flag'))}개, 자동 제외(사람 인식 {int(L.AUTO_MIN_DET * 100)}% 미만 또는 {int(L.AUTO_MIN_FPS)} FPS 미만) {sum(1 for c in cues if c.get('auto') and not c.get('flag'))}개"]
    rows = [(f"게임 파이프라인(실시간, {os.path.basename(meta.get('live_model', ''))})", live)] + [(m["label"], m["metrics"]) for m in models]
    if idle_keys:
        lines += ["", "## 대기 구간 오발동 (공격하지 않을 때 나간 공격)", "",
                  "| 모델 | " + " | ".join(f"{name[k]} (건, 분당)" for k in idle_keys) + " |", "|---" * (len(idle_keys) + 1) + "|"]
        for lab, mt in rows:
            lines.append(f"| {lab} | " + " | ".join(f"{mt[k]['오발동']} ({mt[k]['분당 오발동']})" for k in idle_keys) + " |")
    for k in keys:
        if kind[k] == "idle":
            continue
        lines += ["", f"## {name[k]}", ""]
        cols = [c for c in live[k] if not c.startswith("_")]
        lines.append("| 모델 | " + " | ".join(cols) + " |"); lines.append("|---" * (len(cols) + 1) + "|")
        for lab, mt in rows:
            lines.append(f"| {lab} | " + " | ".join("-" if mt[k].get(c) is None else str(mt[k][c]) for c in cols) + " |")
    lines += ["", "## 읽는 법", "",
              "- 게임 파이프라인: 실험 중 실제로 들어온 입력입니다. 게임과 같은 전체 후처리(쿨다운, 재무장, 동작량 게이팅 포함)를 거친 값입니다.",
              "- 나머지 모델: 기록한 관절 좌표를 각 모델에 넣고 논문과 같은 후처리 시뮬레이션(Precise, 쿨다운·게이팅 제외)을 적용한 값입니다. 여러 시드가 있으면 평균입니다.",
              "- 동작 시작→발동: 손목이 지시 직전 위치에서 어깨 너비의 30% 이상 움직인 순간부터 입력이 나간 순간까지. 사람의 반응 시간이 빠진 값입니다.",
              "- 지시→발동: 사람의 반응 시간이 포함된 값입니다.",
              f"- 분석 시각: {time.strftime('%Y-%m-%d %H:%M')}"]
    open(os.path.join(d, f"결과요약{suffix}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?")
    ap.add_argument("--models", default=None, help="쉼표로 구분한 모델 키, all, 또는 recommended")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--exclude-checked", action="store_true", help="check_compliance.py가 표시한 시행도 뺀다(결과는 _점검제외 파일로)")
    a = ap.parse_args()
    if a.session:
        d = a.session
    else:
        cands = [p for p in glob.glob(os.path.join(L.RESULTS, "*")) if os.path.exists(os.path.join(p, "meta.json"))]
        if not cands:
            print("분석할 실험 기록이 없습니다. 먼저 실플레이_실험_시작.bat으로 실험하세요."); return
        d = max(cands, key=os.path.getmtime)
    meta, recs, bad, blocks, cues, events = load_session(d)
    speed = float(meta.get("speed", 1.0))
    suffix = ""
    if a.exclude_checked:
        suffix = "_점검제외"
        for c in cues:
            if c.get("check"):
                c["flag"] = 3
    print("세션:", d, flush=True)
    chk = check(meta, recs, bad, blocks, cues, events)
    for c in chk:
        print(f"  [{c['level']}] {c['msg']}", flush=True)
    json.dump(chk, open(os.path.join(d, "check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    on = onsets(recs, cues)
    live = metrics(events, blocks, cues, on, speed)
    keys = a.models or ",".join(meta.get("analysis_models", L.RECOMMENDED))
    keys = list(L.MODELS) if keys == "all" else (L.RECOMMENDED if keys == "recommended" else keys.split(","))
    models = []; cache = {}
    for k in keys:
        label, files, _ = L.MODELS[k]
        files = files[: a.seeds]
        rs = []; seq = None
        for p in files:
            ev, seq = eval_model(p, recs, cache); rs.append(metrics(ev, blocks, cues, on, speed))
        models.append({"key": k, "label": f"{label} ({len(files)}시드)" if len(files) > 1 else label, "seq_len": seq,
                       "files": files, "metrics": mean_metrics(rs), "per_seed": rs})
        print(f"  모델 평가 완료: {label}", flush=True)
    out = {"session": d, "meta": meta, "check": chk, "live_pipeline": live, "models": models,
           "onset_threshold_shoulder_width": ONSET_THR, "analyzed": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(out, open(os.path.join(d, f"analysis{suffix}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(d, meta, chk, live, models, blocks, cues, suffix)
    print("저장:", os.path.join(d, f"결과요약{suffix}.md"), flush=True)


if __name__ == "__main__":
    main()
