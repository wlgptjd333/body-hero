"""
저장된 pose_data.json / pose_recordings_meta.json 에서 녹화 구간을 삭제합니다.

사용 예:
  python delete_pose_recordings.py --last 1           # 마지막 1회 삭제
  python delete_pose_recordings.py --last 5          # 마지막 5회 삭제
  python delete_pose_recordings.py --label upper_l   # upper_l 라벨인 녹화만 전부 삭제
  python delete_pose_recordings.py --label upper_l --dry-run  # 저장 없이 확인만
"""
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
RECORD_FRAMES = 60  # 1회 녹화 기본 프레임 수 (메타에 없을 때)


def delete_by_label(data, recordings_meta, label, dry_run):
    """지정한 라벨만 제거한 새 data, new_meta 반환. (메타 start_index 재계산)"""
    to_remove = [r for r in recordings_meta if r.get("label") == label]
    to_keep = [r for r in recordings_meta if r.get("label") != label]
    if not to_remove:
        print(f"'{label}' 라벨인 녹화가 없습니다.")
        return data, recordings_meta, 0
    new_data = []
    new_meta = []
    for rec in to_keep:
        start = rec["start_index"]
        count = rec.get("frame_count", RECORD_FRAMES)
        chunk = data[start : start + count]
        new_meta.append({
            **rec,
            "start_index": len(new_data),
            "frame_count": count,
        })
        new_data.extend(chunk)
    removed_frames = len(data) - len(new_data)
    print(f"삭제 예정: 라벨 '{label}' {len(to_remove)}회 ({removed_frames}프레임)")
    print(f"  → 데이터: {len(data)} → {len(new_data)} 프레임")
    if dry_run:
        print("  [dry-run] 저장하지 않음.")
    return new_data, new_meta, removed_frames


def main():
    parser = argparse.ArgumentParser(description="pose_data.json에서 녹화 구간 삭제")
    parser.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json 경로")
    parser.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json 경로")
    parser.add_argument("--last", type=int, metavar="N", help="마지막 N회 녹화 삭제")
    parser.add_argument("--label", type=str, metavar="LABEL", help="이 라벨인 녹화만 전부 삭제 (예: upper_l)")
    parser.add_argument("--dry-run", action="store_true", help="실제 저장 없이 삭제할 구간만 출력")
    args = parser.parse_args()

    if not args.last and not args.label:
        print("--last N 또는 --label LABEL 중 하나를 지정하세요.")
        print("  예: --last 1   또는   --label upper_l")
        return
    if args.last and args.label:
        print("--last 와 --label 은 동시에 쓸 수 없습니다. 하나만 지정하세요.")
        return

    if not os.path.isfile(args.data):
        print(f"파일 없음: {args.data}")
        return

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("pose_data.json 형식이 리스트가 아닙니다.")
        return

    recordings_meta = []
    meta_path = args.meta
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            recordings_meta = obj.get("recordings", [])
            if not isinstance(recordings_meta, list):
                recordings_meta = []
        except Exception as e:
            print(f"메타 로드 실패: {e}")

    if args.label:
        new_data, new_meta, removed_count = delete_by_label(data, recordings_meta, args.label, args.dry_run)
        if args.dry_run or removed_count == 0:
            return
        data, recordings_meta = new_data, new_meta
    else:
        if args.last < 1:
            print("--last N (N >= 1) 을 지정하세요.")
            return
        if len(recordings_meta) < args.last:
            print(f"메타에 녹화가 {len(recordings_meta)}회뿐입니다. --last {args.last} 불가.")
            return
        to_remove = recordings_meta[-args.last:]
        new_meta = recordings_meta[:-args.last]
        cut_at = to_remove[0]["start_index"]
        removed_frames = sum(rec.get("frame_count", RECORD_FRAMES) for rec in to_remove)
        new_data = data[:cut_at]
        print(f"삭제 예정: 마지막 {args.last}회 녹화")
        for i, rec in enumerate(to_remove):
            lb = rec.get("label", "?")
            fc = rec.get("frame_count", RECORD_FRAMES)
            start = rec.get("start_index", 0)
            print(f"  {i+1}. {lb} (start={start}, {fc}프레임)")
        print(f"  → 데이터: {len(data)} → {len(new_data)} 프레임 (제거 {removed_frames}프레임)")
        if args.dry_run:
            print("  [dry-run] 저장하지 않음.")
            return
        data, recordings_meta = new_data, new_meta

    tmp_data = args.data + ".tmp"
    tmp_meta = meta_path + ".tmp"
    try:
        with open(tmp_data, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_data, args.data)
        print(f"저장: {args.data}")

        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump({"recordings": recordings_meta}, f, ensure_ascii=False, indent=2)
        os.replace(tmp_meta, meta_path)
        print(f"저장: {meta_path} ({len(recordings_meta)}개 녹화)")
    except Exception as e:
        print(f"저장 실패: {e}")
        for p in (tmp_data, tmp_meta):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


if __name__ == "__main__":
    main()
