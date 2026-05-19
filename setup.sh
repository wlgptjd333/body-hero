#!/usr/bin/env bash
set -e
echo "Body Hero - Setup"
echo "========================="

# 1. Create Python virtual environment
if [ ! -d "tools/venv_ml" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv tools/venv_ml || python -m venv tools/venv_ml
else
    echo "[1/3] Virtual environment already exists"
fi

# 2. Upgrade pip + install packages
echo "[2/3] Installing Python packages..."
tools/venv_ml/bin/python -m pip install --upgrade pip -q
tools/venv_ml/bin/pip install -r tools/requirements_ml.txt

# 3. Check Godot CLI (optional)
echo "[3/3] Checking Godot CLI..."
if command -v godot &>/dev/null; then
    echo "Godot CLI installed (can run tests)"
    godot --headless -s addons/gut/gut_cmdln.gd -d --path .
else
    echo "Godot CLI not found - run manually with Godot Editor"
fi

echo ""
echo "========================="
echo "Setup complete!"
echo ""
echo "Open in Godot Editor:  project.godot (Godot 4.6)"
echo "Run ML webcam:         tools/venv_ml/bin/python tools/udp_send_webcam_ml.py"
echo "Collect data:          tools/venv_ml/bin/python tools/collect_pose_data.py"
echo "Train model:           tools/venv_ml/bin/python tools/train_pose_classifier.py"
