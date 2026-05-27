@echo off
chcp 65001 >nul
echo Body Hero - Python Embedded Build Script (개발자 전용)
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_python_embed.ps1"
pause
