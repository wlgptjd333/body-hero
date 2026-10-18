@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 웹캠 없이 도구만 시험합니다(가짜 입력, 4배속). 결과는 실험으로 쓰지 마세요.
"C:\Users\User\Documents\body-hero\.venv_thesis_ml\Scripts\python.exe" play_lab.py --fake --speed 4
pause
