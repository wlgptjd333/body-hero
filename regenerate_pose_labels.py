"""
pose_data.json을 drop + 유지 N(또는 끝까지)으로 재라벨링.

주의: 현재 주 파이프라인은 tools/collect_pose_data.py → tools/train_pose_classifier_seq.py 입니다.
이 스크립트는 기존 pose_data.json을 사후 재라벨링할 때만 쓰는 레거시 보조 도구입니다.

방법 1) pose_recordings_meta.json 있음: --hold-frames N 또는 --hold-until-end.
방법 2) 메타 없음, 녹화 순서·횟수만 알 때: --structure "punch_l:100,none:70,punch_r:5" (jab_l/jab_r 등 옛 이름도 동일 처리)
        → 각 펀치 블록(60프레임)에서 임팩트를 계산해 drop+유지 적용.

--hold-until-end: 임팩트 이후 블록 끝까지 전부 동작 라벨 (hold_only로 녹화한 데이터도
  나중에 고정 유지로 바꾸려면 --hold-frames N만 주면 됨. 반대로 고정 유지 데이터를
  끝까지 쓰려면 --hold-until-end 주면 됨).

사용: python regenerate_pose_labels.py --hold-frames 5 --output pose_data.json
     python regenerate_pose_labels.py --hold-until-end --output pose_data.json
     python regenerate_pose_labels.py --structure "punch_l:100,none:70" --hold-until-end
"""
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
FRAMES_PER_RECORDING = 60
IMPACT_WINDOW_HALF = 1
WINDUP_DROP_FRAMES = 4
RECOVERY_DROP_FRAMES = 4
LABEL_DROP = "drop"

# 정규화 flat 랜드마크 인덱스 (99차원: 33*3). collect_pose_data와 동일
IDX = {"l_sh_x": 33, "l_sh_y": 34, "r_sh_x": 36, "r_sh_y": 37, "l_wr_x": 45, "r_wr_x": 48, "l_wr_y": 46, "r_wr_y": 49}


def _impact_frame_punch_l(frames_flat):
    ext = [f[IDX["l_wr_x"]] - f[IDX["l_sh_x"]] for f in frames_flat]
    return max(range(len(ext)), key=lambda i: ext[i]) if ext else 0


def _impact_frame_punch_r(frames_flat):
    ext = [f[IDX["r_wr_x"]] - f[IDX["r_sh_x"]] for f in frames_flat]
    return min(range(len(ext)), key=lambda i: ext[i]) if ext else 0


def _impact_frame_upper_l(frames_flat):
    ys = [f[IDX["l_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i]) if ys else 0


def _impact_frame_upper_r(frames_flat):
    ys = [f[IDX["r_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i]) if ys else 0


IMPACT_FN = {
    "punch_l": _impact_frame_punch_l,
    "punch_r": _impact_frame_punch_r,
    "jab_l": _impact_frame_punch_l,
    "jab_r": _impact_frame_punch_r,
    "hook_l": _impact_frame_punch_l,
    "hook_r": _impact_frame_punch_r,
    "upper_l": _impact_frame_upper_l,
    "upper_r": _impact_frame_upper_r,
}


def _parse_structure(s):
    """'punch_l:100,none:70,punch_r:5' → [(punch_l, 100), (none, 70), (punch_r, 5)]"""
    out = []
    for part in s.strip().split(","):
        part = part.strip()
        if ":" not in part:
            continue
        label, count = part.split(":", 1)
        label, count = label.strip(), int(count.strip())
        out.append((label, count))
    return out


def _relabel_block(out, start, count, label, impact_idx, hold_frames, recovery_frames=None, hold_until_end=False):
    rdf = 0 if hold_until_end else (recovery_frames if recovery_frames is not None else RECOVERY_DROP_FRAMES)
    action_low = max(0, impact_idx - IMPACT_WINDOW_HALF)
    if hold_until_end:
        action_high = count
    else:
        action_high = min(count, impact_idx + IMPACT_WINDOW_HALF + 1 + hold_frames)
    recovery_end = min(count, action_high + rdf)
    windup_start = max(0, impact_idx - WINDUP_DROP_FRAMES)
    for i in range(count):
        pos = start + i
        if pos >= len(out):
            break
        if action_low <= i < action_high:
            out[pos]["label"] = label
        elif windup_start <= i < action_low or action_high <= i < recovery_end:
            out[pos]["label"] = LABEL_DROP
        else:
            out[pos]["label"] = "none"


def main():
    parser = argparse.ArgumentParser(description="Re-label pose_data with drop + hold N")
    parser.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json path")
    parser.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json (optional if --structure)")
    parser.add_argument("--hold-frames", type=int, default=5, help="유지 구간 프레임 수 (--hold-until-end 미사용 시)")
    parser.add_argument("--hold-until-end", action="store_true", help="임팩트 이후 블록 끝까지 전부 동작 라벨 (회수 drop 없음)")
    parser.add_argument("--recovery-frames", type=int, default=4, help="Frames after action as recovery drop (default 4, --hold-until-end 시 무시)")
    parser.add_argument("--output", default=None, help="Output path (default: 입력 파일 덮어쓰기, 즉 pose_data.json 그대로)")
    parser.add_argument("--structure", type=str, default=None,
                        help='Recording order and counts, e.g. "punch_l:100,none:70,punch_r:5" (each recording = 60 frames)')
    args = parser.parse_args()

    if not os.path.isfile(args.data):
        print(f"데이터 없음: {args.data}")
        raise SystemExit(1)

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = [dict(item) for item in data]

    if args.structure:
        # 메타 없이 구조만으로 재라벨: 각 펀치 블록(60프레임)에서 임팩트 계산
        segments = _parse_structure(args.structure)
        if not segments:
            print("--structure 형식 예: punch_l:100,none:70,punch_r:5")
            raise SystemExit(1)
        total_frames = sum(n * FRAMES_PER_RECORDING for _, n in segments)
        if len(data) < total_frames:
            print(f"데이터 프레임 수({len(data)})가 구조 합계({total_frames})보다 적습니다.")
            raise SystemExit(1)
        punch_labels = set(IMPACT_FN.keys())
        rec_count = 0
        pos = 0
        for label, num_rec in segments:
            for _ in range(num_rec):
                start = pos
                pos += FRAMES_PER_RECORDING
                if label in punch_labels:
                    block = [data[i]["landmarks"] for i in range(start, min(start + FRAMES_PER_RECORDING, len(data)))]
                    if len(block) < FRAMES_PER_RECORDING:
                        continue
                    impact_idx = IMPACT_FN[label](block)
                    _relabel_block(out, start, FRAMES_PER_RECORDING, label, impact_idx, args.hold_frames, args.recovery_frames, args.hold_until_end)
                    rec_count += 1
        mode = "임팩트~끝" if args.hold_until_end else f"유지 {args.hold_frames}프레임"
        print(f"구조 기반 재라벨: {rec_count}개 펀치 블록, {mode}")
    else:
        if not os.path.isfile(args.meta):
            print(f"메타 없음: {args.meta}")
            print('  메타 없이 재라벨하려면 --structure "punch_l:100,none:70,punch_r:5" 처럼 녹화 순서·횟수를 지정하세요.')
            raise SystemExit(1)
        with open(args.meta, "r", encoding="utf-8") as f:
            meta = json.load(f)
        recordings = meta.get("recordings", [])
        punch_count = 0
        for rec in recordings:
            label = rec.get("label")
            if label not in IMPACT_FN or "impact_idx" not in rec:
                continue
            start = rec["start_index"]
            count = rec["frame_count"]
            idx = rec["impact_idx"]
            _relabel_block(out, start, count, label, idx, args.hold_frames, args.recovery_frames, args.hold_until_end)
            punch_count += 1
        mode = "임팩트~끝 (hold_until_end)" if args.hold_until_end else f"hold_frames={args.hold_frames}"
        print(f"메타 기반 재라벨: 펀치 {punch_count}개 (가드/none 회차는 그대로 유지), {mode}")

    # 기본: 입력한 pose_data를 그대로 덮어쓴다. 다른 파일로 남기려면 --output 지정
    out_path = args.output if args.output else args.data
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
