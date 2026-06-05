@echo off
chcp 65001 >nul
echo ==========================================
echo Body Hero - Pose Data Collection
echo ==========================================
echo.
echo This will open your webcam and let you record pose data.
echo Press the key shown on screen to label each action.
echo.
echo Controls (during recording):
echo   1=none  2=guard  3=punch_l  4=punch_r
echo   5=upper_l  6=upper_r  7=squat
echo   Q=quit
echo.
pause
cd /d "%~dp0"
run_python.bat collect_pose_data.py
echo.
echo Collection complete. Data saved to pose_data.json
pause
