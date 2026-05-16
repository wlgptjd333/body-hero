extends Node
## UI 테마 헬퍼 — 프리미엄 사이버펑크 글래스 (Premium Cyberpunk Glass)
## 지저분한 철판 텍스처를 폐기하고 코드로 투명도와 네온 글로우를 구현합니다.

const C_ACCENT := Color(0.0, 0.9, 1.0, 1.0)              # #00E5FF Neon Cyan
const C_ACCENT_DARK := Color(0.0, 0.4, 0.5, 1.0)
const C_DANGER := Color(1.0, 0.0, 0.33, 1.0)             # #FF0055 Neon Red/Pink
const C_WARN := Color(1.0, 0.85, 0.0, 1.0)               # #FFD700 Neon Yellow
const C_SUCCESS := Color(0.0, 1.0, 0.5, 1.0)             # #00FF80 Neon Green

const C_TEXT_PRIMARY := Color(1.0, 1.0, 1.0, 1.0)        # Pure White
const C_TEXT_SECONDARY := Color(0.7, 0.8, 0.9, 1.0)      # Ice Blue Gray
const C_TEXT_MUTED := Color(0.4, 0.5, 0.6, 1.0)          # Dark Blue Gray

const C_BG := Color(0.05, 0.05, 0.07, 1.0)               # 기본 폴백 어두운 배경
const C_PANEL := Color(0.0, 0.0, 0.05, 0.45)           # 투명하고 맑은 유리 (Glass)
const C_PANEL_BORDER := Color(0.0, 0.9, 1.0, 0.4)        # 패널 테두리에 옅은 시안 빛


func _sb_flat(bg: Color, border: Color, border_l: int, border_t: int, border_r: int, border_b: int, shadow_sz: int = 0, shadow_color: Color = Color(0,0,0,0.45)) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.border_width_left = border_l
	sb.border_width_top = border_t
	sb.border_width_right = border_r
	sb.border_width_bottom = border_b
	# 사이버펑크 스타일: 전체적으로 각진 느낌을 살짝 줄이고 부드럽게 라운딩
	sb.corner_radius_top_left = 8
	sb.corner_radius_top_right = 8
	sb.corner_radius_bottom_right = 8
	sb.corner_radius_bottom_left = 8
	if shadow_sz > 0:
		sb.shadow_color = shadow_color
		sb.shadow_size = shadow_sz
		sb.shadow_offset = Vector2.ZERO
	return sb


# ── 버튼 스타일 ──

func style_button_primary(btn: Button) -> void:
	# 투명한 유리 질감의 버튼, 좌측에 시안색 얇은 선 포인트
	var normal := _sb_flat(Color(0.0, 0.05, 0.1, 0.4), Color(0.0, 0.4, 0.5, 0.6), 4, 1, 1, 1, 5)
	normal.content_margin_left = 24
	normal.content_margin_top = 12
	normal.content_margin_right = 20
	normal.content_margin_bottom = 12
	
	# Hover 시 전체적으로 시안색 네온 글로우 발광
	var hover := _sb_flat(Color(0.1, 0.2, 0.3, 0.8), C_ACCENT, 4, 1, 1, 1, 20, Color(0.0, 0.9, 1.0, 0.6))
	hover.content_margin_left = 24
	hover.content_margin_top = 12
	hover.content_margin_right = 20
	hover.content_margin_bottom = 12
	
	# Pressed 시 네온 레드 핑크로 변경되며 타격감 부여
	var pressed := _sb_flat(Color(0.2, 0.0, 0.05, 0.9), C_DANGER, 4, 1, 1, 1, 10, Color(1.0, 0.0, 0.33, 0.8))
	pressed.content_margin_left = 24
	pressed.content_margin_top = 12
	pressed.content_margin_right = 20
	pressed.content_margin_bottom = 12
	
	var disabled := _sb_flat(Color(0.05, 0.05, 0.08, 0.4), Color(0.2, 0.2, 0.3, 0.3), 4, 1, 1, 1)
	disabled.content_margin_left = 24
	disabled.content_margin_top = 12
	disabled.content_margin_right = 20
	disabled.content_margin_bottom = 12
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("disabled", disabled)
	
	btn.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	btn.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_color_override("font_pressed_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_font_size_override("font_size", 16)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_secondary(btn: Button) -> void:
	var normal := _sb_flat(Color(0.0, 0.0, 0.0, 0.2), Color(0.3, 0.3, 0.4, 0.6), 1, 1, 1, 1, 2)
	normal.content_margin_left = 18
	normal.content_margin_top = 10
	normal.content_margin_right = 18
	normal.content_margin_bottom = 10
	
	var hover := _sb_flat(Color(0.1, 0.1, 0.2, 0.6), C_TEXT_SECONDARY, 1, 1, 1, 1, 10, Color(0.7, 0.8, 0.9, 0.3))
	hover.content_margin_left = 18
	hover.content_margin_top = 10
	hover.content_margin_right = 18
	hover.content_margin_bottom = 10
	
	var pressed := _sb_flat(Color(0.0, 0.0, 0.0, 0.8), C_TEXT_PRIMARY, 1, 1, 1, 1)
	pressed.content_margin_left = 18
	pressed.content_margin_top = 10
	pressed.content_margin_right = 18
	pressed.content_margin_bottom = 10
	
	var disabled := _sb_flat(Color(0.05, 0.05, 0.08, 0.4), Color(0.2, 0.2, 0.3, 0.3), 1, 1, 1, 1)
	disabled.content_margin_left = 18
	disabled.content_margin_top = 10
	disabled.content_margin_right = 18
	disabled.content_margin_bottom = 10
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("disabled", disabled)
	
	btn.add_theme_color_override("font_color", C_TEXT_SECONDARY)
	btn.add_theme_color_override("font_hover_color", C_TEXT_PRIMARY)
	btn.add_theme_font_size_override("font_size", 14)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_button_danger(btn: Button) -> void:
	var normal := _sb_flat(Color(0.15, 0.0, 0.05, 0.6), Color(0.5, 0.0, 0.1, 0.5), 4, 1, 1, 1, 5)
	normal.content_margin_left = 24
	normal.content_margin_top = 12
	normal.content_margin_right = 20
	normal.content_margin_bottom = 12
	
	var hover := _sb_flat(Color(0.3, 0.0, 0.1, 0.8), C_DANGER, 4, 1, 1, 1, 20, Color(1.0, 0.0, 0.33, 0.6))
	hover.content_margin_left = 24
	hover.content_margin_top = 12
	hover.content_margin_right = 20
	hover.content_margin_bottom = 12
	
	var pressed := _sb_flat(Color(0.5, 0.0, 0.1, 0.9), C_TEXT_PRIMARY, 4, 1, 1, 1, 10, C_DANGER)
	pressed.content_margin_left = 24
	pressed.content_margin_top = 12
	pressed.content_margin_right = 20
	pressed.content_margin_bottom = 12
	
	var disabled := _sb_flat(Color(0.1, 0.0, 0.0, 0.4), Color(0.3, 0.1, 0.1, 0.3), 4, 1, 1, 1)
	disabled.content_margin_left = 24
	disabled.content_margin_top = 12
	disabled.content_margin_right = 20
	disabled.content_margin_bottom = 12
	
	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("disabled", disabled)
	
	btn.add_theme_color_override("font_color", C_DANGER)
	btn.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_font_size_override("font_size", 16)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


# ── 패널 / 컨테이너 ──

func style_panel_glass(panel: Panel) -> void:
	# 배경이 예쁘게 비치는 반투명 네온 글래스 패널
	var sb := _sb_flat(C_PANEL, C_PANEL_BORDER, 1, 1, 1, 1, 15, Color(0, 0, 0, 0.6))
	sb.content_margin_left = 32
	sb.content_margin_top = 32
	sb.content_margin_right = 32
	sb.content_margin_bottom = 32
	panel.add_theme_stylebox_override("panel", sb)


func style_panel_container_glass(pc: PanelContainer) -> void:
	var sb := _sb_flat(C_PANEL, C_PANEL_BORDER, 1, 1, 1, 1, 15, Color(0, 0, 0, 0.6))
	sb.content_margin_left = 32
	sb.content_margin_top = 32
	sb.content_margin_right = 32
	sb.content_margin_bottom = 32
	pc.add_theme_stylebox_override("panel", sb)


# ── 라벨 ──

func style_label_title(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 28)
	lbl.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	lbl.add_theme_color_override("font_shadow_color", Color(0.0, 0.9, 1.0, 0.5))
	lbl.add_theme_constant_override("shadow_offset_x", 1)
	lbl.add_theme_constant_override("shadow_offset_y", 1)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func style_label_section(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 18)
	lbl.add_theme_color_override("font_color", C_ACCENT)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT


func style_label_body(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 15)
	lbl.add_theme_color_override("font_color", C_TEXT_SECONDARY)


func style_label_caption(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", C_TEXT_MUTED)


# ── ProgressBar ──

func style_progress_bar(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.0, 0.0, 0.0, 0.5), Color(0.2, 0.2, 0.3, 0.4), 1, 1, 1, 1)
	var fill := _sb_flat(C_ACCENT, C_ACCENT_DARK, 0, 0, 0, 0, 10, Color(0.0, 0.9, 1.0, 0.5))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


func style_progress_bar_hp(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.05, 0.0, 0.0, 0.6), Color(0.3, 0.0, 0.1, 0.4), 1, 1, 1, 1)
	var fill := _sb_flat(C_DANGER, Color(0.6, 0.0, 0.2, 1.0), 0, 0, 0, 0, 15, Color(1.0, 0.0, 0.33, 0.6))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


func style_progress_bar_stamina(bar: ProgressBar) -> void:
	var bg := _sb_flat(Color(0.05, 0.05, 0.0, 0.6), Color(0.3, 0.3, 0.1, 0.4), 1, 1, 1, 1)
	var fill := _sb_flat(C_WARN, Color(0.6, 0.5, 0.0, 1.0), 0, 0, 0, 0, 10, Color(1.0, 0.85, 0.0, 0.5))
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


# ── ScrollContainer / 배경 ──

func apply_dark_bg(_node: Control) -> void:
	# 이 메서드는 더 이상 배경 이미지를 런타임에 그리지 않습니다. (tscn 내부에 직접 연결됨)
	pass


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
	var rects: Array[Node] = root.find_children("*", "ColorRect", true, false)
	for r in rects:
		if r is ColorRect:
			r.color = Color(0.02, 0.0, 0.05, 0.6)
			break

	# 2. 메인 패널 (Panel/PanelContainer) 글래스 처리
	var panels: Array[Node] = root.find_children("*", "Panel", true, false)
	for p in panels:
		if p is Panel:
			style_panel_glass(p)
			break
	
	var panel_containers: Array[Node] = root.find_children("*", "PanelContainer", true, false)
	for pc in panel_containers:
		if pc is PanelContainer:
			style_panel_container_glass(pc)
			break
