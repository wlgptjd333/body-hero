#!/bin/bash
cd "$(dirname "$0")"
PY=/c/Users/User/Documents/body-hero/.venv_thesis_ml/Scripts/python.exe
export BH_THREADS=3 PYTHONIOENCODING=utf-8 TF_CPP_MIN_LOG_LEVEL=2
( BH_ARCH=gap BH_SEQ=3 $PY run_fixed_extra.py; echo CHAIN DONE ) > log_fixed_seq3_gap.txt 2>&1 &
( BH_ARCH=lstm BH_SEQ=3 $PY run_fixed_extra.py; echo CHAIN DONE ) > log_fixed_seq3_lstm.txt 2>&1 &
( BH_ARCH=gap BH_SEQ=3 $PY run_groupcv.py; echo CHAIN DONE ) > log_cv_seq3_gap.txt 2>&1 &
( BH_ARCH=lstm BH_SEQ=3 $PY run_groupcv.py; echo CHAIN DONE ) > log_cv_seq3_lstm.txt 2>&1 &
sleep 5
$PY keep_awake.py &
KA=$!
wait %1 %2 %3 %4
kill $KA
echo ALL DONE
