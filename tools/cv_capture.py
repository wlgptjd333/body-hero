"""
OpenCV VideoCapture — Windows에서 USB/내장 인덱스 뒤바뀜 완화용 백엔드 선택.
collect_pose_data, udp_send_webcam*, list_cameras, test_pose_live 등에서 공통 사용.
"""
from __future__ import annotations

import sys
from typing import Any, Tuple


def open_cv_video_capture(camera_index: int, backend: str) -> Tuple[Any, str]:
    import cv2

    if backend == "default":
        return cv2.VideoCapture(camera_index), "default"
    if backend == "dshow":
        if hasattr(cv2, "CAP_DSHOW"):
            return cv2.VideoCapture(camera_index, cv2.CAP_DSHOW), "CAP_DSHOW"
        return cv2.VideoCapture(camera_index), "default(fallback)"
    if backend == "msmf":
        if hasattr(cv2, "CAP_MSMF"):
            return cv2.VideoCapture(camera_index, cv2.CAP_MSMF), "CAP_MSMF"
        return cv2.VideoCapture(camera_index), "default(fallback)"
    # auto
    if sys.platform == "win32" and hasattr(cv2, "CAP_DSHOW"):
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap, "CAP_DSHOW(auto)"
    if hasattr(cv2, "CAP_MSMF"):
        cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
        if cap.isOpened():
            return cap, "CAP_MSMF(auto)"
    return cv2.VideoCapture(camera_index), "default(auto)"
