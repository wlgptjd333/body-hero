import pyautogui
import keyboard
import time

print("=" * 40)
print("  간단 매크로 프로그램")
print("=" * 40)
print("[F8] 키: b → 마우스 클릭 → 스페이스바 입력")
print("[ESC] 키: 프로그램 종료")
print("=" * 40)


def run_macro():
    """b키 -> 마우스 클릭 -> 스페이스바 순서로 입력"""
    print("▶ 매크로 실행 중...")
    
    # 1. 'b' 키 입력
    pyautogui.press('b')
    time.sleep(0.1)
    
    # 2. 현재 마우스 위치에서 클릭
    pyautogui.click()
    time.sleep(0.1)
    
    # 3. 스페이스바 입력
    pyautogui.press('space')
    
    print("✓ 매크로 완료")


# F8 키를 누른면 매크로 실행
keyboard.add_hotkey('f8', run_macro)

# ESC 키를 누르기 전까지 대기
keyboard.wait('esc')

print("\n프로그램을 종료합니다.")
