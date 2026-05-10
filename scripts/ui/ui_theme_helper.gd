extends Node
## UI 테마 헬퍼 — 현대적인 다크 게임 스타일 공통 함수
## 사용: UIThemeHelper.style_button_primary(btn), UIThemeHelper.style_panel_glass(panel) 등

const C_BG := Color(0.051, 0.051, 0.071, 1.0)           # #0D0D12
const C_PANEL := Color(0.078, 0.078, 0.110, 0.82)        # glass panel bg
const C_PANEL_BORDER := Color(1.0, 1.0, 1.0, 0.06)       # subtle border
const C_ACCENT := Color(0.306, 0.804, 0.769, 1.0)        # #4ECDC4 청록
const C_ACCENT_DARK := Color(0.18, 0.55, 0.52, 1.0)
const C_TEXT_PRIMARY := Color(0.941, 0.941, 0.961, 1.0)  # #F0F0F5
const C_TEXT_SECONDARY := Color(0.541, 0.541, 0.604, 1.0) # #8A8A9A
const C_TEXT_MUTED := Color(0.42, 0.42, 0.48, 1.0)
const C_SUCCESS := Color(0.42, 0.796, 0.467, 1.0)        # #6BCB77
const C_DANGER := Color(1.0, 0.42, 0.42, 1.0)            # #FF6B6B
const C_WARN := Color(1.0, 0.78, 0.35, 1.0)


func _sb_flat(bg: Color, border: Color, border_w: int, radius: int, shadow_sz: int = 0, shadow_off: Vector2 = Vector2.ZERO) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.border_width_left = border_w
	sb.border_width_top = border_w
	sb.border_width_right = border_w
	sb.border_width_bottom = border_w
	sb.corner_radius_top_left = radius
	sb.corner_radius_top_right = radius
	sb.corner_radius_bottom_right = radius
	sb.corner_radius_bottom_left = radius
	if shadow_sz > 0:
		sb.shadow_color = Color(0, 0, 0, 0.45)
		sb.shadow_size = shadow_sz
		sb.shadow_offset = shadow_off
	return sb


# ── 버튼 스타일 ──

func style_button_primary(btn: Button) -> void:
	var normal := _sb_flat(Color(0.16, 0.55, 0.52, 0.25), C_ACCENT, 1, 14, 8, Vector2(0, 3))
	normal.content_margin_left = 20
	normal.content_margin_top = 10
	normal.content_margin_right = 20
	normal.content_margin_bottom = 10
	var hover := _sb_flat(Color(0.20, 0.60, 0.57, 0.40), Color(0.45, 0.90, 0.85, 0.8), 1, 14, 12, Vector2(0, 4))
	hover.content_margin_left = 20
	hover.content_margin_top = 10
	hover.content_margin_right = 20
	hover.content_margin_bottom = 10
	var pressed := _sb_flat(Color(0.12, 0.42, 0.40, 0.50), C_ACCENT_DARK, 1, 14, 4, Vector2(0, 2))
	pressed.content_margin_left = 20
	pressed.content_margin_top = 10
	pressed.content_margin_right = 20
	pressed.content_margin_bottom = 10
	var disabled := _sb_flat(Color(0.08, 0.08, 0.10, 0.5), Color(0.3, 0.3, 0.35, 0.3), 1, 14)
	disabled.content_margin_left = 20
	disabled.content_margin_top = 10
	disabled.content_margin_right = 20
	disabled.content_margin_bottom = 10
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("disabled", disabled)
	btn.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	btn.add_theme_color_override("font_hover_color", Color(0.9, 1.0, 0.98, 1.0))
	btn.add_theme_color_override("font_pressed_color", C_TEXT_PRIMARY)
	btn.add_theme_font_size_override("font_size", 15)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_secondary(btn: Button) -> void:
	var normal := _sb_flat(Color(1.0, 1.0, 1.0, 0.05), Color(1.0, 1.0, 1.0, 0.10), 1, 12, 6, Vector2(0, 2))
	normal.content_margin_left = 16
	normal.content_margin_top = 8
	normal.content_margin_right = 16
	normal.content_margin_bottom = 8
	var hover := _sb_flat(Color(1.0, 1.0, 1.0, 0.10), Color(1.0, 1.0, 1.0, 0.20), 1, 12, 10, Vector2(0, 3))
	hover.content_margin_left = 16
	hover.content_margin_top = 8
	hover.content_margin_right = 16
	hover.content_margin_bottom = 8
	var pressed := _sb_flat(Color(1.0, 1.0, 1.0, 0.03), Color(1.0, 1.0, 1.0, 0.08), 1, 12, 3, Vector2(0, 1))
	pressed.content_margin_left = 16
	pressed.content_margin_top = 8
	pressed.content_margin_right = 16
	pressed.content_margin_bottom = 8
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	btn.add_theme_color_override("font_hover_color", C_TEXT_PRIMARY)
	btn.add_theme_font_size_override("font_size", 14)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_danger(btn: Button) -> void:
	var normal := _sb_flat(Color(0.85, 0.25, 0.25, 0.20), C_DANGER, 1, 12, 6, Vector2(0, 2))
	normal.content_margin_left = 16
	normal.content_margin_top = 8
	normal.content_margin_right = 16
	normal.content_margin_bottom = 8
	var hover := _sb_flat(Color(0.90, 0.30, 0.30, 0.35), Color(1.0, 0.50, 0.50, 0.8), 1, 12, 10, Vector2(0, 3))
	hover.content_margin_left = 16
	hover.content_margin_top = 8
	hover.content_margin_right = 16
	hover.content_margin_bottom = 8
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_color_override("font_color", C_DANGER)
	btn.add_theme_color_override("font_hover_color", Color(1.0, 0.60, 0.60, 1.0))
	btn.add_theme_font_size_override("font_size", 14)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


# ── 패널 / 컨테이너 ──

func style_panel_glass(panel: Panel) -> void:
	var sb := _sb_flat(C_PANEL, C_PANEL_BORDER, 1, 20, 20, Vector2(0, 6))
	sb.content_margin_left = 20
	sb.content_margin_top = 16
	sb.content_margin_right = 20
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)


func style_panel_container_glass(pc: PanelContainer) -> void:
	var sb := _sb_flat(C_PANEL, C_PANEL_BORDER, 1, 20, 20, Vector2(0, 6))
	sb.content_margin_left = 20
	sb.content_margin_top = 16
	sb.content_margin_right = 20
	sb.content_margin_bottom = 16
	pc.add_theme_stylebox_override("panel", sb)


# ── 라벨 ──

func style_label_title(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 26)
	lbl.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_label_section(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", C_ACCENT)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT


func style_label_body(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 14)
	lbl.add_theme_color_override("font_color", C_TEXT_SECONDARY)


func style_label_caption(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", C_TEXT_MUTED)


# ── ProgressBar ──

func style_progress_bar(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(1.0, 1.0, 1.0, 0.06), Color(1.0, 1.0, 1.0, 0.04), 0, 6)
	var fill := _sb_flat(C_ACCENT, C_ACCENT, 0, 6)
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


# ── ScrollContainer / 배경 ──

func apply_dark_bg(node: Control) -> void:
	var cr := ColorRect.new()
	cr.color = C_BG
	cr.anchors_preset = Control.PRESET_FULL_RECT
	node.add_child(cr)
	node.move_child(cr, 0)
