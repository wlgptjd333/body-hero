@echo off
chcp 65001 >nul
echo ==========================================
echo Body Hero - Model Training
echo ==========================================
echo.
echo This will train the 4-frame sequence model.
echo Requires: pose_data.json and pose_recordings_meta.json
echo.
pause
cd /d "%~dp0"
run_python.bat train_pose_classifier_seq.py
echo.
echo Training complete. Model saved to pose_classifier_seq_len4.keras
pause
