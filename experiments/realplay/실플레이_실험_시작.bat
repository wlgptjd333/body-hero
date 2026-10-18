@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Body Hero 실플레이 실험을 시작합니다. 게임은 꺼 두세요.
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" play_lab.py
if errorlevel 1 pause
