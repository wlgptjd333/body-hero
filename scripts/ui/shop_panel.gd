extends Control
## Shop Panel: 스웨트(땀방울)로 아이템을 구매하는 UI

signal back_pressed

@onready var _lbl_sweat: Label = $Dim/Panel/Margin/VBox/SweatLabel
@onready var _list: VBoxContainer = $Dim/Panel/Margin/VBox/Scroll/List
@onready var _btn_close: Button = $Dim/Panel/Margin/VBox/BtnClose
@onready var _equip_label: Label = $Dim/Panel/Margin/VBox/EquipLabel

var _item_rows: Dictionary = {}

func _ready() -> void:
	UIThemeHelper.format_glass_popup(self)
	_btn_close.pressed.connect(_on_close)
	UIThemeHelper.style_button_secondary(_btn_close)

	# 패널 스타일
	var panel: Panel = $Dim/Panel
	if panel:
		UIThemeHelper.style_panel_glass(panel)
	var title: Label = $Dim/Panel/Margin/VBox/Title
	if title:
		UIThemeHelper.style_label_title(title)
	if _lbl_sweat:
		UIThemeHelper.style_label_body(_lbl_sweat)
		_lbl_sweat.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if _equip_label:
		UIThemeHelper.style_label_caption(_equip_label)
		_equip_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	_refresh()

func _on_close() -> void:
	back_pressed.emit()

func _refresh() -> void:
	if _lbl_sweat:
		_lbl_sweat.text = "보유 스웨트: %d" % GameState.get_sweat()
	if _equip_label:
		var skin: String = GameState.get_equipped_glove_skin()
		if skin == "":
			_equip_label.text = "착용 중인 글러브: 기본"
		else:
			var name: String = GameState.get_shop_items().get(skin, {}).get("name", skin)
			_equip_label.text = "착용 중인 글러브: %s" % name
	
	for child in _list.get_children():
		child.queue_free()
	_item_rows.clear()

	# 기본 글러브 해제 row
	_add_default_glove_row()

	var items: Dictionary = GameState.get_shop_items()
	for item_id: String in items.keys():
		var def: Dictionary = items[item_id]
		var kind: String = def.get("kind", "")
		var price: int = int(def.get("price", 0))
		var owned: bool = GameState.is_item_owned(item_id)
		var count: int = GameState.get_item_inventory_count(item_id)

		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var title := Label.new()
		title.text = "%s (%d 스웨트)" % [str(def.get("name", item_id)), price]
		title.add_theme_font_size_override("font_size", 15)
		info.add_child(title)

		var desc := Label.new()
		var desc_text: String = str(def.get("desc", ""))
		if kind == "consumable":
			desc_text += " [보유: %d]" % count
		elif kind == "glove_skin" and owned:
			desc_text += " [보유함]"
		desc.text = desc_text
		desc.add_theme_font_size_override("font_size", 12)
		desc.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
		info.add_child(desc)
		row.add_child(info)

		var btn := Button.new()
		var is_equipped: bool = GameState.get_equipped_glove_skin() == item_id

		if kind == "glove_skin" and owned:
			if is_equipped:
				btn.text = "착용 중"
				btn.disabled = true
			else:
				btn.text = "착용"
				btn.pressed.connect(_on_equip.bind(item_id))
		elif kind == "glove_skin" and not owned:
			btn.text = "구매"
			btn.pressed.connect(_on_buy.bind(item_id))
			btn.disabled = GameState.get_sweat() < price
		elif kind == "consumable":
			btn.text = "구매"
			btn.pressed.connect(_on_buy.bind(item_id))
			btn.disabled = GameState.get_sweat() < price
		else:
			btn.text = "구매"
			btn.pressed.connect(_on_buy.bind(item_id))
			btn.disabled = GameState.get_sweat() < price

		row.add_child(btn)
		_list.add_child(row)
		_item_rows[item_id] = {"buy_btn": btn}

		var sep := HSeparator.new()
		_list.add_child(sep)

	var effect_header := Label.new()
	effect_header.text = "━━ 히트 이펙트 ━━"
	effect_header.add_theme_font_size_override("font_size", 14)
	effect_header.add_theme_color_override("font_color", UIThemeHelper.C_ACCENT)
	_list.add_child(effect_header)

	var themes: Dictionary = GameState.get_hit_effect_themes()
	for item_id: String in themes.keys():
		var def: Dictionary = themes[item_id]
		var price: int = int(def.get("price", 0))
		var owned: bool = GameState.is_item_owned(item_id)

		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var title := Label.new()
		title.text = "%s (%d 스웨트)" % [str(def.get("name", item_id)), price]
		title.add_theme_font_size_override("font_size", 15)
		info.add_child(title)

		var desc := Label.new()
		desc.text = str(def.get("desc", ""))
		desc.add_theme_font_size_override("font_size", 12)
		desc.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
		info.add_child(desc)
		row.add_child(info)

		var btn := Button.new()
		var is_equipped: bool = GameState.get_equipped_hit_effect() == item_id

		if owned:
			if is_equipped:
				btn.text = "장착 중"
				btn.disabled = true
			else:
				btn.text = "장착"
				btn.pressed.connect(_on_equip_hit_effect.bind(item_id))
		else:
			btn.text = "구매"
			btn.pressed.connect(_on_buy.bind(item_id))
			btn.disabled = GameState.get_sweat() < price

		row.add_child(btn)
		_list.add_child(row)

		var sep2 := HSeparator.new()
		_list.add_child(sep2)

func _add_default_glove_row() -> void:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var title := Label.new()
	title.text = "기본 글러브"
	title.add_theme_font_size_override("font_size", 15)
	info.add_child(title)

	var desc := Label.new()
	desc.text = "묘한 매력의 기본 글러브"
	desc.add_theme_font_size_override("font_size", 12)
	desc.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	info.add_child(desc)
	row.add_child(info)

	var btn := Button.new()
	var is_default: bool = GameState.get_equipped_glove_skin() == ""
	if is_default:
		btn.text = "착용 중"
		btn.disabled = true
	else:
		btn.text = "착용"
		btn.pressed.connect(_on_equip.bind(""))
	row.add_child(btn)
	_list.add_child(row)

	var sep := HSeparator.new()
	_list.add_child(sep)

func _on_buy(item_id: String) -> void:
	if GameState.try_purchase_item(item_id):
		_refresh()

func _on_equip(item_id: String) -> void:
	if GameState.equip_glove_skin(item_id):
		_refresh()

func _on_equip_hit_effect(item_id: String) -> void:
	if GameState.equip_hit_effect(item_id):
		_refresh()
