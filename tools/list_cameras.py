"""
OpenCV로 열리는 카메라 인덱스만 나열 (Godot 설정 UI에서 OS.execute로 호출).

cv_capture.open_cv_video_capture 와 동일하게 Windows에서는 DirectShow(auto) 우선으로 열림 여부를 검사합니다.

사용:
  python list_cameras.py [출력파일경로] [--backend auto|default|dshow|msmf]
"""
from __future__ import annotations

import argparse
import sys

from cv_capture import open_cv_video_capture


def main() -> int:
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("opencv-python 필요: pip install opencv-python", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="열리는 카메라 인덱스 나열")
    parser.add_argument("out_path", nargs="?", default=None, help="쓰면 이 파일에 인덱스 한 줄씩")
    parser.add_argument(
        "--backend",
        choices=["auto", "default", "dshow", "msmf"],
        default="auto",
        help="Windows 권장: auto (DirectShow 우선)",
    )
    parser.add_argument(
        "--with-names",
        action="store_true",
        help="카메라 이름도 함께 출력 (인덱스|이름 형태)",
    )
    args = parser.parse_args()
    max_index = 10
    opened: list[Tuple[int, str]] = []
    for i in range(max_index):
        cap, _tag = open_cv_video_capture(i, args.backend)
        try:
            if cap.isOpened():
                if args.with_names:
                    name = cap.getBackendName() if hasattr(cap, "getBackendName") else ""
                    if not name:
                        name = _tag
                    opened.append((i, name))
                else:
                    opened.append((i, ""))
        finally:
            cap.release()
    lines: list[str] = []
    for idx, name in opened:
        if args.with_names and name:
            lines.append("%d|%s" % (idx, name))
        else:
            lines.append("%d" % idx)
    output = "\n".join(lines) + ("\n" if lines else "")
    if args.out_path:
        try:
            with open(args.out_path, "w", encoding="utf-8") as f:
                f.write(output)
        except OSError as e:
            print(str(e), file=sys.stderr)
            return 3
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
