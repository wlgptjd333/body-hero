"""
pose_data.json / 시퀀스 윈도우 기준으로 jab·upper·hook 의 L:R 녹화·샘플 수를 출력.
왼쪽/오른쪽 데이터가 치우치면 train_pose_classifier_seq.py 가 자동으로 소수 쪽을 오버샘플하지만,
먼저 이 리포트로 얼마나 모았는지 확인하는 것을 권장.

실행: cd tools → python report_pose_lr_balance.py [--seq-len 8]
"""
import argparse
import os
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from lr_pose_utils import print_class_distribution, print_lr_balance_report  # noqa: E402
from train_pose_classifier_seq import (  # noqa: E402
    ALL_CLASS_NAMES,
    DEFAULT_DATA,
    DEFAULT_META,
    load_sequences_by_recordings,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="잽/어퍼/훅 L:R 데이터 균형 리포트")
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--meta", default=DEFAULT_META)
    parser.add_argument("--seq-len", type=int, default=8)
    args = parser.parse_args()

    if not os.path.isfile(args.data):
        print(f"파일 없음: {args.data}")
        raise SystemExit(1)

    import json

    if os.path.isfile(args.meta):
        with open(args.meta, "r", encoding="utf-8") as f:
            meta = json.load(f)
        recs = meta.get("recordings", [])
        if isinstance(recs, list) and recs:
            meta_labels = [r.get("label") for r in recs if r.get("label")]
            print_class_distribution(
                meta_labels,
                ALL_CLASS_NAMES,
                title="녹화 메타: 누른 키(회차) — pose_recordings_meta.json",
            )
            print(
                "※ 여기 숫자는 '그 라벨로 녹화 시작한 횟수'입니다. "
                "아래 프레임 통계와 다르면 임팩트 검출 실패로 전부 none/drop만 저장됐을 수 있습니다."
            )

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    frame_labels = [x.get("label") for x in data if x.get("label") not in (None, "drop")]
    print_class_distribution(
        frame_labels, ALL_CLASS_NAMES, title="프레임 라벨 전체 (pose_data.json, drop 제외)"
    )
    print_lr_balance_report(frame_labels, ALL_CLASS_NAMES, title="프레임 L/R 쌍만 (잽·어퍼·훅)")

    X_seqs, y_list = load_sequences_by_recordings(
        args.data, args.meta, ALL_CLASS_NAMES, args.seq_len, skip_labels=["drop"]
    )
    print(f"\n시퀀스 샘플 수 (seq_len={args.seq_len}): {len(y_list)}")
    print(
        "※ 시퀀스 개수 = 슬라이딩 윈도우로 잘린 샘플 수라서, 아래 중심 라벨 합과 같지 않을 수 있습니다."
    )
    print_class_distribution(
        y_list, ALL_CLASS_NAMES, title="시퀀스 중심 라벨 — 전체 클래스"
    )
    print_lr_balance_report(y_list, ALL_CLASS_NAMES, title="시퀀스 L/R 쌍만")

    fc = Counter(frame_labels)
    print("\n권장:")
    if fc.get("jab_r", 0) == 0 and fc.get("jab_l", 0) > 0:
        print("  [중요] jab_r 프레임이 0입니다. collect_pose_data.py 에서 키 3으로 오른손 잽을 반드시 녹화하세요.")
        print("    (좌우반전 증강만으로는 실제 오른손 궤적과 항상 같지 않을 수 있습니다.)")
    if fc.get("upper_l", 0) + fc.get("upper_r", 0) == 0:
        print("  어퍼(upper_l / upper_r) 프레임이 없습니다. 키 4·5로 녹화하세요.")
    if fc.get("hook_l", 0) + fc.get("hook_r", 0) == 0:
        print("  훅(hook_l / hook_r) 프레임이 없습니다. 키 6·7로 녹화하세요.")
    print("  - 어퍼는 L/R 헷갈리기 쉬우니 upper_l / upper_r 녹화 횟수를 비슷하게.")
    print("  - 학습: python train_pose_classifier_seq.py (기본: 좌우반전 증강 + L/R 오버샘플)")


if __name__ == "__main__":
    main()
