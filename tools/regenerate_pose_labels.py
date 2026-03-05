"""
pose_data.json을 drop + 유지 N으로 재라벨링.

방법 1) pose_recordings_meta.json 있음: --hold-frames N 만 지정.
방법 2) 메타 없음, 녹화 순서·횟수만 알 때: --structure "jab_l:100,none:70,jab_r:5"
        → 각 펀치 블록(60프레임)에서 임팩트를 계산해 drop+유지 N 적용.

사용: python regenerate_pose_labels.py --hold-frames 5 --output pose_data.json
     python regenerate_pose_labels.py --structure "jab_l:100,none:70,jab_r:5" --hold-frames 5 --output pose_data.json
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


def _impact_frame_jab_l(frames_flat):
    ext = [f[IDX["l_wr_x"]] - f[IDX["l_sh_x"]] for f in frames_flat]
    return max(range(len(ext)), key=lambda i: ext[i]) if ext else 0


def _impact_frame_jab_r(frames_flat):
    ext = [f[IDX["r_wr_x"]] - f[IDX["r_sh_x"]] for f in frames_flat]
    return max(range(len(ext)), key=lambda i: ext[i]) if ext else 0


def _impact_frame_upper_l(frames_flat):
    ys = [f[IDX["l_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i]) if ys else 0


def _impact_frame_upper_r(frames_flat):
    ys = [f[IDX["r_wr_y"]] for f in frames_flat]
    return min(range(len(ys)), key=lambda i: ys[i]) if ys else 0


def _impact_frame_hook_l(frames_flat):
    """collect_pose_data와 동일: 왼손 훅 임팩트 = 어깨 높이 근처에서 몸 안쪽(오른쪽)으로 가장 들어온 프레임."""
    if not frames_flat:
        return 0
    candidates = [i for i in range(len(frames_flat))
                  if abs(frames_flat[i][IDX["l_wr_y"]] - frames_flat[i][IDX["l_sh_y"]]) < 0.35]
    if not candidates:
        return max(range(len(frames_flat)), key=lambda i: frames_flat[i][IDX["l_wr_x"]])
    return max(candidates, key=lambda i: frames_flat[i][IDX["l_wr_x"]])


def _impact_frame_hook_r(frames_flat):
    """collect_pose_data와 동일: 오른손 훅 임팩트 = 어깨 높이 근처에서 몸 안쪽(왼쪽)으로 가장 들어온 프레임."""
    if not frames_flat:
        return 0
    candidates = [i for i in range(len(frames_flat))
                  if abs(frames_flat[i][IDX["r_wr_y"]] - frames_flat[i][IDX["r_sh_y"]]) < 0.35]
    if not candidates:
        return min(range(len(frames_flat)), key=lambda i: frames_flat[i][IDX["r_wr_x"]])
    return min(candidates, key=lambda i: frames_flat[i][IDX["r_wr_x"]])


IMPACT_FN = {
    "jab_l": _impact_frame_jab_l,
    "jab_r": _impact_frame_jab_r,
    "upper_l": _impact_frame_upper_l,
    "upper_r": _impact_frame_upper_r,
    "hook_l": _impact_frame_hook_l,
    "hook_r": _impact_frame_hook_r,
}


def _parse_structure(s):
    """'jab_l:100,none:70,jab_r:5' → [(jab_l, 100), (none, 70), (jab_r, 5)]"""
    out = []
    for part in s.strip().split(","):
        part = part.strip()
        if ":" not in part:
            continue
        label, count = part.split(":", 1)
        label, count = label.strip(), int(count.strip())
        out.append((label, count))
    return out


def _relabel_block(out, start, count, label, impact_idx, hold_frames, recovery_frames=None):
    rdf = recovery_frames if recovery_frames is not None else RECOVERY_DROP_FRAMES
    action_low = max(0, impact_idx - IMPACT_WINDOW_HALF)
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
    parser.add_argument("--hold-frames", type=int, default=5, help="Frames after impact to label as action")
    parser.add_argument("--recovery-frames", type=int, default=4, help="Frames after action as recovery drop (default 4)")
    parser.add_argument("--output", default=None, help="Output path (default: pose_data_holdN.json)")
    parser.add_argument("--structure", type=str, default=None,
                        help='Recording order and counts, e.g. "jab_l:100,none:70,jab_r:5" (each recording = 60 frames)')
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
            print("--structure 형식 예: jab_l:100,none:70,jab_r:5")
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
                    _relabel_block(out, start, FRAMES_PER_RECORDING, label, impact_idx, args.hold_frames, args.recovery_frames)
                    rec_count += 1
        print(f"구조 기반 재라벨: {rec_count}개 펀치 블록, drop + 유지 {args.hold_frames}프레임")
    else:
        if not os.path.isfile(args.meta):
            print(f"메타 없음: {args.meta}")
            print('  메타 없이 재라벨하려면 --structure "jab_l:100,none:70,jab_r:5" 처럼 녹화 순서·횟수를 지정하세요.')
            raise SystemExit(1)
        with open(args.meta, "r", encoding="utf-8") as f:
            meta = json.load(f)
        recordings = meta.get("recordings", [])
        for rec in recordings:
            start = rec["start_index"]
            count = rec["frame_count"]
            idx = rec["impact_idx"]
            label = rec["label"]
            _relabel_block(out, start, count, label, idx, args.hold_frames, args.recovery_frames)
        print(f"메타 기반 재라벨: {len(recordings)}개 녹화, hold_frames={args.hold_frames}")

    out_path = args.output or os.path.join(SCRIPT_DIR, f"pose_data_hold{args.hold_frames}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
