"""work_images/ 작업 트리 경로. 다른 스크립트에서 복사·이동 로직에 재사용."""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

WORK_IMAGES_ROOT: Path = PROJECT_ROOT / "work_images"
WORK_IMAGES_INPUT: Path = WORK_IMAGES_ROOT / "input"
WORK_IMAGES_OUTPUT: Path = WORK_IMAGES_ROOT / "output"
WORK_IMAGES_REFERENCE: Path = WORK_IMAGES_ROOT / "reference"
