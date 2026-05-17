extends Control
## 스테이지 선택 화면

const SCENE_MAIN_MENU: String = "res://scenes/main_menu.tscn"
const STAGES_PER_PAGE: int = 3

@onready var _bg: TextureRect = $Bg
@onready var _back_btn: Button = $BackBtn
@onready var _start_btn: Button = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/StartBtn
@onready var _stage_grid: VBoxContainer = $MainArea/HBoxContainer/StageCol/StageGrid
@onready var _btn_prev: Button = $MainArea/HBoxContainer/StageCol/PageRow/BtnPrev
@onready var _btn_next: Button = $MainArea/HBoxContainer/StageCol/PageRow/BtnNext
@onready var _page_label: Label = $MainArea/HBoxContainer/StageCol/PageRow/PageLabel
@onready var _carousel_stack: Control = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/CarouselStack
@onready var _info_panel: PanelContainer = $MainArea/HBoxContainer/InfoPanel
@onready var _info_monster_name: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/MonsterName
@onready var _info_desc: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/DescLabel
@onready var _info_stars: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/StarsLabel
@onready var _info_best_time: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/BestTimeLabel
@onready var _info_best_combo: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/BestComboLabel
@onready var _info_least_dmg: Label = $MainArea/HBoxContainer/InfoPanel/InfoScroll/InfoVBox/LeastDmgLabel

var _selected_stage_id: String = ""
var _page_index: int = 0
var _card_buttons: Array[Button] = []
var _carousel_rects: Array[TextureRect] = []


func _ready() -> void:
	_beautify()
	_build_carousel()
	_populate_current_page()
	_update_pagination_ui()

	if _back_btn:
		_back_btn.pressed.connect(_on_back)
	if _btn_prev:
		_btn_prev.pressed.connect(_on_prev_page)
	if _btn_next:
		_btn_next.pressed.connect(_on_next_page)
	if _start_btn:
		_start_btn.pressed.connect(_on_start)
		_start_btn.disabled = true

	var default_id: String = GameState.get_last_played_stage_id()
	var found: bool = false
	for def: Dictionary in GameState.get_stage_defs():
		if str(def.get("id", "")) == default_id:
			var idx: int = _find_stage_index(default_id)
			if idx >= 0:
				_page_index = int(float(idx) / float(STAGES_PER_PAGE))
				_populate_current_page()
				_update_pagination_ui()
			_on_stage_selected(default_id)
			found = true
			break
	if not found:
		var defs: Array[Dictionary] = GameState.get_stage_defs()
		if defs.size() > 0:
			_on_stage_selected(str(defs[0].get("id", "")))


func _beautify() -> void:
	UIThemeHelper.style_label_title($Title)
	if _back_btn:
		_back_btn.add_theme_font_size_override("font_size", 16)
		_back_btn.add_theme_color_override("font_color", UIThemeHelper.C_ACCENT)
	if _start_btn:
		UIThemeHelper.style_button_primary(_start_btn)
	if _info_panel:
		UIThemeHelper.style_panel_container_glass(_info_panel)
	if _info_monster_name:
		UIThemeHelper.style_label_title(_info_monster_name)
		_info_monster_name.add_theme_font_size_override("font_size", 22)
	for na: Button in [_btn_prev, _btn_next]:
		if na:
			na.add_theme_font_size_override("font_size", 20)
			na.add_theme_color_override("font_color", UIThemeHelper.C_ACCENT)


func _populate_current_page() -> void:
	for child: Node in _stage_grid.get_children():
		child.queue_free()
	_card_buttons.clear()

	var defs: Array[Dictionary] = GameState.get_stage_defs()
	var start: int = _page_index * STAGES_PER_PAGE
	var end: int = mini(start + STAGES_PER_PAGE, defs.size())

	for i: int in range(start, end):
		var def: Dictionary = defs[i]
		var sid: String = str(def.get("id", ""))
		var sname: String = str(def.get("name", "Stage %d" % (i + 1)))
		var mname: String = str(def.get("monster_name", sname))

		var card := Button.new()
		card.custom_minimum_size = Vector2(200, 68)
		card.size_flags_horizontal = Control.SIZE_FILL
		card.text = "%s\n%s" % [sname, mname]
		card.add_theme_font_size_override("font_size", 15)
		card.alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.pressed.connect(_on_stage_selected.bind(sid))
		_stage_grid.add_child(card)
		_card_buttons.append(card)


func _update_pagination_ui() -> void:
	var defs: Array[Dictionary] = GameState.get_stage_defs()
	var total_pages: int = maxi(1, ceili(float(defs.size()) / STAGES_PER_PAGE))
	if _btn_prev:
		_btn_prev.visible = _page_index > 0
	if _btn_next:
		_btn_next.visible = _page_index < total_pages - 1
	if _page_label:
		if total_pages > 1:
			_page_label.text = "%d / %d" % [_page_index + 1, total_pages]
			_page_label.visible = true
		else:
			_page_label.visible = false


func _on_prev_page() -> void:
	if _page_index > 0:
		_page_index -= 1
		_populate_current_page()
		_update_pagination_ui()
		_apply_card_styles()


func _on_next_page() -> void:
	var defs: Array[Dictionary] = GameState.get_stage_defs()
	var total_pages: int = maxi(1, ceili(float(defs.size()) / STAGES_PER_PAGE))
	if _page_index < total_pages - 1:
		_page_index += 1
		_populate_current_page()
		_update_pagination_ui()
		_apply_card_styles()


func _on_stage_selected(stage_id: String) -> void:
	_selected_stage_id = stage_id
	GameState.set_last_played_stage_id(stage_id)

	var def: Dictionary = GameState.get_stage_def(stage_id)
	if def.is_empty():
		return

	_set_bg(str(def.get("bg_image", "")))

	var idx: int = _find_stage_index(stage_id)
	_animate_carousel(idx)

	if _info_monster_name:
		_info_monster_name.text = str(def.get("monster_name", def.get("name", stage_id)))
	if _info_desc:
		_info_desc.text = str(def.get("description", ""))
	if _info_stars:
		_info_stars.text = _format_stars(stage_id)
		_apply_stars_color(_info_stars, stage_id)

	var record: Dictionary = GameState.get_stage_record(stage_id)
	if _info_best_time:
		var bt: float = float(record.get("best_time", -1.0))
		_info_best_time.text = "최고 기록: %s" % (GameState.format_stage_clear_time(bt) if bt > 0.0 else "—")
	if _info_best_combo:
		_info_best_combo.text = "최고 콤보: %d" % int(record.get("best_combo", 0))
	if _info_least_dmg:
		var ld: float = float(record.get("least_dmg", -1.0))
		_info_least_dmg.text = "최소 피해: %s" % ("%.0f" % ld if ld >= 0.0 else "—")

	if _start_btn:
		_start_btn.disabled = false

	_apply_card_styles()


func _apply_card_styles() -> void:
	var defs: Array[Dictionary] = GameState.get_stage_defs()
	var start: int = _page_index * STAGES_PER_PAGE
	for j: int in range(_card_buttons.size()):
		var btn: Button = _card_buttons[j]
		var def_idx: int = start + j
		if def_idx < defs.size() and str(defs[def_idx].get("id", "")) == _selected_stage_id:
			UIThemeHelper.style_button_primary(btn)
			btn.add_theme_font_size_override("font_size", 15)
		else:
			_style_card_default(btn)


func _style_card_default(btn: Button) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.07, 0.12, 0.9)
	sb.border_width_left = 2
	sb.border_width_top = 2
	sb.border_width_right = 2
	sb.border_width_bottom = 2
	sb.border_color = Color(0.18, 0.18, 0.28, 0.7)
	sb.corner_radius_top_left = 10
	sb.corner_radius_top_right = 10
	sb.corner_radius_bottom_right = 10
	sb.corner_radius_bottom_left = 10
	sb.content_margin_left = 14
	sb.content_margin_top = 10
	sb.content_margin_right = 14
	sb.content_margin_bottom = 10
	btn.add_theme_stylebox_override("normal", sb)
	btn.add_theme_stylebox_override("hover", sb)
	btn.add_theme_stylebox_override("pressed", sb)
	btn.add_theme_stylebox_override("focus", sb)
	btn.add_theme_color_override("font_color", UIThemeHelper.C_TEXT_PRIMARY)
	btn.add_theme_font_size_override("font_size", 15)
	btn.alignment = HORIZONTAL_ALIGNMENT_CENTER


func _set_bg(bg_path: String) -> void:
	if not _bg:
		return
	if not bg_path.is_empty() and ResourceLoader.exists(bg_path):
		_bg.texture = load(bg_path) as Texture2D
		_bg.visible = true
	else:
		_bg.texture = null
		_bg.visible = false


func _find_stage_index(stage_id: String) -> int:
	var defs: Array[Dictionary] = GameState.get_stage_defs()
	for i: int in range(defs.size()):
		if str(defs[i].get("id", "")) == stage_id:
			return i
	return -1


func _format_stars(stage_id: String) -> String:
	var stars: int = GameState.get_stage_stars(stage_id)
	var result: String = ""
	for i in range(3):
		result += "★" if i < stars else "☆"
	return result


func _apply_stars_color(lbl: Label, stage_id: String) -> void:
	var record: Dictionary = GameState.get_stage_record(stage_id)
	var cleared: bool = record.get("best_time", -1.0) > 0.0
	if cleared:
		lbl.add_theme_color_override("font_color", Color(1.0, 0.84, 0.0))
	else:
		lbl.add_theme_color_override("font_color", Color(0.27, 0.27, 0.4))


func _build_carousel() -> void:
	if not _carousel_stack:
		return
	var defs: Array[Dictionary] = GameState.get_stage_defs()
	for i: int in range(defs.size()):
		var def: Dictionary = defs[i]
		var img_path: String = str(def.get("monster_image", ""))
		var tex_rect := TextureRect.new()
		tex_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED as TextureRect.StretchMode
		tex_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE as Control.MouseFilter
		if not img_path.is_empty() and ResourceLoader.exists(img_path):
			tex_rect.texture = load(img_path) as Texture2D
		tex_rect.size = Vector2(140, 140)
		tex_rect.modulate = Color(0.2, 0.2, 0.25, 0.25)
		tex_rect.visible = false
		_carousel_stack.add_child(tex_rect)
		_carousel_rects.append(tex_rect)


func _animate_carousel(selected_index: int) -> void:
	if _carousel_rects.is_empty():
		return
	var cw: float = _carousel_stack.size.x if _carousel_stack.size.x > 10 else 300.0
	var cy: float = _carousel_stack.size.y if _carousel_stack.size.y > 10 else 160.0
	for i: int in range(_carousel_rects.size()):
		var carousel_tr: TextureRect = _carousel_rects[i]
		carousel_tr.visible = true
		var tween: Tween = carousel_tr.create_tween()
		tween.set_parallel(true)
		if i == selected_index:
			tween.tween_property(carousel_tr, "position", Vector2(cw / 2 - 80, cy / 2 - 80), 0.3).set_trans(Tween.TRANS_QUAD)
			tween.tween_property(carousel_tr, "size", Vector2(160, 160), 0.3).set_trans(Tween.TRANS_QUAD)
			tween.tween_property(carousel_tr, "modulate", Color(0.5, 0.5, 0.48, 0.95), 0.3)
		else:
			var offset: float = (i - selected_index) * 55.0
			tween.tween_property(carousel_tr, "position", Vector2(cw / 2 - 50 + offset, cy / 2 - 50), 0.3).set_trans(Tween.TRANS_QUAD)
			tween.tween_property(carousel_tr, "size", Vector2(100, 100), 0.3).set_trans(Tween.TRANS_QUAD)
			tween.tween_property(carousel_tr, "modulate", Color(0.15, 0.15, 0.2, 0.2), 0.3)


func _on_start() -> void:
	if _selected_stage_id.is_empty():
		return
	var def: Dictionary = GameState.get_stage_def(_selected_stage_id)
	var scene_path: String = str(def.get("scene", ""))
	if scene_path.is_empty():
		return
	GameState.set_training_mode(false)
	get_tree().change_scene_to_file(scene_path)


func _on_back() -> void:
	get_tree().change_scene_to_file(SCENE_MAIN_MENU)
