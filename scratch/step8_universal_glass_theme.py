import os
import re

# 1. Update main_menu.tscn text
main_menu = "scenes/main_menu.tscn"
with open(main_menu, "r", encoding="utf-8") as f:
    mm_content = f.read()
mm_content = mm_content.replace('text = "업그레이드 (땀방울)"', 'text = "업그레이드 (스웨트)"')
with open(main_menu, "w", encoding="utf-8") as f:
    f.write(mm_content)


# 2. Update ui_theme_helper.gd with universal function and instructions
ui_helper = "scripts/ui/ui_theme_helper.gd"
with open(ui_helper, "r", encoding="utf-8") as f:
    helper_content = f.read()

universal_func = """

## =========================================================================
## 🛠️ [새로운 UI를 만들 때 테마를 통일하는 방법]
## =========================================================================
## 1. 팝업창(상점, 설정, 업그레이드 등)을 만들 때 최상단 노드의 `_ready()`에 다음 코드를 넣으세요:
##    UIThemeHelper.format_glass_popup(self)
## 
## 2. 이렇게 하면 `self` 아래에 있는 ColorRect(배경 딤 처리)와 Panel(팝업 몸체)을 
##    자동으로 사이버펑크 네온 글래스 테마로 예쁘게 바꿔줍니다.
## 
## 3. 내부 버튼들도 예쁘게 만드시려면 _ready()에서 다음을 호출하세요:
##    UIThemeHelper.style_button_primary(my_btn)   # 기본 버튼 (시안색 네온)
##    UIThemeHelper.style_button_danger(back_btn)  # 뒤로가기/취소 (빨간색 네온)
##    UIThemeHelper.style_button_secondary(sub_btn) # 투명한 서브 버튼
## =========================================================================

func format_glass_popup(root: Control) -> void:
	# 1. 반투명 배경 (ColorRect) 처리 - 너무 까맣지 않게 50% 투명도로
	for child in root.get_children():
		if child is ColorRect:
			child.color = Color(0.02, 0.0, 0.05, 0.6)
			break

	# 2. 메인 패널 (Panel/PanelContainer) 글래스 처리
	for child in root.get_children():
		if child is Panel:
			style_panel_glass(child)
			break
		elif child is PanelContainer:
			style_panel_container_glass(child)
			break
"""

if "func format_glass_popup" not in helper_content:
    helper_content += universal_func
    with open(ui_helper, "w", encoding="utf-8") as f:
        f.write(helper_content)


# 3. Inject format_glass_popup into all ui panel scripts
target_scripts = [
    "scripts/ui/settings_panel.gd",
    "scripts/ui/shop_panel.gd",
    "scripts/ui/boxing_upgrade_panel.gd",
    "scripts/ui/achievement_panel.gd",
    "scripts/ui/how_to_play_panel.gd",
    "scripts/ui/game_records_panel.gd",
    "scripts/ui/stats_panel.gd"
]

for script in target_scripts:
    if not os.path.exists(script):
        continue
    
    with open(script, "r", encoding="utf-8") as f:
        content = f.read()
    
    # If already injected, skip
    if "UIThemeHelper.format_glass_popup(self)" in content:
        continue
    
    # We want to inject it inside _ready()
    # Find _ready() -> void:
    match = re.search(r'func _ready\(\)(?:\s*->\s*void)?:\n', content)
    if match:
        injection = match.group(0) + "\tUIThemeHelper.format_glass_popup(self)\n"
        content = content[:match.start()] + injection + content[match.end():]
        
        # Also, if there's a back button or apply button, let's style them!
        if "_btn_back" in content and "UIThemeHelper.style_button_danger(_btn_back)" not in content:
            # add it right after format_glass_popup
            content = content.replace("UIThemeHelper.format_glass_popup(self)\n", "UIThemeHelper.format_glass_popup(self)\n\tif _btn_back:\n\t\tUIThemeHelper.style_button_danger(_btn_back)\n")
            
        if "_btn_apply" in content and "UIThemeHelper.style_button_primary(_btn_apply)" not in content:
            content = content.replace("UIThemeHelper.format_glass_popup(self)\n", "UIThemeHelper.format_glass_popup(self)\n\tif _btn_apply:\n\t\tUIThemeHelper.style_button_primary(_btn_apply)\n")

        with open(script, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Injected format_glass_popup into {script}")
    else:
        print(f"Could not find _ready in {script}")

print("UI formatting script executed successfully!")
