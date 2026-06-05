@echo off
chcp 65001 >nul
echo ==========================================
echo Body Hero - Webcam ML Test
echo ==========================================
echo.
echo This runs the webcam ML bridge in test mode.
echo Make sure Godot game is NOT running (port conflict).
echo.
echo Controls:
echo   Q = quit
echo   --camera-index N = use camera N
echo   --profile NAME = use profile (precise/balanced/rapid/max_speed)
echo.
pause
cd /d "%~dp0"
run_python.bat udp_send_webcam_ml.py --profile balanced
echo.
pause
