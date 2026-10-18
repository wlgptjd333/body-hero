#!/bin/bash
cd "$(dirname "$0")"
PY=/c/Users/User/Documents/body-hero/.venv_thesis_ml/Scripts/python.exe
export BH_THREADS=3 PYTHONIOENCODING=utf-8 TF_CPP_MIN_LOG_LEVEL=2
( BH_ARCH=gap BH_SEQ=2,4,8 $PY run_groupcv.py; echo CHAIN DONE ) > log_cv_gap.txt 2>&1 &
( BH_ARCH=lstm BH_SEQ=2,4,8 $PY run_groupcv.py; echo CHAIN DONE ) > log_cv_lstm.txt 2>&1 &
( BH_ARCH=mlp BH_SEQ=1 $PY run_groupcv.py; BH_ARCH=gru BH_SEQ=4 $PY run_groupcv.py; echo CHAIN DONE ) > log_cv_mlp_gru.txt 2>&1 &
( BH_ARCH=gap BH_SEQ=6,8 $PY run_fixed_extra.py; BH_ARCH=gru BH_SEQ=4 $PY run_fixed_extra.py; echo CHAIN DONE ) > log_fixed_gap_gru.txt 2>&1 &
( BH_ARCH=lstm BH_SEQ=6,8 $PY run_fixed_extra.py; echo CHAIN DONE ) > log_fixed_lstm.txt 2>&1 &
sleep 5
$PY keep_awake.py
wait
