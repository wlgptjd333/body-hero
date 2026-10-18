# 학습이 끝날 때까지(최대 8시간) 유휴 절전만 막는다. 시스템 설정은 바꾸지 않으며, 이 프로세스가 끝나면 원래대로 돌아간다.
import ctypes, os, time
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = ["log_gap.txt", "log_lstm.txt", "log_mlp.txt"]
ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
t0 = time.time()
try:
    while time.time() - t0 < 8 * 3600:
        done = 0
        for f in LOGS:
            p = os.path.join(HERE, f)
            if os.path.exists(p) and "ALL RUNS DONE" in open(p, encoding="utf8", errors="ignore").read()[-2000:]:
                done += 1
        if done == len(LOGS):
            break
        time.sleep(60)
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
print("keep-awake released")
