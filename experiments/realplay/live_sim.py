# -*- coding: utf-8 -*-
"""게임 인식 코드(udp_send_webcam_ml.py, Precise)의 판정 규칙을 그대로 옮긴 재생 시뮬레이터.
기록한 관절 좌표를 모델에 넣고, 게임과 같은 규칙(임계값·히스테리시스·확정 프레임·쿨다운·같은 손 재무장·어퍼컷 뒤 펀치 보류·
어퍼컷 동작량 게이팅·좌우 어퍼컷 교차 차단·가드 처리)으로 실제 게임에 나갔을 입력을 다시 만든다.
게임 코드는 바꾸지 않는다. 보완 후보는 옵션으로 켠다.
- 예측 지연: 게임은 분류를 별도 스레드에서 돌려 직전 예측을 쓰므로 기본 1프레임 늦게 반영한다(lag)."""
import os
import numpy as np

C = ["none", "guard", "punch_l", "punch_r", "upper_l", "upper_r", "squat"]
PUNCH_LABELS = ("punch_l", "punch_r", "upper_l", "upper_r")
POWER = ("upper_l", "upper_r")
# Precise
CONF_T, UPPER_T, PUNCH_T = 0.95, 0.90, 0.88
PUNCH_CONFIRM, UPPER_CONFIRM, SQUAT_CONFIRM = 2, 2, 3
COOLDOWN = 0.12
UPPER_MOTION_MIN, UPPER_L_RELAX = 0.0020, 0.65
HOLDOFF_AFTER_UPPER, NONE_STREAK_CLEAR, UPPER_LR_BLOCK, GUARD_EXIT = 4, 3, 6, 2
WINDUP_MARGIN = 0.08


def run(frames, probs_by_frame, opts=None):
    """frames: [(t, kind, flat)] kind in ('a','c'). probs_by_frame: {프레임 순번: 확률(7)} (창이 찬 'a' 프레임만).
    opts: punch_confirm, windup_suppress('as_coded'|'fixed'|None), punch_delay(프레임), lag, upper_after_punch(bool)
    반환: [(t, action)]"""
    o = dict(punch_confirm=PUNCH_CONFIRM, windup=None, punch_delay=0, lag=1, upper_after_punch=False)
    o.update(opts or {})
    ev = []
    ema = None; active = None
    pred_queue = []           # 지연된 예측
    prev_flat = None; motion = 0.0
    none_streak = 0; side_none = 0; last_sent_side = ""; squat_count = 0; squat_armed = True
    holdoff = 0; guarding = False; guard_exit = 0
    pl = pr = 0; other_pred = None; other_cnt = 0
    last_action_time = -1e9; last_l = -1e9; last_r = -1e9
    last_upper_side = ""; upper_block_until = 0
    pending = None            # (action, 발동 예정 프레임, side) : punch_delay 후보용
    last_flat = None
    for fi, (t, kind, flat) in enumerate(frames):
        if kind == "c":
            ema = None; active = None; prev_flat = None; motion = 0.0; pred_queue.clear(); last_flat = None
            label = "none"
        else:
            last_flat = flat
            motion = float(np.mean(np.abs(np.asarray(flat) - np.asarray(prev_flat)))) if prev_flat is not None else 1.0
            prev_flat = flat
            if fi in probs_by_frame:
                pred_queue.append(probs_by_frame[fi])
            label = "none"
            if len(pred_queue) > o["lag"]:
                p = pred_queue.pop(0)
                ema = p.copy() if ema is None else 0.7 * p + 0.3 * ema
                ri = int(np.argmax(p)); rl = C[ri]; rc = float(p[ri])
                need = UPPER_T if rl in POWER else (PUNCH_T if rl in ("punch_l", "punch_r") else CONF_T)
                if rc < need:
                    rl = "none"
                ema_conf = float(ema[active]) if active is not None else 0.0
                if rl == "none":
                    if active is not None and ema_conf >= 0.60:
                        label = C[active]
                    else:
                        label = "none"; active = None
                else:
                    label = rl
                    if active is None:
                        active = ri
                    elif active != ri and float(p[ri]) > float(ema[active]) + 0.05:
                        active = ri
        pred = label
        # ---- 게임 판정 규칙
        if pred == "none":
            none_streak += 1
            if none_streak >= NONE_STREAK_CLEAR:
                holdoff = 0
        else:
            none_streak = 0
        if pred in PUNCH_LABELS:
            side_none = 0
        else:
            side_none += 1
            if side_none >= 2:
                last_sent_side = ""
        if pred == "squat":
            squat_count += 1
        else:
            squat_count = 0; squat_armed = True
        if pred in POWER:
            holdoff = max(holdoff, fi + HOLDOFF_AFTER_UPPER)
            if pending and pending[2] == pred[-1]:
                pending = None          # 보완안: 기다리던 같은 손 펀치를 어퍼컷으로 취소
        action = None; now = t
        if pending and fi >= pending[1]:
            action = pending[0]; pending = None
        elif pred == "guard":
            guard_exit = 0; pl = pr = 0; other_pred = None; other_cnt = 0
            if not guarding and (now - last_action_time) >= 0.15:
                action = "guard"; guarding = True
        else:
            if guarding:
                pl = pr = 0; other_pred = None; other_cnt = 0
                guard_exit += 1
                if guard_exit >= GUARD_EXIT:
                    action = "guard_end"; guarding = False
            if action is None and (now - last_action_time) >= COOLDOWN:
                allowed = fi >= holdoff
                if pred in ("punch_l", "punch_r"):
                    other_pred = None; other_cnt = 0
                    low = False
                    if o["windup"] and last_flat is not None:
                        if o["windup"] == "as_coded":   # 게임 코드 그대로: punch_l은 15번, punch_r은 16번 손목
                            w = 15 if pred == "punch_l" else 16; s_ = 11 if pred == "punch_l" else 12
                        else:                            # 손 대응을 학습 데이터에 맞춘 경우: punch_l은 16번, punch_r은 15번
                            w = 16 if pred == "punch_l" else 15; s_ = 12 if pred == "punch_l" else 11
                        low = last_flat[3 * w + 1] > last_flat[3 * s_ + 1] + WINDUP_MARGIN
                    if pred == "punch_l":
                        pr = 0; pl = pl + 1 if (allowed and not low) else 0
                        if pl >= o["punch_confirm"]:
                            action = "punch_l"; pl = 0
                    else:
                        pl = 0; pr = pr + 1 if (allowed and not low) else 0
                        if pr >= o["punch_confirm"]:
                            action = "punch_r"; pr = 0
                    if action and o["punch_delay"] > 0:
                        pending = (action, fi + o["punch_delay"], action[-1]); action = None
                elif pred in POWER:
                    pl = pr = 0
                    block = (pred == "upper_r" and fi < upper_block_until and last_upper_side == "l") or \
                            (pred == "upper_l" and fi < upper_block_until and last_upper_side == "r")
                    mmin = UPPER_MOTION_MIN * (UPPER_L_RELAX if pred == "upper_l" else 1.0)
                    ok = motion >= mmin or other_cnt > 0
                    if block or not ok:
                        other_pred = None; other_cnt = 0
                    elif pred == other_pred:
                        other_cnt += 1
                    else:
                        other_pred = pred; other_cnt = 1
                    if other_cnt >= UPPER_CONFIRM:
                        action = pred; other_pred = None; other_cnt = 0
                elif pred == "squat":
                    pl = pr = 0; other_pred = None; other_cnt = 0
                    if squat_armed and squat_count >= SQUAT_CONFIRM:
                        action = "squat"; squat_armed = False
                else:
                    if pred != "none":
                        pl = pr = 0; other_pred = None; other_cnt = 0
        if guarding and action in PUNCH_LABELS:
            action = None
        if action in PUNCH_LABELS:
            st = last_l if action[-1] == "l" else last_r
            if (now - st) < COOLDOWN:
                action = None; pl = pr = 0; other_pred = None; other_cnt = 0
        if action in PUNCH_LABELS:
            side = action[-1]
            same = side == last_sent_side
            if same and o["upper_after_punch"] and action in POWER:
                same = False                    # 보완안: 같은 손 펀치 직후의 어퍼컷은 허용
            if same:
                action = None; pl = pr = 0; other_pred = None; other_cnt = 0
        if action:
            ev.append((t, action)); last_action_time = now
            if action in PUNCH_LABELS:
                if action[-1] == "l":
                    last_l = now
                else:
                    last_r = now
                if action in POWER:
                    last_upper_side = action[-1]; upper_block_until = fi + UPPER_LR_BLOCK
                    holdoff = max(holdoff, fi + HOLDOFF_AFTER_UPPER)
                last_sent_side = action[-1]
    return ev


def frames_and_probs(recs, model, L_):
    """기록에서 프레임 목록과 창 확률(게임과 같은 버퍼 규칙)을 만든다."""
    frames = []; idx = []; wins = []; buf = []
    for r in recs:
        if r["k"] == "c":
            frames.append((r["t"], "c", None)); buf = []
        elif r["k"] == "a":
            frames.append((r["t"], "a", r["d"])); buf.append(r["d"]); buf = buf[-L_:]
            if len(buf) == L_:
                idx.append(len(frames) - 1); wins.append(list(buf))
    P = model.predict(np.asarray(wins, np.float32), batch_size=4096, verbose=0) if wins else []
    return frames, {i: p for i, p in zip(idx, P)}
