@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 지금까지의 실험 회차를 촬영 조건별로 합칩니다(1회차 예비 실험은 제외).
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" aggregate_sessions.py
echo.
echo 결과: results\종합_결과.md
pause
