"""
collect_pose_data.py와 동일한 라벨 정책으로
pose_data.json 안의 **프레임 라벨**을 pose_recordings_meta.json의
**녹화 구간(start_index, frame_count) + 누른 키(label)** 기준으로 다시 만듭니다.
기본은 60프레임 전부 누른 키로 통일; 구 방식은 --impact-labeling.

왜 필요한가?
- 콘솔의 "동작별 녹화 횟수"는 **메타(키를 누른 회차)** 를 세는 것이지,
  pose_data.json 안의 **실제 프레임 라벨** 개수와 같지 않을 수 있습니다.
- 예전 버그·수동 편집·다른 파일과 섞임 등으로 **메타와 프레임 라벨이 어긋난 경우**
  이 스크립트로 랜드마크는 그대로 두고 라벨만 메타에 맞게 재생성할 수 있습니다.

백업 (기본):
- pose_data_backup_before_relabel.json
- pose_recordings_meta_backup_before_relabel.json
  이미 있으면 새로 안 만듦. --force-backup 으로 타임스탬프 백업.

사용 (tools 폴더):
  python relabel_pose_with_collect.py
  python relabel_pose_with_collect.py --dry-run
  python relabel_pose_with_collect.py --impact-labeling --drop-frames 4
  python relabel_pose_with_collect.py --in-place   # start_index 유지, 라벨·impact만 갱신
  (기본) 메타 끝 phantom/초과는 자동 보정 후 재라벨. 끄기: --no-repair-meta
"""

from __future__ import annotations

import argparse
import json
import os

# collect_pose_data 임포트 시 TF/MediaPipe 로그 억제
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("GLOG_minloglevel", "2")
from collections import Counter
from datetime import datetime
from typing import List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data.json")
META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta.json")

BACKUP_DATA_PATH = os.path.join(SCRIPT_DIR, "pose_data_backup_before_relabel.json")
BACKUP_META_PATH = os.path.join(SCRIPT_DIR, "pose_recordings_meta_backup_before_relabel.json")


def _audit_meta_covers_data(data: list, recs: list) -> Tuple[bool, str]:
    """녹화 구간이 [0, len(data))를 빈틈없이 덮는지 (collect 정상 저장 모델)."""
    if not recs:
        return False, "recordings 가 비었습니다."
    recs_sorted = sorted(recs, key=lambda r: r.get("start_index", 0))
    n = len(data)
    pos = 0
    for r in recs_sorted:
        s = int(r.get("start_index", 0))
        c = int(r.get("frame_count", 0))
        if s != pos:
            return (
                False,
                f"구간 불연속: 누적 끝={pos} 인데 다음 녹화 start_index={s} "
                f"(메타 순서/삭제/수동 편집 의심)",
            )
        if s < 0 or c < 0 or s + c > n:
            return False, f"인덱스 초과: start={s} count={c} len(data)={n}"
        pos = s + c
    if pos != n:
        return (
            False,
            f"데이터 길이와 메타 합 불일치: 메타로 덮은 프레임={pos}, len(data)={n} "
            f"(pose_data만 잘렸거나 메타가 다른 세션일 수 있음)",
        )
    return True, "ok"


def _repair_recordings_for_data_len(recs: list, n: int) -> Tuple[List[dict], List[str]]:
    """
    흔한 불일치: 마지막 녹화는 메타에만 있고 Q 저장 전 종료·크래시로 pose_data에 60프레임이 안 붙음
    → start_index == len(data) 인 phantom 항목 제거.

    또 마지막 녹화의 frame_count만 데이터 끝을 넘는 경우 → frame_count 축소.
    """
    msgs: list[str] = []
    ordered = sorted(recs, key=lambda r: int(r.get("start_index", 0)))
    fixed: list = []
    phantom_rows: list = []
    for r in ordered:
        rr = dict(r)
        s = int(rr.get("start_index", 0))
        if s >= n:
            phantom_rows.append((rr.get("label"), s))
            continue
        fixed.append(rr)

    if phantom_rows:
        by_lab = Counter(lab for lab, _ in phantom_rows)
        smin = min(s for _, s in phantom_rows)
        smax = max(s for _, s in phantom_rows)
        msgs.append(
            f"phantom 녹화 {len(phantom_rows)}개 제거 (메타에만 있고 start_index ≥ len(data)={n})"
        )
        msgs.append(f"  라벨별 제거 횟수: {dict(by_lab)}")
        msgs.append(f"  제거된 start_index 범위: {smin} … {smax}")
        msgs.append(
            f"  ※ 디스크의 pose_data.json 은 {n}프레임뿐이라, 그 뒤 인덱스는 '녹화했다고 메타에만 남은' 항목입니다."
        )

    while fixed:
        last = fixed[-1]
        s = int(last.get("start_index", 0))
        c = int(last.get("frame_count", 0))
        if s + c <= n:
            break
        new_c = n - s
        if new_c <= 0:
            msgs.append(
                f"제거: data 밖 녹화 label={last.get('label')} start={s} count={c}"
            )
            fixed.pop()
            continue
        msgs.append(
            f"축소: 마지막 녹화 label={last.get('label')} frame_count {c} → {new_c} "
            f"(data 끝 {n}에 맞춤)"
        )
        last["frame_count"] = new_c
        if int(last.get("impact_idx", -1)) >= new_c:
            last.pop("impact_idx", None)
            last.pop("guard_start_idx", None)
            msgs.append("  → impact_idx/guard_start_idx 제거(범위 밖)")
        break

    return fixed, msgs


# collect_pose_data.LABEL_DROP 문자열 비교용 (순환 임포트 방지)
def _frame_counter_excluding_drop(data: list) -> Counter:
    from collect_pose_data import LABEL_DROP

    c = Counter()
    for x in data:
        if not isinstance(x, dict):
            continue
        lab = x.get("label")
        if not lab or lab == LABEL_DROP:
            continue
        c[lab] += 1
    return c


def _warn_frame_labels_vs_meta_recordings(data: list, recs: list) -> None:
    fc = _frame_counter_excluding_drop(data)
    mc = Counter(r.get("label") for r in recs if r.get("label"))
    punch_like = (
        "punch_l",
        "punch_r",
        "upper_l",
        "upper_r",
    )
    lines = []
    for pl in punch_like:
        fcnt = fc.get(pl, 0)
        mcnt = mc.get(pl, 0)
        if fcnt >= 40 and mcnt == 0:
            lines.append(
                f"  - 프레임에 '{pl}' 가 {fcnt}개 있는데, 남은 메타 녹화에는 '{pl}' 키가 0회입니다."
            )
    if lines:
        print(
            "\n[경고] 재라벨은 **메타에 적힌 키(녹화 시 누른 번호)** 로 랜드마크를 다시 라벨링합니다."
            "\n  아래처럼 프레임 라벨과 메타가 어긋나면, 저장 후 펀치 등이 메타 동작으로 **덮어써집니다**."
        )
        for ln in lines:
            print(ln)
        print(
            "  → phantom 제거 후 남은 메타가 '앞쪽 34회차'만 담고 있을 수 있습니다. "
            "펀치 녹화는 더 뒤 start_index 에만 있었다면 그 항목은 이미 제거된 상태입니다.\n"
            "  → 백업 메타·pose_data 짝을 맞추거나, 펀치를 다시 녹화하는 편이 안전할 수 있습니다.\n"
        )


def _print_frame_label_stats(data: list, title: str) -> None:
    labels = [x.get("label") for x in data if isinstance(x, dict)]
    c = Counter(labels)
    print(f"\n--- {title} (프레임 라벨 상위) ---")
    for lab, cnt in c.most_common(20):
        print(f"  {lab}: {cnt}")
    print(f"  합계 프레임: {len(data)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="메타 기준으로 pose_data.json 프레임 라벨 재생성 (collect와 동일 정책)"
    )
    parser.add_argument("--data", default=DATA_PATH)
    parser.add_argument("--meta", default=META_PATH)
    parser.add_argument(
        "--impact-labeling",
        action="store_true",
        help="collect의 임팩트/none/drop 분할 라벨. 기본은 전 프레임 누른 키로 통일.",
    )
    parser.add_argument(
        "--drop-frames",
        type=int,
        default=None,
        help="--impact-labeling 일 때만: 윈드업 drop 프레임 수 (기본: collect_pose_data.WINDUP_DROP_FRAMES)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일 저장 없이 검사·통계만 출력",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="데이터 순서·start_index 유지, 각 구간의 label(및 메타 impact)만 갱신",
    )
    parser.add_argument(
        "--force-backup",
        action="store_true",
        help="기존 백업이 있어도 타임스탬프 파일명으로 백업 추가",
    )
    parser.add_argument(
        "--ignore-coverage",
        action="store_true",
        help="메타가 데이터 전체를 덮지 않아도 진행(비권장: 깨진 구간은 건너뜀)",
    )
    parser.set_defaults(repair_meta=True)
    parser.add_argument(
        "--no-repair-meta",
        action="store_false",
        dest="repair_meta",
        help="메타 끝 자동 보정 끔(기본은 켬: phantom 제거·마지막 frame_count 축소)",
    )
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

    if args.repair_meta:
        recs, repair_msgs = _repair_recordings_for_data_len(recs, len(data))
        meta_obj = {**meta_obj, "recordings": recs}
        print("\n[메타 자동보정] len(pose_data)에 맞게 recordings 조정:")
        for m in repair_msgs:
            print(f"  • {m}")
        if not repair_msgs:
            print("  (변경 없음 — 이미 데이터 길이와 맞음)")

    try:
        import collect_pose_data as cpd
    except Exception as e:
        print(f"collect_pose_data 임포트 실패: {e}")
        return

    wdf = args.drop_frames if args.drop_frames is not None else cpd.WINDUP_DROP_FRAMES
    PUNCH_LIKE = ("punch_l", "punch_r", "upper_l", "upper_r")

    ok_cov, msg = _audit_meta_covers_data(data, recs)
    print(f"메타·데이터 커버리지 검사: {msg}")
    if not ok_cov and not args.ignore_coverage:
        print(
            "\n중단했습니다. 자동보정 후에도 pose_data.json 과 메타의 "
            "start_index/frame_count 가 맞지 않습니다.\n"
            "  - 가운데 녹화가 지워지거나 메타/데이터가 서로 다른 백업에서 온 경우 등 "
            "‘끝만’ 고칠 수 없는 깨짐일 수 있습니다.\n"
            "  - 백업에서 짝이 맞는 파일로 복구하거나, "
            "`--ignore-coverage` 로 가능한 구간만 재라벨(비권장)을 검토하세요.\n"
            "  - 자동보정을 끈 상태였다면 기본(보정 켬)으로 다시 실행해 보세요."
        )
        if not args.repair_meta:
            print(
                "  ※ 지금은 --no-repair-meta 입니다. phantom 제거를 쓰려면 "
                "`python relabel_pose_with_collect.py` 만 실행하세요(보정 기본 켬)."
            )
        return

    _warn_frame_labels_vs_meta_recordings(data, recs)

    _print_frame_label_stats(data, "재라벨 전 pose_data.json")

    meta_counts = Counter(r.get("label") for r in recs if r.get("label"))
    print("\n--- 메타: 녹화 회차(누른 키) ---")
    for lab in [
        "none",
        "guard",
        "punch_l",
        "punch_r",
        "upper_l",
        "upper_r",
    ]:
        if meta_counts.get(lab):
            print(f"  {lab}: {meta_counts[lab]}")

    if args.in_place:
        new_recs = []
        for idx_rec, rec in enumerate(recs):
            label = rec.get("label")
            start = int(rec.get("start_index", 0))
            frame_count = int(rec.get("frame_count", 0))
            end = start + frame_count
            if start < 0 or end > len(data) or frame_count <= 0:
                print(f"[건너뜀] recordings[{idx_rec}] label={label} 구간 [{start},{end}) 가 데이터 범위 밖")
                new_recs.append(dict(rec))
                continue
            segment = data[start:end]
            frames_flat = [item.get("landmarks") for item in segment]
            if any((not lm or len(lm) != 99) for lm in frames_flat):
                print(f"[건너뜀] recordings[{idx_rec}] label={label} landmarks 손상")
                new_recs.append(dict(rec))
                continue

            if args.impact_labeling:
                labeled, impact_idx = cpd._label_recorded_frames(
                    label,
                    frames_flat,
                    windup_drop_frames=wdf,
                    hold_until_end=(label in PUNCH_LIKE),
                )
            else:
                labeled, impact_idx = cpd._label_recorded_frames_uniform(label, frames_flat)
            if len(labeled) != len(segment):
                print(f"[경고] recordings[{idx_rec}] 라벨 길이 불일치, 건너뜀")
                new_recs.append(dict(rec))
                continue
            for i, row in enumerate(labeled):
                data[start + i]["label"] = row["label"]

            new_rec = dict(rec)
            new_rec.pop("impact_idx", None)
            new_rec.pop("guard_start_idx", None)
            if args.impact_labeling:
                if label in PUNCH_LIKE and impact_idx is not None:
                    new_rec["impact_idx"] = impact_idx
                elif label == "guard" and impact_idx is not None:
                    new_rec["guard_start_idx"] = impact_idx
            new_recs.append(new_rec)

            action_count = sum(1 for x in labeled if x["label"] == label)
            drop_count = sum(1 for x in labeled if x.get("label") == cpd.LABEL_DROP)
            mode = "impact" if args.impact_labeling else "uniform"
            print(
                f"[{idx_rec+1}/{len(recs)}] in-place {label} ({mode}): "
                f"'{label}' 프레임 {action_count}, drop {drop_count}, impact_idx={impact_idx}"
            )

        meta_out = {"recordings": new_recs}
        _print_frame_label_stats(data, "재라벨 후 (in-place)")

        if args.dry_run:
            print("\n[dry-run] 저장 안 함")
            return

        _write_backups(data, meta_obj, args.force_backup)
        _atomic_write(args.data, data)
        _atomic_write(args.meta, meta_out)
        print(f"\n저장 완료: {args.data}, {args.meta}")
        return

    # 전체 재조립 (연속 메타 모델) — start_index 를 0부터 다시 매김
    new_data: list = []
    new_recs: list = []

    recs_sorted = sorted(recs, key=lambda r: r.get("start_index", 0))
    if not ok_cov:
        print(
            "[경고] --ignore-coverage: 메타와 len(data)가 맞지 않습니다. "
            "들어맞는 녹화 구간만 이어 붙이며, 빠진 인덱스의 프레임은 버려질 수 있습니다."
        )

    n = len(data)
    for idx_rec, rec in enumerate(recs_sorted):
        label = rec.get("label")
        start = int(rec.get("start_index", 0))
        frame_count = int(rec.get("frame_count", 0))
        end = start + frame_count

        if ok_cov:
            if end > n:
                print(f"[경고] 구간 초과 label={label} start={start} end={end} n={n}")
                continue
        else:
            if start < 0 or frame_count <= 0 or end > n:
                print(f"[건너뜀] label={label} [{start},{end}) len={n}")
                continue

        frames = data[start:end]
        if not frames:
            print(f"[경고] 빈 구간 label={label} start={start}")
            continue

        frames_flat = [item.get("landmarks") for item in frames]
        if any((not lm or len(lm) != 99) for lm in frames_flat):
            print(f"[경고] landmarks 손상 label={label} start={start}, 건너뜀")
            continue

        if args.impact_labeling:
            labeled, impact_idx = cpd._label_recorded_frames(
                label,
                frames_flat,
                windup_drop_frames=wdf,
                hold_until_end=(label in PUNCH_LIKE),
            )
        else:
            labeled, impact_idx = cpd._label_recorded_frames_uniform(label, frames_flat)

        start_new = len(new_data)
        new_data.extend(labeled)

        new_rec = {
            "label": label,
            "start_index": start_new,
            "frame_count": len(labeled),
        }
        if args.impact_labeling:
            if label in PUNCH_LIKE and impact_idx is not None:
                new_rec["impact_idx"] = impact_idx
            elif label == "guard" and impact_idx is not None:
                new_rec["guard_start_idx"] = impact_idx

        new_recs.append(new_rec)

        action_count = sum(1 for x in labeled if x["label"] == label)
        drop_count = sum(1 for x in labeled if x.get("label") == cpd.LABEL_DROP)
        mode = "impact" if args.impact_labeling else "uniform"
        print(
            f"[{idx_rec+1}/{len(recs_sorted)}] {label} ({mode}): "
            f"{frame_count}프레임 → {len(labeled)}프레임, "
            f"'{label}' {action_count}, drop {drop_count}, impact_idx={impact_idx}"
        )

    _print_frame_label_stats(new_data, "재라벨 후 (재조립)")

    print(f"\n기존 데이터 프레임 수: {len(data)}")
    print(f"재라벨 후 데이터 프레임 수: {len(new_data)}")
    print(f"기존 recordings 개수: {len(recs)}")
    print(f"재라벨 후 recordings 개수: {len(new_recs)}")

    if args.dry_run:
        print("\n[dry-run] 저장 안 함")
        return

    _write_backups(data, meta_obj, args.force_backup)

    _atomic_write(args.data, new_data)
    meta_write = {"recordings": new_recs}
    _atomic_write(args.meta, meta_write)
    print(f"\n재라벨 데이터 저장: {args.data}")
    print(f"재라벨 메타 저장: {args.meta}")


def _write_backups(data_orig, meta_orig, force: bool) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    def backup(path: str, obj) -> None:
        if os.path.isfile(path) and not force:
            print(f"[참고] 백업 이미 존재, 건너뜀: {path} (--force-backup 으로 타임스탬프 백업)")
            return
        out_path = path
        if os.path.isfile(path) and force:
            out_path = path.replace(".json", f"_{ts}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"백업 저장: {out_path}")

    backup(BACKUP_DATA_PATH, data_orig)
    backup(BACKUP_META_PATH, meta_orig)


def _atomic_write(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


if __name__ == "__main__":
    main()
