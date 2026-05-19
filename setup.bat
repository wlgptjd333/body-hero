@echo off
chcp 65001 >nul
echo Body Hero - Setup
echo =========================

:: 1. Create Python virtual environment
if not exist "tools\venv_ml\" (
    echo [1/3] Creating Python virtual environment...
    py -3.10 -m venv tools\venv_ml || python -m venv tools\venv_ml
    if %errorlevel% neq 0 (
        echo Python 3.10 is not installed. Install it from https://python.org
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists
)

:: 2. Upgrade pip + install packages
echo [2/3] Installing Python packages...
call tools\venv_ml\Scripts\python.exe -m pip install --upgrade pip -q
call tools\venv_ml\Scripts\pip.exe install -r tools\requirements_ml.txt
if %errorlevel% neq 0 (
    echo Package installation failed. Check tools/requirements_ml.txt
    pause
    exit /b 1
)

:: 3. Check Godot
echo [3/3] Checking Godot...
where godot >nul 2>&1
if %errorlevel% equ 0 (
    echo Godot installed
) else (
    echo Godot not in PATH - run manually with Godot Editor
    echo https://godotengine.org/download/windows
)

echo.
echo =========================
echo Setup complete!
echo.
echo Open in Godot Editor:  project.godot
echo Run ML webcam:         tools\venv_ml\Scripts\python.exe tools/udp_send_webcam_ml.py
echo Collect data:          tools\venv_ml\Scripts\python.exe tools/collect_pose_data.py
echo Train model:           tools\venv_ml\Scripts\python.exe tools/train_pose_classifier.py
echo.
pause
