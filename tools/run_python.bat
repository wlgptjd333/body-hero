@echo off
chcp 65001 >nul
REM Body Hero Python Embedded Environment Runner

set PYTHON_EXE=%~dp0python_embed\python.exe

if not exist "%PYTHON_EXE%" (
    echo ERROR: python_embed\python.exe not found!
    echo Please ensure the python_embed folder is in the tools/ directory.
    echo.
    echo If you downloaded the game without Python embed:
    echo 1. Download BodyHero-PythonEmbed.zip from the GitHub Release
    echo 2. Extract it to the same folder as Body Hero.exe
    pause
    exit /b 1
)

if "%~1"=="" (
    echo ==========================================
    echo Body Hero Python Embedded Environment
    echo ==========================================
    echo.
    echo Usage: run_python.bat [script.py] [args...]
    echo.
    echo Examples:
    echo   run_python.bat collect_pose_data.py
    echo   run_python.bat train_pose_classifier_seq.py
    echo   run_python.bat udp_send_webcam_ml.py
    echo.
    echo Available scripts in tools/:
    dir /b "%~dp0*.py"
    echo.
    echo Launching Python shell...
    echo.
    "%PYTHON_EXE%"
) else (
    echo Running: %~1
    "%PYTHON_EXE%" "%~dp0%~1" %2 %3 %4 %5 %6 %7 %8 %9
)
