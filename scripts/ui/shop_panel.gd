extends Control
## Shop Panel: 스웨트(땀방울)로 아이템을 구매하는 UI

signal back_pressed

@onready var _lbl_sweat: Label = $Dim/Panel/Margin/VBox/SweatLabel
@onready var _list: VBoxContainer = $Dim/Panel/Margin/VBox/Scroll/List
@onready var _btn_close: Button = $Dim/Panel/Margin/VBox/BtnClose
@onready var _equip_label: Label = $Dim/Panel/Margin/VBox/EquipLabel

var _item_rows: Dictionary = {}

func _ready() -> void:
	_btn_close.pressed.connect(_on_close)
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
		btn.text = "구매" if not (kind == "glove_skin" and owned) else "착용"
		if kind == "glove_skin" and owned:
			if GameState.get_equipped_glove_skin() == item_id:
				btn.text = "착용 중"
				btn.disabled = true
			else:
				btn.pressed.connect(func() -> void: _on_equip(item_id))
		elif kind == "consumable":
			btn.pressed.connect(func() -> void: _on_buy(item_id))
		else:
			btn.pressed.connect(func() -> void: _on_buy(item_id))
		btn.disabled = GameState.get_sweat() < price
		row.add_child(btn)
		
		_list.add_child(row)
		_item_rows[item_id] = {"buy_btn": btn}
		
		var sep := HSeparator.new()
		_list.add_child(sep)

func _on_buy(item_id: String) -> void:
	if GameState.try_purchase_item(item_id):
		_refresh()

func _on_equip(item_id: String) -> void:
	if GameState.equip_glove_skin(item_id):
		_refresh()
