"""
upper_l / upper_r 녹화 1회를 프레임별로 분석해서,
- 손목 y (wr_y)
- 어깨 y (sh_y)
- wr_y - sh_y (어깨 기준 상대 높이)
- 후보 여부 (wr_y <= sh_y + margin)
- impact_idx (임팩트 프레임)

를 표로 출력합니다.

사용 예 (tools 폴더에서):
  venv_ml\Scripts\activate
  python analyze_uppercut.py --label upper_r --nth 1
"""

import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")

# collect_pose_data.py 의 IDX와 동일한 인덱스 (33*3 flat: 각 랜드마크 x,y,z)
# 11=왼쪽어깨, 12=오른쪽어깨, 15=왼쪽손목, 16=오른쪽손목
IDX = {
    "l_sh_y": 34,
    "r_sh_y": 37,
    "l_wr_y": 46,
    "r_wr_y": 49,
}

# collect_pose_data.py 의 UPPER_WRIST_ABOVE_SHOULDER_MARGIN 와 동일하게 맞춰야 의미가 같다.
UPPER_WRIST_ABOVE_SHOULDER_MARGIN = 0.10


def main() -> None:
    parser = argparse.ArgumentParser(description="upper_l / upper_r 녹화 1회에 대한 프레임별 y값/후보/임팩트 분석")
    parser.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json 경로")
    parser.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json 경로")
    parser.add_argument("--label", required=True, help="upper_l 또는 upper_r (대상 라벨)")
    parser.add_argument("--nth", type=int, default=1, help="해당 라벨의 N번째 녹화 (1부터 시작, 기본 1)")
    args = parser.parse_args()

    if args.label not in ("upper_l", "upper_r"):
        print("지금 스크립트는 upper_l / upper_r 만 지원합니다. --label upper_l 또는 upper_r 로 호출하세요.")
        return

    if not os.path.isfile(args.data):
        print(f"파일 없음: {args.data}")
        return
    if not os.path.isfile(args.meta):
        print(f"파일 없음: {args.meta}")
        return

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("pose_data.json 형식이 리스트가 아닙니다.")
        return

    with open(args.meta, "r", encoding="utf-8") as f:
        meta_obj = json.load(f)
    recs = meta_obj.get("recordings", [])
    if not isinstance(recs, list):
        print("pose_recordings_meta.json 형식이 잘못되었습니다.")
        return

    # upper_l / upper_r 만 필터링
    recs_label = [r for r in recs if r.get("label") == args.label]
    if not recs_label:
        print(f"라벨 '{args.label}' 로 된 녹화가 없습니다.")
        return

    nth = max(1, args.nth)
    if nth > len(recs_label):
        print(f"라벨 '{args.label}' 녹화는 {len(recs_label)}회뿐입니다. --nth {nth} 불가.")
        return

    rec = recs_label[nth - 1]
    idx_in_all = recs.index(rec)
    start = rec.get("start_index", 0)
    count = rec.get("frame_count", 60)
    impact_idx = rec.get("impact_idx", None)

    frames = data[start : start + count]
    if not frames:
        print("선택한 녹화에 프레임이 없습니다.")
        return

    print(f"분석 대상: label={args.label}, recordings index={idx_in_all}, start_index={start}, frame_count={len(frames)}, impact_idx={impact_idx}")
    print(f"  UPPER_WRIST_ABOVE_SHOULDER_MARGIN={UPPER_WRIST_ABOVE_SHOULDER_MARGIN}")
    print()
    print("i  per_label   wr_y       sh_y       diff(wr_y-sh_y)   candidate(wr_y<=sh_y+margin)   IMPACT")
    print("-" * 90)

    wr_key = "r_wr_y" if args.label == "upper_r" else "l_wr_y"
    sh_key = "r_sh_y" if args.label == "upper_r" else "l_sh_y"
    wr_idx = IDX[wr_key]
    sh_idx = IDX[sh_key]

    for i, item in enumerate(frames):
        flat = item.get("landmarks")
        lab = item.get("label")
        if not flat or len(flat) <= max(wr_idx, sh_idx):
            print(f"{i:02d}  {lab:9s}  (랜드마크 길이 부족)")
            continue
        wr_y = float(flat[wr_idx])
        sh_y = float(flat[sh_idx])
        diff = wr_y - sh_y
        cand = wr_y <= sh_y + UPPER_WRIST_ABOVE_SHOULDER_MARGIN
        impact_mark = "*" if (impact_idx is not None and i == int(impact_idx)) else ""
        print(f"{i:02d}  {lab:9s}  {wr_y:+8.4f}  {sh_y:+8.4f}  {diff:+17.4f}        {str(cand):5s} {impact_mark}")


if __name__ == "__main__":
    main()

