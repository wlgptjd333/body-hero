import os
import re

targets = [
    ("scenes/home_hub.tscn", "res://assets/textures/ui/premium_home_bg.png"),
    ("scenes/main_menu.tscn", "res://assets/textures/ui/premium_home_bg.png"),
    ("scenes/ui/settings_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/shop_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/stats_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/game_records_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/boxing_upgrade_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/how_to_play_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/achievement_panel.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/stage_select.tscn", "res://assets/textures/ui/apocalyptic_bg.png"),
    ("scenes/ui/boss_buff_select.tscn", "res://assets/textures/ui/apocalyptic_bg.png")
]

for filepath, tex_path in targets:
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    out_lines = []
    
    # 1. Insert ext_resource
    ext_id = "bg_tex_123"
    ext_line = f'[ext_resource type="Texture2D" uid="uid://dummy_tex_123" path="{tex_path}" id="{ext_id}"]\n'
    
    # Find last ext_resource to insert after
    last_ext_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("[ext_resource "):
            last_ext_idx = i
            
    if last_ext_idx != -1:
        lines.insert(last_ext_idx + 1, ext_line)
    else:
        # insert after format=3 line
        lines.insert(1, ext_line)
        
    in_target_node = False
    
    for line in lines:
        # Check if we hit a node that is a ColorRect used as background
        if line.startswith("[node "):
            if 'type="ColorRect"' in line and ('name="Bg"' in line or 'name="Dim"' in line or 'name="ColorRect"' in line or 'name="DimOverlay"' in line):
                line = line.replace('type="ColorRect"', 'type="TextureRect"')
                in_target_node = True
                out_lines.append(line)
                
                # Add texture rect properties
                out_lines.append(f'texture = ExtResource("{ext_id}")\n')
                out_lines.append("expand_mode = 1\n")
                out_lines.append("stretch_mode = 6\n")
                out_lines.append("modulate = Color(0.3, 0.3, 0.35, 1)\n")
                continue
            else:
                in_target_node = False
                
        if in_target_node and line.startswith("color = "):
            continue # Remove color line
            
        out_lines.append(line)
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(out_lines)
        
    print(f"Updated {filepath}")
