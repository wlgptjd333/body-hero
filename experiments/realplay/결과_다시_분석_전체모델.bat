@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 가장 최근 실험을 모델 15개 전부로 다시 분석합니다(5~10분).
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" analyze_session.py --models all
echo.
echo 결과: results 폴더의 가장 최근 폴더 안 결과요약.md
pause
