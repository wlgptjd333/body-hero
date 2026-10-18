@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 가장 최근 회차의 시행 목록을 엽니다. 분석에서 뺄 시행을 고르세요.
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" trial_editor.py
