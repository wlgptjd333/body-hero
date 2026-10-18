@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 게임 v1.1(body-hero-rebuild) 인식 코드와 모델로 확인 실험을 시작합니다. 게임은 꺼 두세요.
set BH_TOOLS=C:\Users\User\Documents\body-hero-rebuild\tools
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" play_lab.py
if errorlevel 1 pause
