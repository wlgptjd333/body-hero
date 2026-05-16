#!/usr/bin/env bash
set -e
echo "Body Hero — 환경 설정"
echo "========================="

# 1. Python 가상환경 생성
if [ ! -d "tools/venv_ml" ]; then
    echo "[1/3] Python 가상환경 생성 중..."
    python3 -m venv tools/venv_ml || python -m venv tools/venv_ml
else
    echo "[1/3] 가상환경 이미 존재함"
fi

# 2. pip 업그레이드 + 패키지 설치
echo "[2/3] Python 패키지 설치 중..."
tools/venv_ml/bin/python -m pip install --upgrade pip -q
tools/venv_ml/bin/pip install -r tools/requirements_ml.txt

# 3. Godot CLI 확인 (선택)
echo "[3/3] Godot CLI 확인 중..."
if command -v godot &>/dev/null; then
    echo "Godot CLI 설치됨 (테스트 실행 가능)"
    godot --headless -s addons/gut/gut_cmdln.gd -d --path .
else
    echo "Godot CLI 없음 — Godot Editor로 수동 실행"
fi

echo ""
echo "========================="
echo "설정 완료!"
echo ""
echo "Godot Editor로 열기:  project.godot (Godot 4.6)"
echo "ML 웹캠 실행:         tools/venv_ml/bin/python tools/udp_send_webcam_ml.py"
echo "데이터 수집:          tools/venv_ml/bin/python tools/collect_pose_data.py"
echo "모델 학습:            tools/venv_ml/bin/python tools/train_pose_classifier.py"
