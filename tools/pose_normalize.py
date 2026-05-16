"""
MediaPipe Pose 랜드마크를 어깨 너비(shoulder width) 기준으로 정규화합니다.
거리/카메라 위치가 달라도 같은 동작이 비슷한 값으로 들어가게 해서
가까이서만 학습해도 멀리서 판정이 잘 되도록 돕습니다.

사용: from pose_normalize import normalize_landmarks, normalize_landmarks_flat
"""
import math

# MediaPipe Pose 33점 인덱스
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12


def _get_xy(lm):
    """랜드마크 1개에서 (x, y) 추출. 리스트 또는 .x/.y 객체 지원."""
    if hasattr(lm, "x"):
        return (lm.x, lm.y)
    return (lm[0], lm[1])


def shoulder_center_and_width(landmarks):
    """
    landmarks: 33개 랜드마크 (각 .x, .y, .z 또는 [x,y,z])
    returns: (center_x, center_y), width
    width = 어깨 간 거리 (2D). 0이면 1e-5 반환해 division by zero 방지.
    """
    if len(landmarks) <= max(LEFT_SHOULDER, RIGHT_SHOULDER):
        return (0.5, 0.5), 1.0
    l = _get_xy(landmarks[LEFT_SHOULDER])
    r = _get_xy(landmarks[RIGHT_SHOULDER])
    cx = (l[0] + r[0]) / 2
    cy = (l[1] + r[1]) / 2
    w = math.hypot(r[0] - l[0], r[1] - l[1])
    if w <= 0:
        w = 1e-5
    return (cx, cy), w


def _get_xyz(lm):
    if hasattr(lm, "z"):
        return (lm.x, lm.y, lm.z)
    if len(lm) >= 3:
        return (lm[0], lm[1], lm[2])
    return (lm[0], lm[1], 0.0)


def normalize_landmarks(landmarks, center=None, width=None):
    """
    랜드마크를 어깨 중심 기준·어깨 너비 스케일로 정규화.
    center, width를 None으로 두면 landmarks에서 계산.

    returns: 33개 (x', y', z') 리스트. z는 width로 나눠 스케일 맞춤.
    """
    if center is None or width is None:
        center, width = shoulder_center_and_width(landmarks)
    cx, cy = center
    out = []
    for lm in landmarks:
        x, y, z = _get_xyz(lm)
        out.append((
            (x - cx) / width,
            (y - cy) / width,
            z / width,
        ))
    return out


def normalize_landmarks_flat(landmarks, center=None, width=None):
    """
    정규화한 랜드마크를 1차원 리스트로 반환 (모델 입력용).
    길이: 33 * 3 = 99
    """
    norm = normalize_landmarks(landmarks, center=center, width=width)
    return [v for t in norm for v in t]


def landmarks_to_flat(landmarks):
    """정규화 없이 33*3 = 99 float 리스트로만 변환 (저장/로드 호환)."""
    return [v for lm in landmarks for v in _get_xyz(lm)]
