"""
ML 파이프라인 공통: 클래스 이름과 순서.

시퀀스·단일(Keras)·수집·추론에서 반드시 동일한 순서를 사용해야 softmax 인덱스가 맞습니다.
- 좌우 펀치 → punch_l / punch_r
- Godot 게임 액션명과 동일(punch_l, punch_r, upper_l, upper_r, …).
"""

from typing import Final, List

# softmax 인덱스 = 리스트 순서
POSE_CLASS_NAMES: Final[List[str]] = [
    "none",
    "guard",
    "punch_l",
    "punch_r",
    "upper_l",
    "upper_r",
    "squat",
]

GUARD_INDEX: Final[int] = 1  # pose_classifier.keras 단일 모델과 동일
