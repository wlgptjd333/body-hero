# -*- coding: utf-8 -*-
"""시행 편집: 회차의 지시 시행 목록을 보고, 분석에서 뺄 시행을 고른다(기록은 지우지 않고 표시만 바꾼다).
- 사람 인식이 낮거나 프레임률이 낮은 시행은 '자동 제외'로 표시되며, 분석에서 항상 빠진다.
- 체크한 시행은 cues.csv의 flag가 2(편집에서 제외)로 바뀐다. X 키로 표시한 시행은 flag 1.
- [저장 후 다시 분석]을 누르면 결과요약.md가 다시 만들어진다.
사용: python trial_editor.py [세션 폴더]  (생략하면 가장 최근 회차)"""
import csv, glob, json, os, subprocess, sys, threading
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

FONT = "Malgun Gothic"
cands = [p for p in glob.glob(os.path.join(L.RESULTS, "*")) if os.path.exists(os.path.join(p, "cues.csv"))]
if not cands:
    print("회차 기록이 없습니다."); sys.exit(0)
d = sys.argv[1] if len(sys.argv) > 1 else max(cands, key=os.path.getmtime)
meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
cues = list(csv.DictReader(open(os.path.join(d, "cues.csv"), encoding="utf-8")))
events = [(float(r["t"]), r["action"]) for r in csv.DictReader(open(os.path.join(d, "events.csv"), encoding="utf-8"))]
recs, _ = L.load_jsonl(os.path.join(d, "frames.jsonl"))
q = L.trial_quality(recs, cues, float(meta.get("speed", 1.0)))
t_first = float(cues[0]["t_cue"]) if cues else 0.0

root = tk.Tk(); root.title(f"시행 편집 - {os.path.basename(d)}"); root.geometry("980x680+40+40")
tk.Label(root, text=f"{os.path.basename(d)}  ({meta.get('condition', '')})", font=(FONT, 13, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
tk.Label(root, text="분석에서 뺄 시행을 클릭해 선택하세요(Ctrl·Shift로 여러 개, 한 번 더 클릭하면 해제). 기록 자체는 지워지지 않습니다.",
         font=(FONT, 10)).pack(anchor="w", padx=10)
cols = ("idx", "cue", "time", "inputs", "quality", "status")
tv = ttk.Treeview(root, columns=cols, show="headings", selectmode="extended", height=24)
for c, w, t in zip(cols, (110, 110, 80, 360, 140, 140), ("시행", "지시", "시작 후(초)", "들어온 입력", "FPS / 사람 인식", "상태")):
    tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
sb = ttk.Scrollbar(root, orient="vertical", command=tv.yview); tv.configure(yscrollcommand=sb.set)
tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6); sb.pack(side="left", fill="y", pady=6)
tv.tag_configure("auto", background="#fde2e2"); tv.tag_configure("x", background="#fff3cd"); tv.tag_configure("ed", background="#ffe0b2")


def status(c):
    fl = int(c.get("flag") or 0)
    if L.is_auto_bad(q[c["idx"]]):
        return "자동 제외", "auto"
    if fl == 1:
        return "X 키로 표시", "x"
    if fl == 2:
        return "편집에서 제외", "ed"
    return "사용", ""


def refresh():
    tv.delete(*tv.get_children())
    for c in cues:
        t0, t1 = float(c["t_cue"]), float(c["t_end"])
        ins = ", ".join(L.KO.get(x, x) for t, x in events if t0 <= t < t1) or "(없음)"
        fps, det = q[c["idx"]]
        st, tag = status(c)
        tv.insert("", "end", iid=c["idx"], values=(c["idx"], "연타" if c["cue"] == "combo" else L.KO.get(c["cue"], c["cue"]),
                                                    f"{t0 - t_first:6.0f}", ins, f"{fps:4.1f} / {det * 100:3.0f}%", st), tags=(tag,))


def toggle():
    for iid in tv.selection():
        c = next(x for x in cues if x["idx"] == iid)
        fl = int(c.get("flag") or 0)
        c["flag"] = "0" if fl == 2 else ("2" if fl == 0 else c["flag"])
    refresh()


def save_and_analyze():
    with open(os.path.join(d, "cues.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cues[0].keys())); w.writeheader(); w.writerows(cues)
    meta["flagged"] = sum(1 for c in cues if int(c.get("flag") or 0) > 0)
    json.dump(meta, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    btn_an.config(state="disabled", text="분석 중...")

    def run():
        r = subprocess.run([L.PY, os.path.join(L.HERE, "analyze_session.py"), d], cwd=L.HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        open(os.path.join(d, "analysis_log.txt"), "w", encoding="utf-8").write(r.stdout + "\n" + r.stderr)
        root.after(0, lambda: (btn_an.config(state="normal", text="저장 후 다시 분석"),
                               messagebox.showinfo("시행 편집", "분석이 끝났습니다. 결과요약.md를 확인하세요." if r.returncode == 0 else "분석에 실패했습니다. analysis_log.txt를 확인하세요.")))
    threading.Thread(target=run, daemon=True).start()


bf = tk.Frame(root); bf.pack(side="bottom", fill="x", pady=6)
tk.Button(bf, text="선택한 시행 제외/해제", font=(FONT, 11), command=toggle).pack(side="left", padx=10)
btn_an = tk.Button(bf, text="저장 후 다시 분석", font=(FONT, 11, "bold"), command=save_and_analyze); btn_an.pack(side="left", padx=10)
tk.Button(bf, text="결과 폴더 열기", command=lambda: os.startfile(d)).pack(side="left", padx=10)
tk.Label(bf, text="빨강: 자동 제외 · 노랑: X 키 · 주황: 편집에서 제외", font=(FONT, 9), fg="gray").pack(side="left", padx=10)
refresh()
root.mainloop()
