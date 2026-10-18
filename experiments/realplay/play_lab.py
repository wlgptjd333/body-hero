# -*- coding: utf-8 -*-
"""Body Hero 실플레이 실험 (혼자 진행용 GUI).
게임의 인식 코드(udp_send_webcam_ml.py)에 기록 기능만 덧붙인 사본을 띄워, 화면 지시에 따라 플레이하는 동안
관절 좌표·실제 입력·지시 시각을 모두 기록한다. 끝나면 기록을 점검하고, 고른 모델들로 같은 기록을 재생해 비교한다.
실행: 실플레이_실험_시작.bat  (웹캠 없이 시험: python play_lab.py --fake)"""
import argparse, csv, json, os, queue, random, socket, subprocess, sys, threading, time, hashlib, platform, ctypes
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_common as L

ap = argparse.ArgumentParser()
ap.add_argument("--fake", action="store_true", help="웹캠 대신 수집 데이터로 가짜 입력(도구 시험용)")
ap.add_argument("--speed", type=float, default=1.0, help="시험용 시간 배속(가짜 입력과 함께만 사용)")
ap.add_argument("--auto", action="store_true", help="시험용: 스페이스 입력을 자동으로 진행")
ap.add_argument("--blocks", default=None, help="시험용: 블록 키를 쉼표로")
ap.add_argument("--resume", default=None, help="중단된 회차 폴더(남은 지시만 진행)")
ARGS = ap.parse_args()
SPEED = ARGS.speed if ARGS.fake else 1.0
FONT = "Malgun Gothic"
FOOT = "스페이스: 다음 · X: 방금 시행 '지시와 다름' 표시 · P: 일시정지 · Esc: 중단"


def sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return None


class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


def _systimes():
    i, k, u = _FT(), _FT(), _FT()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u)):
        return None
    v = lambda f: (f.hi << 32) | f.lo
    return v(i), v(k), v(u)


class Lab:
    def __init__(self, root):
        self.root = root; self.q = queue.Queue(); self.events = []; self.go = threading.Event(); self.abort = False
        self.f_times = []; self.a_times = []; self.last_action = None; self.proc = None; self.state_path = None
        self.cfg = L.read_game_settings()
        self.resume = None
        root.title("Body Hero 실플레이 실험"); root.geometry("1000x720+30+30")
        self.setup_view()

    # ------------------------------------------------------------ 설정 화면
    def setup_view(self):
        f = self.setup = tk.Frame(self.root, padx=16, pady=12); f.pack(fill="both", expand=True)
        tk.Label(f, text="Body Hero 실플레이 실험", font=(FONT, 20, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(f, text="게임은 꺼 두세요. 카메라 앞 2~3 m, 몸 전체(머리~무릎)가 보이게 서 주세요.", font=(FONT, 11)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))
        tk.Label(f, text="이름 이니셜", font=(FONT, 11)).grid(row=2, column=0, sticky="w")
        self.name = tk.StringVar(value="A"); tk.Entry(f, textvariable=self.name, width=8).grid(row=2, column=1, sticky="w")
        tk.Label(f, text="카메라 번호", font=(FONT, 11)).grid(row=3, column=0, sticky="w")
        self.cam = tk.StringVar(value=str(self.cfg["index"])); tk.Entry(f, textvariable=self.cam, width=8).grid(row=3, column=1, sticky="w")
        tk.Label(f, text=f"(게임 설정: 카메라 {self.cfg['index']}, {self.cfg['backend']}, 중앙 영역 {self.cfg['center_zone_margin']}, 프로필 Precise로 고정)",
                 font=(FONT, 9), fg="gray").grid(row=3, column=2, sticky="w")
        pf = tk.Frame(f); pf.grid(row=2, column=2, sticky="e")
        tk.Label(pf, text="회차 설정:", font=(FONT, 10, "bold")).pack(side="left")
        for pname, pcond, pblocks, prep in L.PRESETS:
            tk.Button(pf, text=pname, font=(FONT, 9), command=lambda c=pcond, b=pblocks, r=prep: self.preset(c, b, r)).pack(side="left", padx=2)
        sf = tk.Frame(f); sf.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        tk.Label(sf, text="촬영 조건", font=(FONT, 11)).grid(row=0, column=0, sticky="w")
        self.cond = tk.StringVar(value=L.CONDITIONS[0])
        ttk.Combobox(sf, textvariable=self.cond, values=L.CONDITIONS, width=50, state="readonly").grid(row=0, column=1, sticky="w")
        tk.Label(sf, text="메모(장소, 거리, 조명)", font=(FONT, 11)).grid(row=1, column=0, sticky="w")
        self.memo = tk.StringVar(value=""); tk.Entry(sf, textvariable=self.memo, width=60).grid(row=1, column=1, sticky="w")
        self.intrain = tk.BooleanVar(value=False)
        tk.Checkbutton(sf, variable=self.intrain, text="실험자가 학습 데이터 녹화에 참여한 사람이다(3명 중 1명)", font=(FONT, 10)).grid(row=3, column=1, sticky="w")
        tk.Label(sf, text="지시 블록 반복", font=(FONT, 11)).grid(row=2, column=0, sticky="w")
        self.rep = tk.IntVar(value=1)
        rf = tk.Frame(sf); rf.grid(row=2, column=1, sticky="w")
        tk.Spinbox(rf, from_=1, to=5, textvariable=self.rep, width=4, command=self.update_total).pack(side="left")
        tk.Label(rf, text=" 배 (지시 동작·빠른 잽·좌우 연타·비스듬히 서기의 지시 수)", font=(FONT, 9), fg="gray").pack(side="left")

        bf = tk.LabelFrame(f, text=" 실험 블록 (순서대로 진행) ", font=(FONT, 11), padx=8, pady=6); bf.grid(row=5, column=0, columnspan=3, sticky="we", pady=8)
        self.bvars = {}
        for i, k in enumerate(L.BLOCK_ORDER):
            b = L.BLOCKS[k]; v = tk.BooleanVar(value=b["default"] if ARGS.blocks is None else k in ARGS.blocks.split(","))
            self.bvars[k] = v
            n = sum(b.get("cues", {}).values())
            sec = b["sec"] if b["kind"] == "idle" else n * (b["window"] + b["rest"])
            tk.Checkbutton(bf, variable=v, text=f"{b['name']}  ({'지시 %d개, ' % n if n else ''}약 {sec / 60:.1f}분{', 반복 가능' if k in L.REPEATABLE else ''}){'  ← 권장' if b['default'] else ''}",
                           font=(FONT, 10), command=self.update_total).grid(row=i, column=0, sticky="w")
        self.total = tk.Label(bf, text="", font=(FONT, 10, "bold")); self.total.grid(row=len(L.BLOCK_ORDER), column=0, sticky="w", pady=(4, 0))

        mf = tk.LabelFrame(f, text=" 끝난 뒤 비교할 모델 (같은 기록을 재생해 평가, 실험 시간은 늘지 않음) ", font=(FONT, 11), padx=8, pady=6)
        mf.grid(row=6, column=0, columnspan=3, sticky="we")
        self.mvars = {}
        for i, (k, (label, files, desc)) in enumerate(L.MODELS.items()):
            v = tk.BooleanVar(value=k in L.RECOMMENDED); self.mvars[k] = v
            tk.Checkbutton(mf, variable=v, text=label + (f" · {desc}" if desc else "") + ("  ← 권장" if k in L.RECOMMENDED else ""),
                           font=(FONT, 10)).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 20))
        row = (len(L.MODELS) + 1) // 2
        bb = tk.Frame(mf); bb.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tk.Button(bb, text="권장만", command=lambda: self.pick(L.RECOMMENDED)).pack(side="left")
        tk.Button(bb, text="전체", command=lambda: self.pick(list(L.MODELS))).pack(side="left", padx=6)
        self.seeds = tk.IntVar(value=5)
        tk.Radiobutton(bb, text="시드 5개 평균", variable=self.seeds, value=5).pack(side="left", padx=(20, 0))
        tk.Radiobutton(bb, text="시드 1개(빠름)", variable=self.seeds, value=1).pack(side="left")

        tk.Label(f, text="스페이스: 다음 블록 · X: 방금 시행을 '지시와 다름'으로 표시 · P: 일시정지 · Esc: 중단(기록은 저장됨)",
                 font=(FONT, 10), fg="#555").grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 4))
        bx = tk.Frame(f); bx.grid(row=8, column=0, columnspan=3, pady=8)
        tk.Button(bx, text="실험 시작", font=(FONT, 14, "bold"), bg="#2a78d6", fg="white", padx=20, command=self.start).pack(side="left", padx=8)
        tk.Button(bx, text="중단된 회차 이어하기", font=(FONT, 12), command=self.pick_resume).pack(side="left", padx=8)
        self.resume_lbl = tk.Label(f, text="", font=(FONT, 10), fg="#2a78d6"); self.resume_lbl.grid(row=10, column=0, columnspan=3)
        if ARGS.resume:
            self.root.after(300, lambda: self.load_resume(ARGS.resume))
        if ARGS.fake:
            tk.Label(f, text="※ 시험 모드: 웹캠 대신 수집 데이터로 가짜 입력을 만듭니다. 결과를 실험으로 쓰지 마세요.", fg="red", font=(FONT, 10)).grid(row=9, column=0, columnspan=3)
        self.update_total()
        if ARGS.auto:
            self.root.after(500, self.start)

    def pick_resume(self):
        import glob
        cands = []
        for d in sorted(glob.glob(os.path.join(L.RESULTS, "*")), key=os.path.getmtime, reverse=True):
            try:
                m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
            except Exception:
                continue
            if m.get("status") in ("중단", "실패") and not m.get("resumed_by"):
                cands.append(d)
        if not cands:
            messagebox.showinfo("이어하기", "이어할 중단된 회차가 없습니다."); return
        self.load_resume(cands[0])

    def load_resume(self, d):
        meta, rem, order = L.resume_plan(d)
        if not order:
            messagebox.showinfo("이어하기", "남은 지시가 없습니다."); return
        self.resume = {"from": os.path.basename(d), "dir": d, "counts": rem}
        self.name.set(meta["name"]); self.cond.set(meta.get("condition", L.CONDITIONS[0])); self.memo.set(meta.get("memo", ""))
        self.rep.set(meta.get("repeat", 1)); self.intrain.set(str(meta.get("in_training_data", "")).startswith("예"))
        for k, v in self.bvars.items():
            v.set(k in order)
        for k, v in self.mvars.items():
            v.set(k in meta.get("analysis_models", L.RECOMMENDED))
        txt = ", ".join(f"{L.BLOCKS[k]['name']} " + (f"{sum(rem[k].values())}개" if k in rem else "전체") for k in order)
        self.resume_lbl.config(text=f"이어하기: {os.path.basename(d)} → 남은 것: {txt}  (설정 확인 후 [실험 시작])")
        self.update_total()

    def preset(self, cond, blocks, rep):
        self.cond.set(cond); self.rep.set(rep)
        for k, v in self.bvars.items():
            v.set(k in blocks)
        self.update_total()

    def pick(self, keys):
        for k, v in self.mvars.items():
            v.set(k in keys)

    def plan(self):
        return [k for k in L.BLOCK_ORDER if self.bvars[k].get()]

    def update_total(self):
        s = 0
        try:
            r = max(1, int(self.rep.get()))
        except Exception:
            r = 1
        for k in self.plan():
            b = L.BLOCKS[k]
            s += b["sec"] if b["kind"] == "idle" else sum(b["cues"].values()) * (b["window"] + b["rest"]) * (r if k in L.REPEATABLE else 1)
        self.total.config(text=f"예상 소요: 약 {s / 60 + 2:.0f}분 (준비·쉬는 시간 포함)")

    # ------------------------------------------------------------ 실행 화면
    def start(self):
        if not self.plan():
            messagebox.showwarning("실험", "블록을 하나 이상 고르세요."); return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.sock.bind(("127.0.0.1", 4242)); self.sock.settimeout(0.2)
        except OSError:
            messagebox.showerror("실험", "UDP 4242 포트를 쓸 수 없습니다. 게임이나 이전 실험 창이 켜져 있으면 끄고 다시 시작하세요."); return
        name = "".join(ch for ch in self.name.get() if ch.isalnum()) or "A"
        self.dir = os.path.join(L.RESULTS, time.strftime("%Y%m%d_%H%M%S") + f"_{name}" + ("_시험" if ARGS.fake else ""))
        os.makedirs(self.dir, exist_ok=True)
        self.log_path = os.path.join(self.dir, "frames.jsonl"); open(self.log_path, "w").close()
        self.state_path = os.path.join(self.dir, "state.json"); self.set_state("none")
        self.models_sel = [k for k, v in self.mvars.items() if v.get()]
        self.meta = {"name": name, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "fake": ARGS.fake, "speed": SPEED,
                     "camera_index": int(self.cam.get() or 0), "game_settings": self.cfg, "profile": "precise",
                     "live_model": os.path.join(L.TOOLS, "pose_classifier_seq_len4.keras"), "live_model_sha": sha(os.path.join(L.TOOLS, "pose_classifier_seq_len4.keras")),
                     "game_version": L.GAME_VERSION,
                     "game_code": os.path.join(L.TOOLS, "udp_send_webcam_ml.py"), "game_code_sha": sha(os.path.join(L.TOOLS, "udp_send_webcam_ml.py")),
                     "python": L.PY, "platform": platform.platform(), "plan": self.plan(),
                     "plan_counts": {k: sum(L.BLOCKS[k].get("cues", {}).values()) for k in self.plan() if L.BLOCKS[k]["kind"] != "idle"},
                     "analysis_models": self.models_sel, "analysis_seeds": self.seeds.get(),
                     "continues": self.resume["from"] if self.resume else None,
                     "condition": self.cond.get(), "memo": self.memo.get(), "repeat": max(1, int(self.rep.get())), "in_training_data": "예" if self.intrain.get() else "아니오"}
        self.meta["plan_counts"] = {k: sum(L.BLOCKS[k].get("cues", {}).values()) * (self.meta["repeat"] if k in L.REPEATABLE else 1)
                                    for k in self.plan() if L.BLOCKS[k]["kind"] not in ("idle", "practice")}
        if self.resume:
            self.meta["plan_counts"] = {k: sum(v.values()) for k, v in self.resume["counts"].items()}
            try:
                pm = os.path.join(self.resume["dir"], "meta.json"); m = json.load(open(pm, encoding="utf-8"))
                m["resumed_by"] = os.path.basename(self.dir); json.dump(m, open(pm, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except Exception:
                pass
        self.awake = L.keep_awake(True); self.meta["keep_awake"] = self.awake
        self.launch_bridge()
        self.setup.destroy()
        r = self.root
        top = tk.Frame(r, bg="#222"); top.pack(fill="x")
        self.st = {}
        for k in ("cam", "person", "cpu", "input", "prog"):
            lab = tk.Label(top, text="", font=(FONT, 12, "bold"), bg="#222", fg="white", padx=12, pady=6); lab.pack(side="left"); self.st[k] = lab
        self.big = tk.Label(r, text="", font=(FONT, 56, "bold")); self.big.pack(pady=(16, 0))
        self.img = tk.Label(r); self.img.pack()
        self.refs = {}
        for lab in L.C:
            p = os.path.join(L.REF_DIR, lab + ".png")
            if os.path.exists(p):
                try:
                    self.refs[lab] = tk.PhotoImage(file=p)
                except Exception:
                    pass
        self.small = tk.Label(r, text="", font=(FONT, 17), wraplength=900); self.small.pack(pady=4)
        self.fb = tk.Label(r, text="", font=(FONT, 20), fg="#2a78d6"); self.fb.pack(pady=4)
        self.bar = ttk.Progressbar(r, length=900, mode="determinate"); self.bar.pack(pady=12)
        self.foot = tk.Label(r, text=FOOT, font=(FONT, 10), fg="gray"); self.foot.pack(pady=(0, 8))
        r.bind("<space>", lambda e: self.go.set()); r.bind("<Escape>", lambda e: self.do_abort())
        self.flags = set(); self.cur_idx = None; self.paused = False; self._cpu_prev = _systimes()
        for key in ("<KeyPress-x>", "<KeyPress-X>"):
            r.bind(key, self.on_flag)
        for key in ("<KeyPress-p>", "<KeyPress-P>"):
            r.bind(key, self.on_pause)
        r.protocol("WM_DELETE_WINDOW", self.do_abort)
        threading.Thread(target=self.rx, daemon=True).start()
        threading.Thread(target=self.tail, daemon=True).start()
        threading.Thread(target=self.script, daemon=True).start()
        self.tick()

    def launch_bridge(self):
        env = dict(os.environ, BH_LOG_PATH=self.log_path, PYTHONIOENCODING="utf-8")
        self.out_f = open(os.path.join(self.dir, "bridge_stdout.txt"), "w", encoding="utf-8")
        if ARGS.fake:
            cmd = [L.PY, os.path.join(L.HERE, "fake_bridge.py"), "--log", self.log_path, "--state", self.state_path, "--speed", str(SPEED)]
        else:
            br = os.path.join(self.dir, "udp_send_webcam_ml_logged.py")
            L.make_logged_bridge(br); self.meta["bridge_copy_sha"] = sha(br)
            cmd = [L.PY, br, "--camera-index", str(self.meta["camera_index"]), "--camera-backend", str(self.cfg["backend"]),
                   "--profile", "precise", "--center-zone", str(self.cfg["center_zone_margin"]), "--seq-model", self.meta["live_model"]]
            if self.cfg.get("skip_guard_single"):
                cmd.append("--skip-guard-single")
            if self.cfg.get("full_body_squat"):
                cmd.append("--full-body-squat")
        self.meta["bridge_cmd"] = cmd
        self.proc = subprocess.Popen(cmd, cwd=L.TOOLS, env=env, stdout=self.out_f, stderr=subprocess.STDOUT)

    def on_flag(self, e=None):
        if self.cur_idx:
            self.flags.add(self.cur_idx)
            self.fb.config(text="방금 시행을 '지시와 다름'으로 표시했습니다", fg="#d97706")

    def on_pause(self, e=None):
        self.paused = not self.paused
        self.foot.config(text="일시정지: 다음 지시 전에 멈춥니다 (P로 계속)" if self.paused else FOOT)

    def set_state(self, label, quit=False):
        try:
            json.dump({"label": label, "quit": quit}, open(self.state_path, "w", encoding="utf-8"))
        except Exception:
            pass

    # ------------------------------------------------------------ 백그라운드
    def rx(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(1024)
            except socket.timeout:
                if getattr(self, "closed", False):
                    return
                continue
            except OSError:
                return
            t = time.perf_counter(); a = data.decode("utf-8", "ignore").strip()
            self.events.append((t, a)); self.last_action = (t, a); self.q.put(("action", a))

    def tail(self):
        pos = 0; part = ""
        while not getattr(self, "closed", False):
            try:
                with open(self.log_path, encoding="utf-8") as f:
                    f.seek(pos); chunk = f.read(); pos = f.tell()
            except Exception:
                chunk = ""
            part += chunk; lines = part.split("\n"); part = lines.pop()
            for ln in lines:
                if '"k":"f"' in ln:
                    try: self.f_times.append(json.loads(ln)["t"])
                    except Exception: pass
                elif '"k":"a"' in ln:
                    i = ln.find('"t":'); j = ln.find(",", i)
                    try: self.a_times.append(float(ln[i + 4:j]))
                    except Exception: pass
            if len(self.f_times) > 3000:
                self.f_times = self.f_times[-1000:]
            if len(self.a_times) > 3000:
                self.a_times = self.a_times[-1000:]
            time.sleep(0.2)

    def stats(self):
        now = time.perf_counter(); win = 2.0 / SPEED
        f = [t for t in self.f_times[-400:] if t > now - win]; a = [t for t in self.a_times[-400:] if t > now - win]
        fps = len(f) / win / SPEED if f else 0.0
        det = len(a) / len(f) if f else 0.0
        return fps, min(1.0, det)

    def tick(self):
        if getattr(self, "closed", False):
            return
        fps, det = self.stats()
        ok_cam = fps >= 25; ok_p = det >= 0.95
        self.st["cam"].config(text=f"카메라 {fps:4.1f} FPS", fg="#7CFC00" if ok_cam else ("#FFD700" if fps >= 15 else "#FF6347"))
        self.st["person"].config(text=f"사람 인식 {det * 100:3.0f}%", fg="#7CFC00" if ok_p else ("#FFD700" if det >= 0.8 else "#FF6347"))
        if self.last_action:
            ago = (time.perf_counter() - self.last_action[0]) * SPEED
            self.st["input"].config(text=f"마지막 입력: {L.KO.get(self.last_action[1], self.last_action[1])} ({ago:.1f}초 전)")
        else:
            self.st["input"].config(text="마지막 입력: 없음")
        self.cam_ok = ok_cam and ok_p
        try:
            cur = _systimes()
            if cur and self._cpu_prev and cur != self._cpu_prev:
                di, dk, du = (cur[j] - self._cpu_prev[j] for j in range(3))
                busy = min(1.0, max(0.0, (dk + du - di) / max(1, dk + du)))
                self.st["cpu"].config(text=f"CPU {busy * 100:3.0f}%", fg="#7CFC00" if busy < 0.8 else ("#FFD700" if busy < 0.95 else "#FF6347"))
                self.cpu_hist = getattr(self, "cpu_hist", []) + [busy]
            self._cpu_prev = cur
        except Exception:
            pass
        while not self.q.empty():
            kind, *val = self.q.get()
            if kind == "show":
                big, small, color, ref = val; self.big.config(text=big, fg=color); self.small.config(text=small)
                self.img.config(image=self.refs.get(ref, "") if ref else "")
            elif kind == "prog":
                done, total, label = val; self.bar.config(maximum=max(1, total), value=done); self.st["prog"].config(text=label)
            elif kind == "action":
                a = val[0]; self.fb.config(text=f"인식: {L.KO.get(a, a)}", fg="#2a78d6")
                if getattr(self, "flash_on", False) and a in L.ATTACK:
                    self.root.configure(bg="white"); self.big.configure(bg="white")
                    self.root.after(120, lambda: (self.root.configure(bg="black"), self.big.configure(bg="black")))
            elif kind == "flashmode":
                self.flash_on = val[0]; bg = "black" if val[0] else self.root.cget("bg")
                if val[0]:
                    self.root.configure(bg="black"); self.big.configure(bg="black")
            elif kind == "done":
                self.finish(val[0]); return
        self.root.after(50, self.tick)

    # ------------------------------------------------------------ 실험 진행 (작업 스레드)
    def wait(self, sec):
        end = time.perf_counter() + sec / SPEED
        while time.perf_counter() < end:
            if self.abort:
                raise KeyboardInterrupt
            time.sleep(0.01)

    def wait_space(self):
        self.go.clear()
        if ARGS.auto:
            self.wait(0.5); return
        while not self.go.wait(0.05):
            if self.abort:
                raise KeyboardInterrupt

    def show(self, big, small="", color="black", ref=None):
        self.q.put(("show", big, small, color, ref))

    def script(self):
        self.blocks = []; self.cues = []; status = "완료"
        try:
            self.show("카메라 준비 중", "인식 모듈을 켜는 중입니다(10~30초). 미리보기 창이 뜨면 몸 전체가 보이게 서 주세요.", "gray")
            t0 = time.perf_counter()
            while True:
                self.wait(0.5)
                if self.proc.poll() is not None:
                    self.show("인식 모듈 오류", "인식 모듈이 꺼졌습니다. 결과 폴더의 bridge_stdout.txt를 확인하세요.", "red"); status = "실패"; raise KeyboardInterrupt
                if getattr(self, "cam_ok", False):
                    break
                if time.perf_counter() - t0 > 90 / SPEED:
                    self.show("카메라 확인", "90초가 지나도 사람이 안정적으로 잡히지 않습니다. 위 표시가 초록색이 되게 자리를 맞춘 뒤 스페이스.", "orange")
                    self.wait_space(); break
            plan = self.meta["plan"]
            for bi, k in enumerate(plan, 1):
                b = L.BLOCKS[k]
                self.show(f"{bi}/{len(plan)} {b['name']}", b["guide"] + "\n준비되면 스페이스", "#2a78d6")
                self.q.put(("prog", 0, 1, f"블록 {bi}/{len(plan)}"))
                self.wait_space()
                for n in (3, 2, 1):
                    self.show(str(n), "대기 자세", "gray"); self.wait(1)
                rec = {"key": k, "name": b["name"], "kind": b["kind"], "t_start": time.perf_counter(), "t_end": None, "completed": "0"}
                self.blocks.append(rec)
                try:
                    if b["kind"] == "idle":
                        self.set_state("none"); total = b["sec"]; t_s = time.perf_counter()
                        while (time.perf_counter() - t_s) * SPEED < total:
                            left = total - (time.perf_counter() - t_s) * SPEED
                            self.show("공격하지 마세요", f"{b['guide']}\n남은 시간 {left:4.0f}초", "gray", None if k == "idle_still" else "none")
                            self.q.put(("prog", total - left, total, f"블록 {bi}/{len(plan)} {b['name']}")); self.wait(0.25)
                    else:
                        reps = self.meta["repeat"] if k in L.REPEATABLE else 1
                        counts = self.resume["counts"][k] if self.resume and k in self.resume["counts"] else {c: n * reps for c, n in b["cues"].items()}
                        seq = [c for c, n in counts.items() for _ in range(n)]
                        random.Random(f"{self.meta['name']}-{k}-{self.meta['started']}").shuffle(seq)
                        if b["kind"] == "flash":
                            self.q.put(("flashmode", True))
                        for i, c in enumerate(seq, 1):
                            while self.paused:
                                self.show("일시정지", "P를 누르면 계속합니다", "orange"); self.wait(0.2)
                            self.set_state("none"); self.show("준비 자세", f"{i}/{len(seq)}", "gray", "none"); self.wait(b["rest"])
                            t = time.perf_counter(); self.set_state(c); self.cur_idx = f"{k}-{i}"
                            word = "왼손 → 오른손 (한 번씩)!" if c == "combo" else L.KO[c] + "!"
                            self.show(word, f"{i}/{len(seq)}", "red" if b["kind"] != "flash" else "white",
                                      None if c == "combo" or b["kind"] == "flash" else c)
                            try:
                                import winsound; winsound.Beep(880, 60)
                            except Exception:
                                pass
                            self.wait(b["window"])
                            self.cues.append({"block": k, "idx": f"{k}-{i}", "cue": c, "t_cue": t, "t_end": t + (b["window"] + b["rest"]) / SPEED, "flag": 0})
                            self.q.put(("prog", i, len(seq), f"블록 {bi}/{len(plan)} {b['name']} {i}/{len(seq)}"))
                        self.q.put(("flashmode", False)); self.set_state("none"); self.wait(b["rest"])
                    rec["completed"] = "1"
                finally:
                    rec["t_end"] = time.perf_counter()
            self.show("끝!", "기록을 저장하고 점검하는 중입니다...", "green")
        except KeyboardInterrupt:
            if status != "실패":
                status = "중단"
        self.q.put(("done", status))

    def do_abort(self):
        if getattr(self, "closed", False):
            if getattr(self, "an_done", 0) is None and not messagebox.askyesno("분석 중", "분석이 아직 끝나지 않았습니다. 그래도 닫을까요? 기록은 저장되어 있고, 나중에 결과_다시_분석 파일로 분석할 수 있습니다."):
                return
            L.keep_awake(False); self.root.destroy(); return
        if ARGS.auto or messagebox.askyesno("실험 중단", "실험을 멈출까요? 지금까지 기록은 저장됩니다."):
            self.abort = True

    # ------------------------------------------------------------ 저장과 분석
    def finish(self, status):
        self.set_state("none", quit=True)
        time.sleep(0.5)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(5)
            except Exception: self.proc.kill()
        self.closed = True
        try: self.sock.close()
        except Exception: pass
        # 마지막 지시의 범위가 블록 끝을 넘지 않게
        for c in self.cues:
            b = next(b for b in self.blocks if b["key"] == c["block"])
            c["t_end"] = min(c["t_end"], b["t_end"])
            c["flag"] = 1 if c["idx"] in self.flags else 0
        ch = getattr(self, "cpu_hist", [])
        self.meta.update(status=status, ended=time.strftime("%Y-%m-%d %H:%M:%S"), flagged=len(self.flags),
                         cpu_mean=round(sum(ch) / len(ch) * 100, 1) if ch else None, cpu_max=round(max(ch) * 100, 1) if ch else None)
        json.dump(self.meta, open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with open(os.path.join(self.dir, "events.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["t", "action"]); w.writerows(self.events)
        with open(os.path.join(self.dir, "cues.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["block", "idx", "cue", "t_cue", "t_end", "flag"]); w.writeheader(); w.writerows(self.cues)
        with open(os.path.join(self.dir, "blocks.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["key", "name", "kind", "t_start", "t_end", "completed"]); w.writeheader()
            w.writerows([b for b in self.blocks if b["t_end"] is not None])
        try: os.remove(self.state_path)
        except Exception: pass
        L.keep_awake(False)
        self.big.config(text="분석 중", fg="green", bg=self.root.cget("bg")); self.img.config(image="")
        self.small.config(text="기록 점검과 모델 재생 평가를 하고 있습니다(1~5분). 창을 닫지 마세요. 기록은 이미 저장되었습니다.")
        cmd = [L.PY, os.path.join(L.HERE, "analyze_session.py"), self.dir, "--models", ",".join(self.models_sel) or "recommended",
               "--seeds", str(self.meta["analysis_seeds"])]
        self.an_lines = []; self.an_done = None

        def run():
            p = subprocess.Popen(cmd, cwd=L.HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore",
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            for line in p.stdout:
                self.an_lines.append(line)
            self.an_done = p.wait()
        threading.Thread(target=run, daemon=True).start()
        self.poll_analysis(status)

    def poll_analysis(self, status):
        done = [l for l in self.an_lines if "모델 평가 완료" in l]
        total = max(1, len(self.models_sel))
        self.bar.config(maximum=total, value=len(done))
        self.fb.config(text=f"모델 평가 {len(done)}/{total}", fg="#2a78d6")
        if self.an_done is None:
            self.root.after(300, lambda: self.poll_analysis(status)); return
        open(os.path.join(self.dir, "analysis_log.txt"), "w", encoding="utf-8").write("".join(self.an_lines))
        self.show_result(status, self.an_done == 0)

    def show_result(self, status, ok):
        for wdg in list(self.root.children.values()):
            wdg.destroy()
        self.root.configure(bg=self.root.cget("bg"))
        t = tk.Text(self.root, font=(FONT, 11), wrap="word"); t.pack(fill="both", expand=True, padx=10, pady=10)
        md = os.path.join(self.dir, "결과요약.md")
        head = f"실험 {status}. 저장 위치: {self.dir}\n\n"
        if ok and os.path.exists(md):
            t.insert("1.0", head + open(md, encoding="utf-8").read())
        else:
            t.insert("1.0", head + "분석에 실패했습니다. analysis_log.txt를 확인하거나 결과_다시_분석.bat을 실행하세요.\n\n"
                     + open(os.path.join(self.dir, "analysis_log.txt"), encoding="utf-8").read()[-3000:])
        bf = tk.Frame(self.root); bf.pack(pady=6)
        tk.Button(bf, text="결과 폴더 열기", command=lambda: os.startfile(self.dir)).pack(side="left", padx=6)
        tk.Button(bf, text="닫기", command=self.root.destroy).pack(side="left", padx=6)
        if ARGS.auto:
            self.root.after(1500, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    Lab(root)
    root.mainloop()
