import re

new_content = """extends Node
## UI 테마 헬퍼 — 아포칼립스 텍스처 스타일 공통 함수
## 사용: UIThemeHelper.style_button_primary(btn), UIThemeHelper.style_panel_glass(panel) 등

const C_ACCENT := Color(1.0, 0.341, 0.133, 1.0)          # #FF5722 Warning Orange
const C_TEXT_PRIMARY := Color(0.95, 0.95, 0.92, 1.0)     # Warm Off-White
const C_TEXT_SECONDARY := Color(0.65, 0.65, 0.60, 1.0)   # Gritty Gray
const C_TEXT_MUTED := Color(0.45, 0.45, 0.42, 1.0)       # Dark Gray
const C_SUCCESS := Color(0.70, 1.0, 0.02, 1.0)           # #B2FF05 Toxic Green
const C_DANGER := Color(1.0, 0.0, 0.235, 1.0)            # #FF003C Blood Red
const C_WARN := Color(1.0, 0.85, 0.0, 1.0)               # Radioactive Yellow (Stamina)
const C_BG := Color(0.071, 0.071, 0.082, 1.0) # Fallback

# 텍스처 프리로드
var tex_bg: Texture2D = preload("res://assets/textures/ui/apocalyptic_bg.png")
var tex_panel: Texture2D = preload("res://assets/textures/ui/apocalyptic_panel.png")
var tex_button: Texture2D = preload("res://assets/textures/ui/apocalyptic_button.png")

func _sb_tex(tex: Texture2D, m_left: float, m_top: float, m_right: float, m_bottom: float, mod: Color = Color.WHITE) -> StyleBoxTexture:
	var sb := StyleBoxTexture.new()
	sb.texture = tex
	sb.texture_margin_left = m_left
	sb.texture_margin_top = m_top
	sb.texture_margin_right = m_right
	sb.texture_margin_bottom = m_bottom
	sb.modulate_color = mod
	return sb

func _sb_flat(bg: Color, border: Color, border_l: int, border_t: int, border_r: int, border_b: int, shadow_sz: int = 0, shadow_color: Color = Color(0,0,0,0.45)) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.border_width_left = border_l
	sb.border_width_top = border_t
	sb.border_width_right = border_r
	sb.border_width_bottom = border_b
	sb.corner_radius_top_left = 0
	sb.corner_radius_top_right = 0
	sb.corner_radius_bottom_right = 0
	sb.corner_radius_bottom_left = 0
	if shadow_sz > 0:
		sb.shadow_color = shadow_color
		sb.shadow_size = shadow_sz
		sb.shadow_offset = Vector2.ZERO
	return sb


# ── 버튼 스타일 ──

func style_button_primary(btn: Button) -> void:
	# 9-slice 마진을 충분히 주어 텍스처 형태 유지
	var normal := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.8, 0.8, 0.8, 1.0))
	normal.content_margin_left = 24
	normal.content_margin_top = 16
	normal.content_margin_right = 24
	normal.content_margin_bottom = 16
	
	var hover := _sb_tex(tex_button, 40, 40, 40, 40, Color(1.5, 0.8, 0.5, 1.0)) # 오렌지빛 발광
	hover.content_margin_left = 24
	hover.content_margin_top = 16
	hover.content_margin_right = 24
	hover.content_margin_bottom = 16
	
	var pressed := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.4, 0.3, 0.3, 1.0))
	pressed.content_margin_left = 24
	pressed.content_margin_top = 16
	pressed.content_margin_right = 24
	pressed.content_margin_bottom = 16
	
	var disabled := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.2, 0.2, 0.2, 0.6))
	disabled.content_margin_left = 24
	disabled.content_margin_top = 16
	disabled.content_margin_right = 24
	disabled.content_margin_bottom = 16
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("disabled", disabled)
	
	btn.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	btn.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_color_override("font_pressed_color", C_ACCENT)
	btn.add_theme_font_size_override("font_size", 18)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_secondary(btn: Button) -> void:
	var normal := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.4, 0.4, 0.4, 0.8))
	normal.content_margin_left = 18
	normal.content_margin_top = 10
	normal.content_margin_right = 18
	normal.content_margin_bottom = 10
	
	var hover := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.8, 0.8, 0.8, 1.0))
	hover.content_margin_left = 18
	hover.content_margin_top = 10
	hover.content_margin_right = 18
	hover.content_margin_bottom = 10
	
	var pressed := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.2, 0.2, 0.2, 1.0))
	pressed.content_margin_left = 18
	pressed.content_margin_top = 10
	pressed.content_margin_right = 18
	pressed.content_margin_bottom = 10
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	
	btn.add_theme_color_override("font_color", C_TEXT_SECONDARY)
	btn.add_theme_color_override("font_hover_color", C_TEXT_PRIMARY)
	btn.add_theme_font_size_override("font_size", 14)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_danger(btn: Button) -> void:
	var normal := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.6, 0.2, 0.2, 1.0))
	normal.content_margin_left = 24
	normal.content_margin_top = 12
	normal.content_margin_right = 20
	normal.content_margin_bottom = 12
	
	var hover := _sb_tex(tex_button, 40, 40, 40, 40, Color(1.5, 0.5, 0.5, 1.0))
	hover.content_margin_left = 24
	hover.content_margin_top = 12
	hover.content_margin_right = 20
	hover.content_margin_bottom = 12
	
	var pressed := _sb_tex(tex_button, 40, 40, 40, 40, Color(0.3, 0.1, 0.1, 1.0))
	pressed.content_margin_left = 24
	pressed.content_margin_top = 12
	pressed.content_margin_right = 20
	pressed.content_margin_bottom = 12
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	
	btn.add_theme_color_override("font_color", C_DANGER)
	btn.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_font_size_override("font_size", 16)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


# ── 패널 / 컨테이너 ──

func style_panel_glass(panel: Panel) -> void:
	# 텍스처 패널 적용
	var sb := _sb_tex(tex_panel, 60, 60, 60, 60, Color(0.9, 0.9, 0.9, 0.9))
	sb.content_margin_left = 32
	sb.content_margin_top = 32
	sb.content_margin_right = 32
	sb.content_margin_bottom = 32
	panel.add_theme_stylebox_override("panel", sb)


func style_panel_container_glass(pc: PanelContainer) -> void:
	var sb := _sb_tex(tex_panel, 60, 60, 60, 60, Color(0.9, 0.9, 0.9, 0.9))
	sb.content_margin_left = 32
	sb.content_margin_top = 32
	sb.content_margin_right = 32
	sb.content_margin_bottom = 32
	pc.add_theme_stylebox_override("panel", sb)


# ── 라벨 ──

func style_label_title(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 34)
	lbl.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	lbl.add_theme_color_override("font_shadow_color", C_ACCENT * 0.7)
	lbl.add_theme_constant_override("shadow_offset_x", 3)
	lbl.add_theme_constant_override("shadow_offset_y", 3)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_label_section(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 20)
	lbl.add_theme_color_override("font_color", C_ACCENT)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT


func style_label_body(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", C_TEXT_SECONDARY)


func style_label_caption(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", C_TEXT_MUTED)


# ── ProgressBar ──

func style_progress_bar(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.05, 0.05, 0.05, 0.8), Color(0.2, 0.2, 0.2, 0.5), 1, 1, 1, 1)
	var fill := _sb_flat(C_ACCENT, C_ACCENT, 0, 0, 0, 0, 10, Color(1.0, 0.34, 0.13, 0.6))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


func style_progress_bar_hp(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.05, 0.0, 0.0, 0.8), Color(0.3, 0.0, 0.0, 0.5), 2, 2, 2, 2)
	var fill := _sb_flat(C_DANGER, C_DANGER, 0, 0, 0, 0, 15, Color(1.0, 0.0, 0.23, 0.8))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


func style_progress_bar_stamina(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.05, 0.05, 0.0, 0.8), Color(0.3, 0.3, 0.0, 0.5), 1, 1, 1, 1)
	var fill := _sb_flat(C_WARN, C_WARN, 0, 0, 0, 0, 12, Color(1.0, 0.85, 0.0, 0.6))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


# ── ScrollContainer / 배경 ──

func apply_dark_bg(node: Control) -> void:
	# 기존 ColorRect 대신 TextureRect를 사용하여 분위기 있는 아포칼립스 벙커 배경 삽입
	var tr := TextureRect.new()
	tr.texture = tex_bg
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVER
	tr.anchors_preset = Control.PRESET_FULL_RECT
	
	# 이미지가 너무 밝으면 UI가 가려지므로 약간 어둡게 모듈레이트
	tr.modulate = Color(0.3, 0.3, 0.35, 1.0)
	
	node.add_child(tr)
	node.move_child(tr, 0)
"""

with open("scripts/ui/ui_theme_helper.gd", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Updated ui_theme_helper.gd successfully.")
