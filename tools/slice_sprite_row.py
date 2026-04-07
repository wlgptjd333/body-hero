#!/usr/bin/env python3
"""
스프라이트 시트에서 '한 줄' 영역만 잘라 동일 폭으로 N등분해 PNG로 저장합니다.
(MONSTER BURGER처럼 상단 큰 그림 + IDLE 5프레임 줄 + 하단 파츠가 있는 시트는
반드시 --region으로 IDLE 줄만 지정하세요. 전체 이미지를 5등분하면 안 됩니다.)

필요: pip install pillow (requirements_sprites.txt에 포함)

예시:
  python tools/slice_sprite_row.py work_images/reference/my_sheet.png ^
    --region 120,520,2480,380 --prefix burger_idle --frames 5

--region L,T,W,H 는 IDLE 행을 딱 감싸는 사각형(픽셀). 이미지 뷰어·Aseprite에서 좌표 확인.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

from work_images_paths import WORK_IMAGES_OUTPUT


def _parse_region(s: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in re.split(r"[,\s]+", s.strip()) if p.strip()]
    if len(parts) != 4:
        raise ValueError("--region 은 left,top,width,height 네 숫자여야 합니다.")
    return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))


def main() -> int:
    p = argparse.ArgumentParser(
        description="스프라이트 시트의 한 행을 N등분해 PNG로 저장"
    )
    p.add_argument(
        "input",
        type=Path,
        help="스프라이트 시트 PNG/JPG 경로",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=WORK_IMAGES_OUTPUT,
        help=f"출력 폴더 (기본: {WORK_IMAGES_OUTPUT})",
    )
    p.add_argument(
        "--prefix",
        type=str,
        default="idle",
        help="파일명 접두어 (예: burger_idle → burger_idle_01.png …)",
    )
    p.add_argument(
        "--frames",
        type=int,
        default=5,
        help="가로로 나눌 프레임 수 (기본 5)",
    )
    p.add_argument(
        "--region",
        type=str,
        default="",
        help="IDLE 줄만 포함하는 사각형: left,top,width,height (픽셀). 상·하단이 있는 시트는 필수.",
    )
    p.add_argument(
        "--full-width",
        action="store_true",
        help="region 없이 이미지 전체를 가로로만 N등분 (한 줄짜리 시트 전용)",
    )
    p.add_argument(
        "--trim",
        type=int,
        default=0,
        help="각 셀에서 사방으로 잘라낼 픽셀(검은 테두리 제거용, 선택)",
    )
    p.add_argument(
        "--digits",
        type=int,
        default=2,
        help="번호 자릿수 (기본 2 → 01, 02 …)",
    )
    args = p.parse_args()

    inp: Path = args.input.resolve()
    if not inp.is_file():
        print(f"파일 없음: {inp}", file=sys.stderr)
        return 1

    if args.frames < 1:
        print("--frames 는 1 이상", file=sys.stderr)
        return 1

    with Image.open(inp) as im:
        im = im.convert("RGBA")
        w, h = im.size

        if args.region:
            left, top, rw, rh = _parse_region(args.region)
            if left < 0 or top < 0 or rw < 1 or rh < 1:
                print("--region 값이 잘못되었습니다.", file=sys.stderr)
                return 1
            if left + rw > w or top + rh > h:
                print(
                    f"region이 이미지 밖입니다. 이미지 크기: {w}x{h}",
                    file=sys.stderr,
                )
                return 1
            row = im.crop((left, top, left + rw, top + rh))
        elif args.full_width:
            row = im
        else:
            print(
                "상·하단이 있는 시트는 --region L,T,W,H 로 IDLE 줄만 지정하세요.\n"
                "한 줄짜리 이미지 전체만 자를 때는 --full-width 를 붙이세요.",
                file=sys.stderr,
            )
            return 1

        rw2, rh2 = row.size
        cell_w = rw2 // args.frames
        if cell_w < 1:
            print("프레임 폭이 0입니다. region 폭을 늘리거나 --frames를 줄이세요.", file=sys.stderr)
            return 1

        out_dir: Path = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        trim = max(0, args.trim)

        for i in range(args.frames):
            x0 = i * cell_w
            x1 = x0 + cell_w if i < args.frames - 1 else rw2
            cell = row.crop((x0, 0, x1, rh2))
            if trim > 0 and cell.size[0] > 2 * trim and cell.size[1] > 2 * trim:
                cell = cell.crop(
                    (
                        trim,
                        trim,
                        cell.size[0] - trim,
                        cell.size[1] - trim,
                    )
                )
            num = i + 1
            name = f"{args.prefix}_{num:0{args.digits}d}.png"
            out_path = out_dir / name
            cell.save(out_path, format="PNG")
            print(out_path)

    print(f"완료: {args.frames}장 → {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
