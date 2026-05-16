import os

targets = [
    "scenes/home_hub.tscn",
    "scenes/main_menu.tscn",
    "scenes/ui/settings_panel.tscn",
    "scenes/ui/shop_panel.tscn",
    "scenes/ui/stats_panel.tscn",
    "scenes/ui/game_records_panel.tscn",
    "scenes/ui/boxing_upgrade_panel.tscn",
    "scenes/ui/how_to_play_panel.tscn",
    "scenes/ui/achievement_panel.tscn",
    "scenes/ui/stage_select.tscn",
    "scenes/ui/boss_buff_select.tscn"
]

for filepath in targets:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Remove the dummy uid.
    content = content.replace(' uid="uid://dummy_tex_123"', '')
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Fixed {filepath}")
