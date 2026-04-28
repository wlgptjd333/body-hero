"""
L/R(펀치·어퍼) 혼동 완화용 일괄 학습 헬퍼.

1) report_pose_lr_balance.py  — 데이터 L:R 비율 확인
2) train_pose_classifier_seq.py — 시퀀스 모델 (기본: 좌우반전 + L/R 오버샘플)
3) (선택) train_pose_classifier.py — 가드 단일 프레임 폴백

실행: cd tools → python train_pose_lr_focused.py  (데이터 녹화: collect_pose_data.py --camera-index N --camera-backend dshow)
옵션은 각 스크립트에 동일하게 넘기려면 이 파일을 수정하거나 아래 subprocess 인자를 조정.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run_step(desc: str, argv: list) -> None:
    print("\n" + "=" * 60)
    print(desc)
    print(" ".join(argv))
    print("=" * 60 + "\n")
    r = subprocess.run(argv, cwd=SCRIPT_DIR)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="L/R 중심 포즈 학습 일괄 실행")
    parser.add_argument("--skip-report", action="store_true", help="1단계 리포트 생략")
    parser.add_argument("--skip-single", action="store_true", help="가드 단일 모델 학습 생략")
    parser.add_argument("--seq-len", type=int, default=8)
    args, _rest = parser.parse_known_args()

    if not os.path.isfile(os.path.join(SCRIPT_DIR, "pose_data.json")):
        print("pose_data.json 이 없습니다. 먼저 python collect_pose_data.py 로 녹화하세요.")
        raise SystemExit(1)

    if not args.skip_report:
        run_step(
            "[1/3] L:R 데이터 균형 리포트",
            [PY, os.path.join(SCRIPT_DIR, "report_pose_lr_balance.py"), "--seq-len", str(args.seq_len)],
        )

    run_step(
        "[2/3] 시퀀스 모델 (L/R 오버샘플 + 좌우반전 기본)",
        [
            PY,
            os.path.join(SCRIPT_DIR, "train_pose_classifier_seq.py"),
            "--seq-len",
            str(args.seq_len),
        ],
    )

    if not args.skip_single:
        run_step(
            "[3/3] 단일 프레임 모델 (가드 폴백, L/R 오버샘플 기본)",
            [PY, os.path.join(SCRIPT_DIR, "train_pose_classifier.py")],
        )

    print("\n완료. pose_classifier_seq.keras 및 (실행 시) pose_classifier.keras 를 확인하세요.")


if __name__ == "__main__":
    main()
