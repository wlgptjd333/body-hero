extends Control
## Achievement Panel: 업적 목록을 보여주는 UI

signal back_pressed

@onready var _scroll: ScrollContainer = $Dim/Panel/Margin/VBox/Scroll
@onready var _list: VBoxContainer = $Dim/Panel/Margin/VBox/Scroll/List
@onready var _btn_close: Button = $Dim/Panel/Margin/VBox/BtnClose
@onready var _summary: Label = $Dim/Panel/Margin/VBox/SummaryLabel

func _ready() -> void:
	_btn_close.pressed.connect(_on_close)
	_refresh_list()

func _on_close() -> void:
	back_pressed.emit()

func _refresh_list() -> void:
	# 기존 항목 제거
	for child in _list.get_children():
		child.queue_free()
	
	var defs: Dictionary = GameState.get_achievement_defs()
	var total: int = defs.size()
	var unlocked: int = 0
	
	for id: String in defs.keys():
		var def: Dictionary = defs[id]
		var is_unlocked: bool = GameState.is_achievement_unlocked(id)
		var progress: int = GameState.get_achievement_progress(id)
		var target: int = int(def.get("target", 1))
		if is_unlocked:
			unlocked += 1
		
		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		
		var icon := Label.new()
		icon.text = "🏆" if is_unlocked else "🔒"
		icon.add_theme_font_size_override("font_size", 20)
		row.add_child(icon)
		
		var vbox := VBoxContainer.new()
		vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		
		var title := Label.new()
		title.text = str(def.get("title", id))
		title.add_theme_font_size_override("font_size", 16)
		if is_unlocked:
			title.add_theme_color_override("font_color", Color(1.0, 0.92, 0.35))
		else:
			title.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7))
		vbox.add_child(title)
		
		var desc := Label.new()
		desc.text = "%s (%d / %d)" % [str(def.get("desc", "")), mini(progress, target), target]
		desc.add_theme_font_size_override("font_size", 12)
		desc.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
		vbox.add_child(desc)
		
		var bar := ProgressBar.new()
		bar.max_value = float(target)
		bar.value = float(mini(progress, target))
		bar.custom_minimum_size = Vector2(0, 8)
		vbox.add_child(bar)
		
		row.add_child(vbox)
		_list.add_child(row)
		
		var sep := HSeparator.new()
		_list.add_child(sep)
	
	if _summary:
		_summary.text = "업적: %d / %d 달성" % [unlocked, total]
