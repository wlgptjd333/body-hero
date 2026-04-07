#!/usr/bin/env python3
"""
원본 이미지 폴더를 읽어 rembg(U2-Net)로 배경을 제거하고, 비율 유지 + 투명 패딩으로
정사각형(기본 512x512) PNG로 저장합니다.

개별 파일 유지(스프라이트 시트 미생성). Godot AnimatedSprite2D에 프레임 단위로 넣기 적합합니다.

설치: pip install -r tools/requirements_sprites.txt

기본 입·출력: work_images/input → work_images/output (경로는 tools/work_images_paths.py)

예시:
  python tools/sanitize_sprites.py --prefix burger_idle
  python tools/sanitize_sprites.py --input path/to/raw --output path/to/out --prefix monster_attack

주의: 배경과 피사체 색이 비슷하거나 작은 파편이 많으면 일부가 잘리거나 배경으로
오인될 수 있습니다. 흰 찌꺼기 자동 제거(strip/매팅)는 기본 끔 — 필요 시 --strip-white 등.

rembg만 적용(배경 제거)하고, 남은 흰 점은 에디터에서 수동으로 지우려면 그대로 실행.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

try:
    from rembg import remove, new_session
except ImportError:  # 일부 버전 호환
    from rembg import remove
    from rembg.session_factory import new_session  # type: ignore

from work_images_paths import WORK_IMAGES_INPUT, WORK_IMAGES_OUTPUT

_DEFAULT_INPUT = WORK_IMAGES_INPUT
_DEFAULT_OUTPUT = WORK_IMAGES_OUTPUT

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def natural_sort_key(path: Path) -> list:
    """frame_2.png 가 frame_10.png 보다 앞에 오도록 정렬."""
    s = path.stem
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def remove_background(
    img: Image.Image,
    session,
    alpha_matting: bool,
    fg_thresh: int,
    bg_thresh: int,
    erode_size: int,
) -> Image.Image:
    buf = io.BytesIO()
    # rembg는 RGB 권장; 알파는 내부에서 재계산
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    save_img = img.convert("RGB") if img.mode == "RGBA" else img
    save_img.save(buf, format="PNG")
    raw = buf.getvalue()
    out_bytes = remove(
        raw,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=fg_thresh,
        alpha_matting_background_threshold=bg_thresh,
        alpha_matting_erode_size=erode_size,
    )
    return Image.open(io.BytesIO(out_bytes)).convert("RGBA")


def strip_paper_white_rgba(
    img: Image.Image,
    rgb_min: int,
    gray_max_delta: int,
) -> Image.Image:
    """
    rembg 후에도 남는 흰/미색 종이 배경(겨드랑이·틈새 등)을 투명 처리.
    R,G,B가 모두 높고 색차가 작은 '무채색에 가까운 밝은 픽셀'만 제거.
    """
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    r = arr[..., 0].astype(np.int16)
    g = arr[..., 1].astype(np.int16)
    b = arr[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = mx - mn
    mask = (r >= rgb_min) & (g >= rgb_min) & (b >= rgb_min) & (delta <= gray_max_delta)
    arr = arr.copy()
    arr[..., 3] = np.where(mask, 0, arr[..., 3])
    return Image.fromarray(arr, mode="RGBA")


def strip_matte_halo_rgba(
    img: Image.Image,
    rgb_min: int,
    gray_max_delta: int,
    alpha_max: int,
) -> Image.Image:
    """
    알파가 완전하지 않은(반투명) 밝은 무채색 픽셀 — 가장자리·안쪽 얇은 흰 테두리에 흔함.
    """
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    r = arr[..., 0].astype(np.int16)
    g = arr[..., 1].astype(np.int16)
    b = arr[..., 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = mx - mn
    a = arr[..., 3].astype(np.int16)
    mask = (
        (a > 0)
        & (a < 255)
        & (a <= alpha_max)
        & (r >= rgb_min)
        & (g >= rgb_min)
        & (b >= rgb_min)
        & (delta <= gray_max_delta)
    )
    arr = arr.copy()
    arr[..., 3] = np.where(mask, 0, arr[..., 3])
    return Image.fromarray(arr, mode="RGBA")


def erode_alpha_rgba(img: Image.Image, iterations: int) -> Image.Image:
    """
    알파 마스크를 3×3 최소값 침식. 검은 외곽선 등 어두운 가장자리도 함께 깎일 수 있으므로 기본은 끔.
    """
    if iterations <= 0:
        return img
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8).copy()
    a = arr[..., 3].astype(np.uint16)
    h, w = a.shape
    for _ in range(iterations):
        p = np.pad(a, 1, mode="constant", constant_values=0)
        stacks = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                stacks.append(p[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w])
        a = np.minimum.reduce(stacks)
    arr[..., 3] = np.clip(a, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def fit_center_canvas(src: Image.Image, canvas_size: int) -> Image.Image:
    target = (canvas_size, canvas_size)
    img = src.copy()
    img.thumbnail(target, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", target, (0, 0, 0, 0))
    x = (canvas_size - img.size[0]) // 2
    y = (canvas_size - img.size[1]) // 2
    out.paste(img, (x, y), img)
    return out


def collect_images(input_dir: Path) -> list[Path]:
    files = [
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    ]
    files.sort(key=natural_sort_key)
    return files


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="rembg 배경 제거 + 정사각형 PNG 정규화")
    p.add_argument(
        "--input",
        type=Path,
        default=_DEFAULT_INPUT,
        help=f"원본 이미지 폴더 (기본: {_DEFAULT_INPUT})",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"출력 폴더 (기본: {_DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--size",
        type=int,
        default=512,
        help="출력 한 변 픽셀 (정사각형)",
    )
    p.add_argument(
        "--prefix",
        type=str,
        default="",
        help="지정 시 {prefix}_01.png 형식으로 연번 저장. 미지정 시 원본 파일명(확장자만 .png)",
    )
    p.add_argument(
        "--digits",
        type=int,
        default=2,
        help="--prefix 사용 시 번호 자릿수 (기본 2 → 01, 02, …)",
    )
    p.add_argument(
        "--model",
        type=str,
        default="u2net",
        help='rembg 모델 이름 (기본 u2net, 파편 보존에 유리. 가벼운 모델: "u2netp")',
    )
    p.add_argument(
        "--no-alpha-matting",
        action="store_true",
        help="알파 매팅 끔 (빠르지만 경계/유사색 배경에서 품질 저하 가능)",
    )
    p.add_argument(
        "--fg-thresh",
        type=int,
        default=240,
        help="알파 매팅 foreground 임계값 (낮추면 전경으로 더 많이 잡을 수 있음)",
    )
    p.add_argument(
        "--bg-thresh",
        type=int,
        default=10,
        help="알파 매팅 background 임계값",
    )
    p.add_argument(
        "--erode",
        type=int,
        default=10,
        help="알파 매팅 erode 크기",
    )
    p.add_argument(
        "--strip-white",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="rembg 후 밝은 무채색(흰 찌꺼기) 픽셀을 투명 처리 (기본 끔, 수동 보정 시 그대로)",
    )
    p.add_argument(
        "--strip-rgb-min",
        type=int,
        default=234,
        help="strip: R,G,B가 모두 이 값 이상이면 후보 (낮출수록 더 많이 지움)",
    )
    p.add_argument(
        "--strip-gray-delta",
        type=int,
        default=32,
        help="strip: max(R,G,B)-min(R,G,B)가 이 값 이하면 무채색으로 간주",
    )
    p.add_argument(
        "--matte-halo",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="반투명 밝은 테두리(매팅 잔광) 제거 (기본 끔)",
    )
    p.add_argument(
        "--matte-rgb-min",
        type=int,
        default=220,
        help="matte strip: R,G,B 최솟값 후보. 너무 낮으면 검은 테두리 인접 반투명까지 지울 수 있음",
    )
    p.add_argument(
        "--matte-gray-delta",
        type=int,
        default=38,
        help="matte strip: 무채색 판정 색차 상한",
    )
    p.add_argument(
        "--matte-alpha-max",
        type=int,
        default=252,
        help="matte strip: 알파가 이 값 이하인 픽셀만(완전 불투명 제외)",
    )
    p.add_argument(
        "--alpha-erode",
        type=int,
        default=0,
        help="알파 침식 반복(기본 0). 1+ 는 가장자리 1px·검은 외곽선까지 깎일 수 있음. 흰 찌꺼기만 줄이려면 strip 옵션 조절 권장",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_dir: Path = args.input.resolve()
    output_dir: Path = args.output.resolve()
    size: int = args.size

    if size < 1:
        print("--size 는 1 이상이어야 합니다.", file=sys.stderr)
        return 1

    if not input_dir.is_dir():
        print(f"입력 폴더가 없습니다: {input_dir}", file=sys.stderr)
        print("폴더를 만들고 이미지를 넣은 뒤 다시 실행하세요.", file=sys.stderr)
        return 1

    files = collect_images(input_dir)
    if not files:
        print(f"'{input_dir}' 에 지원 이미지가 없습니다. ({', '.join(sorted(_IMAGE_EXTS))})", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    use_matting = not args.no_alpha_matting
    session = new_session(args.model)

    for i, src_path in enumerate(tqdm(files, desc="sanitize")):
        if args.prefix:
            num = i + 1
            out_name = f"{args.prefix}_{num:0{args.digits}d}.png"
        else:
            out_name = f"{src_path.stem}.png"
        out_path = output_dir / out_name

        try:
            with Image.open(src_path) as im:
                im = im.convert("RGBA")
                cut = remove_background(
                    im,
                    session=session,
                    alpha_matting=use_matting,
                    fg_thresh=args.fg_thresh,
                    bg_thresh=args.bg_thresh,
                    erode_size=args.erode,
                )
                if args.strip_white:
                    cut = strip_paper_white_rgba(
                        cut,
                        rgb_min=args.strip_rgb_min,
                        gray_max_delta=args.strip_gray_delta,
                    )
                if args.matte_halo:
                    cut = strip_matte_halo_rgba(
                        cut,
                        rgb_min=args.matte_rgb_min,
                        gray_max_delta=args.matte_gray_delta,
                        alpha_max=args.matte_alpha_max,
                    )
                cut = erode_alpha_rgba(cut, args.alpha_erode)
                final_img = fit_center_canvas(cut, size)
                final_img.save(out_path, format="PNG")
        except Exception as e:
            print(f"[실패] {src_path}: {e}", file=sys.stderr)

    print(f"완료: {len(files)}장 → {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
