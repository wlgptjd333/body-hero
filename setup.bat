@echo off
chcp 65001 >nul
echo Body Hero — 환경 설정
echo =========================

:: 1. Python 가상환경 생성
if not exist "tools\venv_ml\" (
    echo [1/3] Python 가상환경 생성 중...
    python -m venv tools\venv_ml
    if %errorlevel% neq 0 (
        echo Python이 설치되어 있지 않습니다. https://python.org 에서 3.12를 설치하세요.
        pause
        exit /b 1
    )
) else (
    echo [1/3] 가상환경 이미 존재함
)

:: 2. pip 업그레이드 + 패키지 설치
echo [2/3] Python 패키지 설치 중...
call tools\venv_ml\Scripts\python.exe -m pip install --upgrade pip -q
call tools\venv_ml\Scripts\pip.exe install -r tools\requirements_ml.txt
if %errorlevel% neq 0 (
    echo 패키지 설치 실패. tools/requirements_ml.txt 확인
    pause
    exit /b 1
)

:: 3. Godot 확인
echo [3/3] Godot 확인 중...
where godot >nul 2>&1
if %errorlevel% equ 0 (
    echo Godot 설치됨
) else (
    echo Godot이 PATH에 없음 — Godot Editor로 수동 실행 필요
    echo https://godotengine.org/download/windows
)

echo.
echo =========================
echo 설정 완료!
echo.
echo Godot Editor로 열기:  project.godot
echo ML 웹캠 실행:         tools\venv_ml\Scripts\python.exe tools/udp_send_webcam_ml.py
echo 데이터 수집:           tools\venv_ml\Scripts\python.exe tools/collect_pose_data.py
echo 모델 학습:            tools\venv_ml\Scripts\python.exe tools/train_pose_classifier.py
echo.
pause
