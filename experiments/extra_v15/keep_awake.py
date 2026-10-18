# 학습이 끝날 때까지(최대 8시간) 유휴 절전만 막는다. 시스템 설정은 바꾸지 않는다.
import ctypes, os, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
t0 = time.time()
try:
    while time.time() - t0 < 8 * 3600:
        logs = glob.glob(os.path.join(HERE, "log_*.txt"))
        if logs and all("CHAIN DONE" in open(p, encoding="utf8", errors="ignore").read()[-3000:] for p in logs):
            break
        time.sleep(60)
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
