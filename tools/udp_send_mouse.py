"""
UDP로 마우스 좌표를 Godot에 전송하는 테스트 스크립트.
실행 후 Godot에서 게임을 켜두면 글러브가 마우스 위치를 따라갑니다.

데이터 형식: "left_x,left_y,right_x,right_y" (0~1 정규화)
- 지금은 왼손/오른손 모두 마우스 위치로 보냄 (테스트용)
- MediaPipe 연동 시 여기서 left/right 손목 좌표를 넣으면 됨.

필요: pip install pyautogui  (또는 마우스 좌표만 쓰면 기본 라이브러리만으로 가능)
"""
import socket
import time

# Godot Main.gd의 포트와 동일
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 4242

# 윈도우에서 마우스 위치 얻기 (표준 라이브러리만 사용)
try:
    import ctypes
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    user32 = ctypes.windll.user32

    def get_mouse_pos():
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def get_screen_size():
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return w, h
except Exception:
    # Windows 아님 또는 실패 시
    try:
        import pyautogui
        def get_mouse_pos():
            return pyautogui.position()
        def get_screen_size():
            return pyautogui.size()
    except ImportError:
        print("Windows가 아니면: pip install pyautogui 후 다시 실행하세요.")
        exit(1)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    screen_w, screen_h = get_screen_size()
    print(f"화면 크기: {screen_w} x {screen_h}")
    print("마우스를 움직이면 Godot 글러브가 따라갑니다. 종료: Ctrl+C")
    print("Godot에서 게임을 실행한 뒤 이 스크립트를 실행하세요.\n")

    while True:
        try:
            x, y = get_mouse_pos()
            # 0~1 정규화 (Godot Main.gd에서 _normalized_coords = true 일 때)
            nx = x / max(screen_w, 1)
            ny = y / max(screen_h, 1)
            # 왼손/오른손 모두 마우스 위치 (테스트용)
            msg = f"{nx:.4f},{ny:.4f},{nx:.4f},{ny:.4f}"
            sock.sendto(msg.encode("utf-8"), (GODOT_HOST, GODOT_PORT))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("전송 오류:", e)
        time.sleep(1 / 30)  # 약 30 FPS

    sock.close()
    print("종료.")


if __name__ == "__main__":
    main()
