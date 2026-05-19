"""
펀치/어퍼 L↔R 혼동 완화용 공통 유틸.

- LR_PAIRS: (왼쪽 라벨, 오른쪽 라벨) — 학습 시 소수 클래스 오버샘플링에 사용.
- oversample_lr_minorities: 훈련 배치에서 각 쌍의 적은 쪽을 복제해 다수 쪽에 가깝게 맞춤.
- print_lr_balance_report: 녹화/시퀀스 단위 L:R 비율 출력.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Sequence, Tuple

import numpy as np

# MediaPipe·게임 라벨: 몸 기준 왼손 / 오른손
LR_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("punch_l", "punch_r"),
    ("upper_l", "upper_r"),
)


def print_lr_balance_report(
    labels: Sequence[str],
    class_names: Sequence[str],
    title: str = "L/R 비율",
) -> None:
    """라벨 문자열 목록에서 punch/upper L:R 쌍별 개수·비율 출력."""
    c = Counter(labels)
    print(f"\n=== {title} ===")
    for left, right in LR_PAIRS:
        if left not in class_names or right not in class_names:
            continue
        nl, nr = c.get(left, 0), c.get(right, 0)
        tot = nl + nr
        if tot == 0:
            print(f"  {left}/{right}: 데이터 없음")
            continue
        ratio = nl / max(1, nr)
        skew = " (소수: 오른쪽)" if nl > nr else " (소수: 왼쪽)" if nr > nl else " (균형)"
        print(f"  {left}: {nl}  |  {right}: {nr}  |  L:R = {ratio:.2f}{skew}")


def print_class_distribution(
    labels: Sequence[str],
    class_names: Sequence[str],
    title: str = "클래스별 개수",
) -> None:
    """알려진 클래스 순서로 출력하고, 그 외 라벨이 있으면 함께 표시."""
    c = Counter(labels)
    print(f"\n=== {title} ===")
    for name in class_names:
        n = c.get(name, 0)
        print(f"  {name}: {n}")
    others = {k: v for k, v in c.items() if k not in class_names}
    if others:
        print("  (기타 라벨)")
        for k, v in sorted(others.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")
    print(f"  합계: {sum(c.values())}")


def oversample_lr_minorities(
    X: np.ndarray,
    y: np.ndarray,
    class_names: Sequence[str],
    rng: np.random.RandomState,
    max_ratio: float = 6.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    훈련 집합에서 각 L/R 쌍마다 '적은 쪽' 시퀀스(또는 프레임)를 복제해
    개수 목표 = min(다수쪽 개수, 소수쪽 * max_ratio).

    max_ratio: 소수 클래스를 원본 대비 최대 몇 배까지 늘릴지(다수를 무한히 맞추면 과적합 위험).
    """
    if len(X) != len(y) or len(X) == 0:
        return X, y
    label_to_idx = {c: i for i, c in enumerate(class_names)}
    chunks_x: List[np.ndarray] = [X]
    chunks_y: List[np.ndarray] = [y]

    for left, right in LR_PAIRS:
        li = label_to_idx.get(left)
        ri = label_to_idx.get(right)
        if li is None or ri is None:
            continue
        idx_l = np.where(y == li)[0]
        idx_r = np.where(y == ri)[0]
        nl, nr = len(idx_l), len(idx_r)
        if nl == 0 or nr == 0:
            continue
        if nl < nr:
            minor_idx, n_min, n_maj = idx_l, nl, nr
        elif nr < nl:
            minor_idx, n_min, n_maj = idx_r, nr, nl
        else:
            continue
        # 소수 쪽을 최대 max_ratio배까지 늘린 뒤, 그보다 다수가 많으면 다수 개수까지만 맞춤
        target = min(n_maj, int(n_min * max_ratio))
        if target <= n_min:
            continue
        need = target - n_min
        pick = rng.choice(minor_idx, size=need, replace=True)
        chunks_x.append(X[pick])
        chunks_y.append(y[pick])

    if len(chunks_x) == 1:
        return X, y
    X2 = np.concatenate(chunks_x, axis=0)
    y2 = np.concatenate(chunks_y, axis=0)
    perm = rng.permutation(len(X2))
    return X2[perm], y2[perm]


def lr_confusion_hints(
    class_names: Sequence[str],
    cm: np.ndarray,
) -> str:
    """혼동 행렬에서 L/R 쌍끼리 서로 오분류된 비율 힌트 텍스트."""
    name_to_i = {c: i for i, c in enumerate(class_names)}
    lines: List[str] = []
    for left, right in LR_PAIRS:
        li, ri = name_to_i.get(left), name_to_i.get(right)
        if li is None or ri is None:
            continue
        row_l = cm[li]
        row_r = cm[ri]
        wrong_l_as_r = row_l[ri]
        wrong_r_as_l = row_r[li]
        support_l = row_l.sum()
        support_r = row_r.sum()
        if support_l > 0:
            lines.append(
                f"  {left}가 {right}로 오분류: {wrong_l_as_r} / 행합 {int(support_l)} "
                f"({100.0 * wrong_l_as_r / support_l:.1f}%)"
            )
        if support_r > 0:
            lines.append(
                f"  {right}가 {left}로 오분류: {wrong_r_as_l} / 행합 {int(support_r)} "
                f"({100.0 * wrong_r_as_l / support_r:.1f}%)"
            )
    return "\n".join(lines) if lines else "(L/R 쌍 없음)"

