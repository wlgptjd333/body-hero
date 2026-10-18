# -*- coding: utf-8 -*-
"""실플레이 실험 공통 설정: 경로, 모델 목록, 실험 블록 정의, 후처리 시뮬레이션, 게임 인식 코드 사본 만들기."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\User\Documents\body-hero"
ORIG_TOOLS = os.path.join(ROOT, "tools")
# 실험할 게임 인식 코드 폴더. 기본은 원래 게임(v1.0.0 기준 작업 폴더), v1.1 확인 실험은 BH_TOOLS로 body-hero-rebuild/tools 지정
TOOLS = os.environ.get("BH_TOOLS", ORIG_TOOLS)
GAME_VERSION = "v1.1 (body-hero-rebuild)" if "rebuild" in TOOLS else "v1.0.0"
PY = os.path.join(ROOT, ".venv_thesis_ml", "Scripts", "python.exe")
THESIS = os.path.dirname(HERE)
R0 = os.path.join(THESIS, "재실험_2x2_증강수정", "results")
R1 = os.path.join(THESIS, "재실험_추가_v15", "results")
RESULTS = os.path.join(HERE, "results")
GODOT_CFG = os.path.join(os.environ.get("APPDATA", ""), "Godot", "app_userdata", "Body Hero", "display_settings.cfg")

C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
KO = {"none": "대기", "guard": "가드", "punch_l": "왼손 펀치", "punch_r": "오른손 펀치",
      "upper_l": "왼손 어퍼컷", "upper_r": "오른손 어퍼컷", "squat": "스쿼트"}
ATTACK = {"punch_l", "punch_r", "upper_l", "upper_r"}

# ---------------------------------------------------------------- 모델 목록
# key: (표시 이름, 파일 목록, 설명). 반복 비교 모델은 고정 분할의 5개 시드(42~46). 시드 1개만 쓰려면 분석에서 --seeds 1.
def _seeds(d, name):
    return [os.path.join(d, f"model_{name}_seed{s}.keras") for s in range(42, 47)]


MODELS = {
    "v11": ("게임 v1.1 모델", [os.path.join(ROOT + "-rebuild", "tools", "pose_classifier_seq_len4.keras")], "리빌딩 후 게임 모델"),
    "deployed": ("gap_g_seed44 (9/29 실험 모델, 배포본 아님)", [os.path.join(ORIG_TOOLS, "game_model_test", "gap_g_seed44.keras")], "1~3회차 실시간 판정에 쓴 모델"),
    "gap4": ("GAP 4프레임", _seeds(R0, "gap_seq4"), "논문 반복 비교 모델"),
    "lstm3": ("LSTM 3프레임", _seeds(R1, "lstm_seq3"), "논문 4.11~4.14절 비교 대상"),
    "lstm4": ("LSTM 4프레임", _seeds(R0, "lstm_seq4"), ""),
    "gap3": ("GAP 3프레임", _seeds(R1, "gap_seq3"), ""),
    "gap2": ("GAP 2프레임", _seeds(R0, "gap_seq2"), ""),
    "lstm2": ("LSTM 2프레임", _seeds(R0, "lstm_seq2"), ""),
    "mlp1": ("MLP 1프레임", _seeds(R0, "mlp_seq1"), ""),
    "gapwide4": ("GAP(확장) 4프레임", _seeds(R0, "gapwide_seq4"), ""),
    "gru4": ("GRU 4프레임", _seeds(R1, "gru_seq4"), ""),
    "gap6": ("GAP 6프레임", _seeds(R1, "gap_seq6"), ""),
    "gap8": ("GAP 8프레임", _seeds(R1, "gap_seq8"), ""),
    "lstm6": ("LSTM 6프레임", _seeds(R1, "lstm_seq6"), ""),
    "lstm8": ("LSTM 8프레임", _seeds(R1, "lstm_seq8"), ""),
    "reference": ("게임 v1.0.0 배포 모델 (논문 4.3절 평가 기준 모델)", [os.path.join(ORIG_TOOLS, "pose_classifier_seq_len4.keras")], "릴리스 zip에 들어 있는 모델"),
}
RECOMMENDED = ["v11", "reference", "gap4", "lstm3"]

# ---------------------------------------------------------------- 실험 블록
# kind: idle(공격하지 않기) / cue(지시 동작) / combo(두 손 연타) / flash(지연 측정용 화면 깜빡임)
REF_DIR = os.path.join(HERE, "ref")   # 동작 예시 사진(학습 데이터 녹화 화면에서 잘라 냄)
CONDITIONS = ["기본: 발까지 보임, 조명 켬", "조명 끔: 자연광 또는 어두움, 발까지 보임", "좁은 공간: 발이 잘림, 조명 켬", "기타(메모에 적기)"]
# 1시간 이내 계획의 회차 설정. (이름, 촬영 조건, 블록, 지시 블록 반복)
PRESETS = [
    ("① 본 실험 (약 17분)", CONDITIONS[0], ["practice", "idle_still", "idle_ready_l", "idle_ready_r", "idle_active", "cued", "fast", "angle"], 2),
    ("② 조명 끔 (약 7분)", CONDITIONS[1], ["idle_ready_l", "idle_ready_r", "cued", "fast"], 1),
    ("③ 좁은 공간 (약 6분)", CONDITIONS[2], ["idle_ready_l", "idle_ready_r", "cued"], 1),
    ("④ 다른 사람 (선택, 약 8분)", CONDITIONS[0], ["practice", "idle_ready_l", "idle_ready_r", "cued", "fast"], 1),
]
BLOCKS = {
    "practice": dict(name="연습 (분석 안 함)", kind="practice", default=True, window=2.5, rest=1.5,
                     cues={"punch_l": 2, "punch_r": 2, "upper_l": 2, "upper_r": 2, "guard": 1, "squat": 1},
                     guide="각 동작을 예시 사진처럼 해 보세요. 화면 아래 '인식'이 맞게 나오는지 확인만 하면 됩니다. 이 블록은 분석에 쓰지 않습니다."),
    "idle_still": dict(name="정자세 대기", kind="idle", sec=45, default=True,
                       guide="양발을 어깨너비로 나란히 두고 손은 편하게 내린 채 서 있으세요. 공격, 가드, 스쿼트는 하지 마세요."),
    "idle_ready_l": dict(name="준비 자세 대기 (왼발 앞)", kind="idle", sec=45, default=True,
                         guide="왼발을 앞에 두고 주먹을 턱 아래쯤 든 준비 자세(예시 사진의 대기 자세)로 서 있으세요. 공격하지 마세요. 가볍게 들썩이는 정도는 괜찮습니다."),
    "idle_ready_r": dict(name="준비 자세 대기 (오른발 앞)", kind="idle", sec=45, default=True,
                         guide="오른발을 앞에 두고 주먹을 턱 아래쯤 든 준비 자세로 서 있으세요. 공격하지 마세요. 가볍게 들썩이는 정도는 괜찮습니다."),
    "idle_active": dict(name="움직이며 대기", kind="idle", sec=45, default=True,
                        guide="준비 자세에서 제자리 스텝, 어깨 털기, 몸 흔들기를 해 주세요. 공격, 가드, 스쿼트는 하지 마세요."),
    "cued": dict(name="지시 동작", kind="cue", default=True, window=2.0, rest=2.0,
                 cues={"punch_l": 12, "punch_r": 12, "upper_l": 12, "upper_r": 12, "guard": 8, "squat": 8},
                 guide="화면의 동작을 예시 사진처럼 한 번만 하고 준비 자세로 돌아오세요. 펀치는 어깨 높이로 곧게, 어퍼컷은 아래에서 위로 올려 칩니다. 지시와 다르게 했으면 바로 X 키를 누르세요."),
    "fast": dict(name="빠른 잽", kind="cue", default=True, window=1.5, rest=1.5,
                 cues={"punch_l": 12, "punch_r": 12},
                 guide="지시가 나오면 어깨 높이로 최대한 빠르게 '툭' 치고 바로 거두세요. 한 번만 칩니다. 잘못했으면 X."),
    "combo": dict(name="좌우 연타", kind="combo", default=False, window=2.5, rest=2.0, cues={"combo": 12},
                  guide="지시가 나오면 왼손 한 번, 오른손 한 번(모두 2번)만 빠르게 이어서 치세요. 더 치지 마세요. 잘못했으면 X."),
    "angle": dict(name="비스듬히 서기", kind="cue", default=True, window=2.0, rest=2.0,
                  cues={"punch_l": 5, "punch_r": 5, "upper_l": 5, "upper_r": 5},
                  guide="왼발을 앞에 두고, 오른쪽 어깨가 뒤로 가게 몸을 약 30도 돌린 채로 지시 동작을 한 번씩 하세요. 블록 내내 이 자세를 유지하세요. 잘못했으면 X."),
    "flash": dict(name="화면 반응 지연 (선택, 휴대폰 슬로모션)", kind="flash", default=False, window=2.5, rest=2.5,
                  cues={"punch_r": 10},
                  guide="휴대폰 슬로모션으로 몸과 이 화면을 함께 찍으면서 오른손 펀치를 하세요. 입력이 들어오면 화면이 하얗게 깜빡입니다."),
}
BLOCK_ORDER = ["practice", "idle_still", "idle_ready_l", "idle_ready_r", "idle_active", "cued", "fast", "combo", "angle", "flash"]
REPEATABLE = {"cued", "fast", "combo", "angle"}   # 반복 횟수를 고를 수 있는 블록

# 게임 기본 프로파일(Precise)의 진입 임계값과 확인 프레임 (udp_send_webcam_ml.py, 논문 표 3)
PRECISE = {0: .95, 1: .95, 2: .88, 3: .88, 4: .90, 5: .90, 6: .95}
CONF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3}


def sim(P, thr=PRECISE, conf=CONF):
    """논문 4.7~4.13절과 같은 후처리 시뮬레이션(EMA 0.7, 진입 임계값, 확인 프레임, 해제 0.60). 반환: [(창 번호, 클래스)]."""
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
                if cnt >= conf[c]:
                    act = c; ev.append((k, c))
            else:
                cand = None; cnt = 0
    return ev


def read_game_settings():
    """게임 설정 파일에서 카메라·인식 옵션을 읽는다. 없으면 게임 기본값."""
    cfg = {"index": 0, "backend": "auto", "center_zone_margin": 0.3, "skip_guard_single": False, "full_body_squat": False}
    try:
        txt = open(GODOT_CFG, encoding="utf-8").read()
        for k in cfg:
            m = re.search(rf"^{k}=(.+)$", txt, re.M)
            if m:
                v = m.group(1).strip().strip('"')
                cfg[k] = (v == "true") if v in ("true", "false") else (float(v) if "." in v else (int(v) if v.isdigit() else v))
    except Exception:
        pass
    return cfg


# ---------------------------------------------------------------- 게임 인식 코드 사본 (기록 기능만 추가)
PATCHES = [
    # (찾을 문자열, 바꿀 문자열, 기대 개수)
    ('SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))\n',
     'SCRIPT_DIR = r"%s"\nsys.path.insert(0, SCRIPT_DIR)\n' % TOOLS
     + '_BH_LOG_PATH = os.environ.get("BH_LOG_PATH", "")\n_BH_LOG = None\n'
     + 'def _bh_log(kind, i, data=None):\n'
     + '    global _BH_LOG\n'
     + '    if not _BH_LOG_PATH:\n        return\n'
     + '    if _BH_LOG is None:\n        _BH_LOG = open(_BH_LOG_PATH, "a", encoding="utf-8")\n'
     + '    rec = {"k": kind, "t": time.perf_counter(), "i": i}\n'
     + '    if data is not None:\n        rec["d"] = data\n'
     + '    _BH_LOG.write(json.dumps(rec, separators=(",", ":")) + "\\n")\n'
     + '    if kind != "a":\n        _BH_LOG.flush()\n', 1),
    ('                frame_idx += 1\n',
     '                frame_idx += 1\n                _bh_log("f", frame_idx)\n', 1),
    ('                                sequence_buffer.append(last_flat)\n',
     '                                sequence_buffer.append(last_flat)\n'
     '                                _bh_log("a", frame_idx, [round(float(v), 5) for v in last_flat])\n', 1),
    ('\n                            sequence_buffer.clear()\n',
     '\n                            sequence_buffer.clear()\n                            _bh_log("c", frame_idx)\n', 1),
    ('\n                        sequence_buffer.clear()\n',
     '\n                        sequence_buffer.clear()\n                        _bh_log("c", frame_idx)\n', 1),
    ('            sock.sendto(action.encode("utf-8"), (GODOT_HOST, GODOT_PORT))\n',
     '            sock.sendto(action.encode("utf-8"), (GODOT_HOST, GODOT_PORT))\n            _bh_log("s", -1, action)\n', 1),
]


def make_logged_bridge(dst):
    """tools/udp_send_webcam_ml.py를 읽어 기록 기능만 추가한 사본을 dst에 쓴다. 게임 코드 자체는 바꾸지 않는다."""
    src_path = os.path.join(TOOLS, "udp_send_webcam_ml.py")
    s = open(src_path, encoding="utf-8").read()
    for a, b, n in PATCHES:
        cnt = s.count(a)
        if cnt != n:
            raise RuntimeError(f"게임 인식 코드가 예상과 다릅니다(패치 위치 {cnt}개, 기대 {n}개): {a.strip()[:60]}")
        s = s.replace(a, b)
    s = s.replace("import sys\n", "import sys\n", 1)
    open(dst, "w", encoding="utf-8").write(s)
    return src_path


def load_jsonl(path):
    out = []; bad = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                bad += 1
    return out, bad


# ---------------------------------------------------------------- 시행 품질, 이어하기, 화면 꺼짐 방지
AUTO_MIN_DET = 0.8    # 지시 구간에서 사람이 잡힌 프레임 비율이 이보다 낮으면 자동 제외
AUTO_MIN_FPS = 5.0    # 지시 구간 프레임률이 이보다 낮으면 자동 제외(카메라 멈춤). 어두우면 카메라가 10 FPS 안팎으로 떨어지는데, 그건 조건이므로 빼지 않는다


def trial_quality(recs, cues, speed=1.0):
    """지시마다 (프레임률, 사람 인식 비율)."""
    import numpy as np
    f = np.array([r["t"] for r in recs if r["k"] == "f"]); a = np.array([r["t"] for r in recs if r["k"] == "a"])
    out = {}
    for c in cues:
        t0, t1 = float(c["t_cue"]), float(c["t_end"])
        nf = int(((f >= t0) & (f < t1)).sum()); na = int(((a >= t0) & (a < t1)).sum())
        out[c["idx"]] = (nf / max(1e-6, t1 - t0) / speed, min(1.0, na / nf) if nf else 0.0)
    return out


def is_auto_bad(q):
    fps, det = q
    return det < AUTO_MIN_DET or fps < AUTO_MIN_FPS


def resume_plan(session_dir):
    """중단된 회차에서 남은 지시를 계산한다. 반환: (meta, {블록: {동작: 남은 개수}}, 남은 블록 순서)
    완료로 보는 지시: 표시(flag)되지 않았고 자동 제외 대상이 아닌 지시."""
    import csv
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    cues = list(csv.DictReader(open(os.path.join(session_dir, "cues.csv"), encoding="utf-8")))
    blocks = list(csv.DictReader(open(os.path.join(session_dir, "blocks.csv"), encoding="utf-8")))
    recs, _ = load_jsonl(os.path.join(session_dir, "frames.jsonl"))
    q = trial_quality(recs, cues, float(meta.get("speed", 1.0)))
    done_blocks = {b["key"] for b in blocks if b["completed"] == "1"}
    rem = {}; order = []
    for k in meta["plan"]:
        if k in done_blocks or BLOCKS[k]["kind"] == "practice":
            continue
        b = BLOCKS[k]
        if b["kind"] == "idle":
            order.append(k); continue
        reps = meta.get("repeat", 1) if k in REPEATABLE else 1
        want = {c: n * reps for c, n in b["cues"].items()}
        for c in cues:
            if c["block"] == k and int(c.get("flag") or 0) == 0 and not is_auto_bad(q[c["idx"]]):
                want[c["cue"]] -= 1
        want = {c: n for c, n in want.items() if n > 0}
        if want:
            rem[k] = want; order.append(k)
    return meta, rem, order


def keep_awake(on=True):
    """실험 중 화면 꺼짐과 절전을 막는다(Windows)."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else 0))
        return True
    except Exception:
        return False
