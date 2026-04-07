#!/usr/bin/env python3
"""
Aseprite(.aseprite) IDLE 애니 → 프레임별 PNG 추출 → (선택) rembg 배경 제거 →
알파 기준 트림 후 동일 캔버스에 중앙 정렬(프레임 간 흔들림 최소화).

필요:
  - Aseprite 설치 + CLI 사용 가능 (Steam/일반 설치 경로 자동 탐색 또는 환경변수 ASEPRITE)
  - pip install pillow numpy rembg onnxruntime (requirements_sprites.txt)

예시:
  python tools/process_idle_aseprite.py work_images/input/IDLESprite-0001.aseprite
  python tools/process_idle_aseprite.py work_images/input/IDLESprite-0001.aseprite --ignore-layer Background
  python tools/process_idle_aseprite.py work_images/input/IDLESprite-0001.aseprite --no-rembg

Aseprite 없이 이미 PNG만 있으면:
  python tools/process_idle_aseprite.py --from-dir work_images/input/my_frames --prefix burger_idle

배경 레이어 이름을 모르면 Aseprite에서 배경 레이어를 끄거나 삭제 후 저장한 뒤 실행해도 됩니다.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

try:
    from rembg import remove, new_session
except ImportError:
    from rembg import remove
    from rembg.session_factory import new_session  # type: ignore

from work_images_paths import WORK_IMAGES_OUTPUT

_DEFAULT_MODEL = "u2netp"


def _find_aseprite() -> Path | None:
    env = os.environ.get("ASEPRITE", "").strip()
    if env and Path(env).is_file():
        return Path(env)
    candidates = [
        Path(r"C:\Program Files\Aseprite\Aseprite.exe"),
        Path(r"C:\Program Files (x86)\Aseprite\Aseprite.exe"),
        Path(os.path.expandvars(r"%ProgramFiles%\Aseprite\Aseprite.exe")),
        Path(os.path.expandvars(r"%LocalAppData%\Programs\Aseprite\Aseprite.exe")),
        Path(
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Steam\steamapps\common\Aseprite\Aseprite.exe"
            )
        ),
        Path(
            os.path.expandvars(
                r"%ProgramFiles%\Steam\steamapps\common\Aseprite\Aseprite.exe"
            )
        ),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return shutil.which("aseprite") and Path(shutil.which("aseprite")) or None


def _export_aseprite_frames(
    aseprite_exe: Path,
    ase_path: Path,
    out_dir: Path,
    ignore_layer: str,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame-{frame001}.png")
    cmd = [str(aseprite_exe), "-b"]
    if ignore_layer:
        cmd.extend(["--ignore-layer", ignore_layer])
    cmd.extend([str(ase_path.resolve()), "--save-as", pattern])
    subprocess.run(cmd, check=True, cwd=str(out_dir.parent))
    frames = sorted(out_dir.glob("frame-*.png"))
    if not frames:
        raise RuntimeError(
            f"Aseprite가 PNG를 만들지 않았습니다. 명령: {' '.join(cmd)}"
        )
    return frames


def _remove_bg(img: Image.Image, session) -> Image.Image:
    buf = io.BytesIO()
    im = img.convert("RGBA")
    im.convert("RGB").save(buf, format="PNG")
    raw = buf.getvalue()
    out = remove(raw, session=session)
    return Image.open(io.BytesIO(out)).convert("RGBA")


def _trim_alpha(im: Image.Image) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    return im.crop(bbox)


def _uniform_center_frames(
    frames: list[Image.Image],
    canvas_size: int,
) -> list[Image.Image]:
    """트림 후 최대 너비·높이에 맞춰 중앙 배치, 그다음 정사각 canvas_size에 중앙 패딩."""
    trimmed = [_trim_alpha(f) for f in frames]
    widths = [t.size[0] for t in trimmed]
    heights = [t.size[1] for t in trimmed]
    if not widths or not heights:
        raise ValueError("빈 프레임")
    max_w = max(widths)
    max_h = max(heights)
    mid: list[Image.Image] = []
    for t in trimmed:
        cw, ch = t.size
        sheet = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        ox = (max_w - cw) // 2
        oy = (max_h - ch) // 2
        sheet.paste(t, (ox, oy), t)
        mid.append(sheet)
    out: list[Image.Image] = []
    for sheet in mid:
        sw, sh = sheet.size
        if sw > canvas_size or sh > canvas_size:
            sheet = sheet.copy()
            sheet.thumbnail((canvas_size, canvas_size), Image.Resampling.LANCZOS)
            sw, sh = sheet.size
        final = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        fx = (canvas_size - sw) // 2
        fy = (canvas_size - sh) // 2
        final.paste(sheet, (fx, fy), sheet)
        out.append(final)
    return out


def _load_png_dir(d: Path) -> list[Path]:
    exts = {".png", ".webp"}
    files = sorted(
        [p for p in d.iterdir() if p.suffix.lower() in exts and p.is_file()],
        key=lambda p: natural_key(p.stem),
    )
    return files


def natural_key(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aseprite IDLE → 정규화 PNG 시퀀스")
    p.add_argument(
        "aseprite_file",
        type=Path,
        nargs="?",
        default=None,
        help=".aseprite 파일 (없으면 --from-dir 필수)",
    )
    p.add_argument(
        "--from-dir",
        type=Path,
        default=None,
        help="이미 추출된 PNG들이 있는 폴더 (Aseprite CLI 생략)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=WORK_IMAGES_OUTPUT,
        help=f"출력 폴더 (기본 {WORK_IMAGES_OUTPUT})",
    )
    p.add_argument("--prefix", type=str, default="burger_idle", help="burger_idle_01.png …")
    p.add_argument("--digits", type=int, default=2)
    p.add_argument("--size", type=int, default=512, help="최종 정사각 한 변")
    p.add_argument(
        "--no-rembg",
        action="store_true",
        help="rembg 생략(이미 투명 배경이거나 수동 누끼 예정)",
    )
    p.add_argument(
        "--ignore-layer",
        type=str,
        default="",
        help='Aseprite 내보낼 때 숨길 레이어 이름 (예: "Background")',
    )
    p.add_argument(
        "--aseprite",
        type=Path,
        default=None,
        help="Aseprite.exe 경로 (미지정 시 ASEPRITE 환경변수·기본 경로 탐색)",
    )
    p.add_argument(
        "--model",
        type=str,
        default=_DEFAULT_MODEL,
        help="rembg 모델 (기본 u2netp)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir: Path = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    temp_dir: Path | None = None

    try:
        if args.from_dir:
            d = args.from_dir.resolve()
            if not d.is_dir():
                print(f"폴더 없음: {d}", file=sys.stderr)
                return 1
            frame_paths = _load_png_dir(d)
            if not frame_paths:
                print(f"PNG 없음: {d}", file=sys.stderr)
                return 1
        elif args.aseprite_file:
            ase = args.aseprite_file.resolve()
            if not ase.is_file():
                print(f"파일 없음: {ase}", file=sys.stderr)
                return 1
            exe = args.aseprite or _find_aseprite()
            if not exe or not Path(exe).is_file():
                print(
                    "Aseprite.exe 를 찾지 못했습니다. "
                    "ASEPRITE 환경변수에 전체 경로를 지정하거나 --aseprite 로 넘기세요.\n"
                    "또는 Aseprite에서 File → Export → PNG 시퀀스로 저장한 뒤 --from-dir 로 처리하세요.",
                    file=sys.stderr,
                )
                return 1
            temp_dir = Path(tempfile.mkdtemp(prefix="ase_export_"))
            frame_paths = _export_aseprite_frames(
                Path(exe),
                ase,
                temp_dir,
                args.ignore_layer.strip(),
            )
        else:
            print(".aseprite 파일 또는 --from-dir 이 필요합니다.", file=sys.stderr)
            return 1

        images: list[Image.Image] = []
        for fp in frame_paths:
            with Image.open(fp) as im:
                images.append(im.convert("RGBA"))

        session = None
        if not args.no_rembg:
            session = new_session(args.model)
            images = [_remove_bg(im, session) for im in images]

        normalized = _uniform_center_frames(images, args.size)

        # 프레임 수가 줄었을 때 이전 burger_idle_06.png 등이 남지 않도록
        for old in sorted(out_dir.glob(f"{args.prefix}_*.png")):
            old.unlink()

        for i, final in enumerate(normalized):
            name = f"{args.prefix}_{i + 1:0{args.digits}d}.png"
            final.save(out_dir / name, format="PNG")
            print(out_dir / name)

        print(f"완료: {len(normalized)}장 → {out_dir}", file=sys.stderr)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Aseprite 실행 실패: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    finally:
        if temp_dir and temp_dir.is_dir():
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
