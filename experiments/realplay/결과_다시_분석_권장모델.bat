@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 가장 최근 실험을 권장 모델(배포, GAP 4프레임, LSTM 3프레임)로 다시 분석합니다.
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" analyze_session.py --models recommended
echo.
echo 결과: results 폴더의 가장 최근 폴더 안 결과요약.md
pause
