"""
저장된 pose_data.json / pose_recordings_meta.json에서
특정 녹화 1회를 뼈대(스켈레톤) 애니메이션으로 리플레이합니다.

사용 예 (tools 폴더에서):
  venv_ml\Scripts\activate
  python replay_pose.py --label upper_l --nth 1

옵션:
  --label LABEL   : 보고 싶은 라벨 (예: punch_l, punch_r, upper_l, upper_r ...)
  --nth N        : 해당 라벨의 N번째 녹화 (1부터 시작, 기본 1)
  --fps F        : 재생 FPS (기본 30, 숫자가 클수록 빨라짐)
"""

import os
import json
import argparse
from typing import List, Tuple

import cv2
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "pose_data.json")
DEFAULT_META = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")

# collect_pose_data.py와 동일한 포즈 연결 (MediaPipe Pose 33점)
POSE_CONNECTIONS: Tuple[Tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19), (16, 18), (16, 20), (16, 22), (18, 20),
    (23, 24), (11, 23), (12, 24), (23, 25), (24, 26), (25, 27), (26, 28),
    (27, 29), (28, 30), (29, 31), (30, 32),
)


def flat_to_points(flat: List[float]) -> np.ndarray:
    """
    99차원 flat (33 * 3)을 (33, 3) array로 변환.
    x,y,z는 어깨 기준 정규화된 좌표.
    """
    arr = np.asarray(flat, dtype=np.float32)
    if arr.shape[0] != 99:
        raise ValueError(f"landmarks 길이 오류: {arr.shape[0]} (기대값 99)")
    return arr.reshape(33, 3)


def norm_points_to_image(points: np.ndarray, width: int = 640, height: int = 480, scale: float = 120.0) -> np.ndarray:
    """
    어깨 기준 정규화 좌표를 단순히 화면 중앙 기준으로 스케일링해서 2D 픽셀 좌표로 변환.
    y축은 아래로 증가하도록 그대로 사용.
    """
    cx = width / 2.0
    cy = height / 2.0
    xs = cx + points[:, 0] * scale
    ys = cy + points[:, 1] * scale
    pts = np.stack([xs, ys], axis=1)
    return pts.astype(np.int32)


def replay_recording(
    data: list,
    rec: dict,
    window_name: str = "Pose replay",
    fps: int = 30,
) -> None:
    """
    단일 녹화(rec)를 뼈대 애니메이션으로 재생.
    - data: pose_data.json 리스트
    - rec: recordings_meta의 한 항목 (label, start_index, frame_count, impact_idx 등)
    """
    start = rec.get("start_index", 0)
    count = rec.get("frame_count", 60)
    label = rec.get("label", "?")
    impact_idx = rec.get("impact_idx", None)
    guard_start_idx = rec.get("guard_start_idx", None)

    frames = data[start : start + count]
    if not frames:
        print("이 녹화에는 프레임이 없습니다.")
        return

    delay = max(1, int(1000 / max(1, fps)))  # ms
    width, height = 640, 480

    print(f"리플레이: label={label}, start_index={start}, frame_count={len(frames)}, impact_idx={impact_idx}, guard_start_idx={guard_start_idx}")
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    paused = False
    idx = 0
    while True:
        frame_info = frames[idx]
        flat = frame_info.get("landmarks")
        lab = frame_info.get("label")
        pts3 = flat_to_points(flat)
        pts2 = norm_points_to_image(pts3, width=width, height=height, scale=120.0)

        img = np.zeros((height, width, 3), dtype=np.uint8)

        # 뼈대 라인
        for i, j in POSE_CONNECTIONS:
            if i < len(pts2) and j < len(pts2):
                a = tuple(pts2[i])
                b = tuple(pts2[j])
                cv2.line(img, a, b, (0, 180, 255), 2)

        # 포인트
        for k, (x, y) in enumerate(pts2):
            cv2.circle(img, (int(x), int(y)), 4, (0, 255, 0), -1)

        # 임팩트/가드 시작 프레임이면 빨간 원으로 강조
        if impact_idx is not None and idx == impact_idx:
            color = (0, 0, 255)
            for (x, y) in pts2:
                cv2.circle(img, (int(x), int(y)), 6, color, 1)
        if guard_start_idx is not None and idx == guard_start_idx:
            color = (255, 0, 0)
            for (x, y) in pts2:
                cv2.circle(img, (int(x), int(y)), 6, color, 1)

        # 텍스트 정보
        cv2.putText(img, f"Label: {label} (frame {idx+1}/{len(frames)})", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(img, f"Per-frame label: {lab}", (10, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)
        if impact_idx is not None:
            cv2.putText(img, f"Impact idx: {impact_idx+1}", (10, 72),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
        if guard_start_idx is not None:
            cv2.putText(img, f"Guard start idx: {guard_start_idx+1}", (10, 96),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

        cv2.imshow(window_name, img)
        key = cv2.waitKey(0 if paused else delay) & 0xFF

        if key in (ord("q"), ord("Q"), 27):  # q 또는 ESC
            break
        if key in (ord(" "), ord("p")):
            paused = not paused
            continue
        if key in (ord("d"), ord("D"), 83):  # 오른쪽 화살표
            idx = (idx + 1) % len(frames)
            continue
        if key in (ord("a"), ord("A"), 81):  # 왼쪽 화살표
            idx = (idx - 1) % len(frames)
            continue

        if not paused:
            idx = (idx + 1) % len(frames)

    cv2.destroyWindow(window_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="pose_data.json에서 특정 녹화 1회를 뼈대 애니메이션으로 리플레이")
    parser.add_argument("--data", default=DEFAULT_DATA, help="pose_data.json 경로")
    parser.add_argument("--meta", default=DEFAULT_META, help="pose_recordings_meta.json 경로")
    parser.add_argument("--label", required=True, help="보고 싶은 라벨 (예: punch_l, punch_r, upper_l, upper_r, guard, none)")
    parser.add_argument("--nth", type=int, default=1, help="해당 라벨의 N번째 녹화 (1부터 시작, 기본 1)")
    parser.add_argument("--fps", type=int, default=30, help="재생 FPS (기본 30)")
    args = parser.parse_args()

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

    # 라벨로 필터링
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
    print(f"전체 recordings 중 index={idx_in_all}, label='{args.label}' 의 {nth}번째 녹화를 재생합니다.")

    replay_recording(data, rec, window_name=f"Replay {args.label} #{nth}", fps=args.fps)


if __name__ == "__main__":
    main()

