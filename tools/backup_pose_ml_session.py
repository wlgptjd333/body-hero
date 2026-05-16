"""
현재 tools 폴더의 포즈 ML 데이터·가중치·히스토리를 타임스탬프 폴더로 옮기고,
빈 pose_data.json + pose_recordings_meta.json 을 만들어 처음부터 수집할 수 있게 합니다.

실행 (tools 디렉터리에서):
  python backup_pose_ml_session.py
  python backup_pose_ml_session.py --dry-run   # 이동만 시뮬레이션
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 이동 대상 (있을 때만)
FILES_TO_ARCHIVE = [
    "pose_data.json",
    "pose_recordings_meta.json",
    "pose_classifier.keras",
    "pose_classifier_seq.keras",
    "pose_classifier_seq_len4.keras",
    "training_history.json",
    "training_history_seq.json",
    "classification_report.txt",
    "classification_report_seq.txt",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="pose_data / keras 등 ML 세션 백업 후 빈 데이터로 리셋")
    parser.add_argument("--dry-run", action="store_true", help="실제 이동·쓰기 없이 출력만")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = os.path.join(SCRIPT_DIR, "pose_ml_backup", f"pose_ml_backup_{stamp}")
    os.makedirs(dest_dir, exist_ok=True)

    readme = os.path.join(dest_dir, "README.txt")
    readme_body = (
        "Body Hero pose ML 백업\n"
        f"시각: {stamp}\n"
        "이 폴더로 pose_data.json, 메타, keras, 리포트 등을 옮겼습니다.\n"
        "복구: 파일을 tools/ 로 이름 그대로 복사하면 됩니다.\n"
    )
    if not args.dry_run:
        with open(readme, "w", encoding="utf-8") as f:
            f.write(readme_body)
    else:
        print("[dry-run] README 생략")

    moved = 0
    for name in FILES_TO_ARCHIVE:
        src = os.path.join(SCRIPT_DIR, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(dest_dir, name)
        print(f"  이동: {name} -> {dest_dir}/")
        if not args.dry_run:
            shutil.move(src, dst)
        moved += 1

    if moved == 0:
        print("옮길 파일이 없었습니다 (이미 비어 있거나 경로가 다름).")
    else:
        print(f"총 {moved}개 파일을 {dest_dir} 로 이동했습니다.")

    empty_data = os.path.join(SCRIPT_DIR, "pose_data.json")
    empty_meta = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")
    if not args.dry_run:
        if not os.path.isfile(empty_data):
            with open(empty_data, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print("생성: pose_data.json (빈 배열)")
        else:
            print("유지: pose_data.json (이미 존재 — 수동으로 비우려면 삭제 후 재실행)")
        if not os.path.isfile(empty_meta):
            with open(empty_meta, "w", encoding="utf-8") as f:
                json.dump({"recordings": []}, f, ensure_ascii=False, indent=2)
            print("생성: pose_recordings_meta.json (빈 recordings)")
        else:
            print("유지: pose_recordings_meta.json (이미 존재)")
    else:
        print("[dry-run] 빈 pose_data / meta 생성 단계 생략")

    print("\n다음: python collect_pose_data.py 로 녹화 → python train_pose_classifier.py")
    print("     → python train_pose_classifier_seq.py [--seq-len 4]")


if __name__ == "__main__":
    main()
