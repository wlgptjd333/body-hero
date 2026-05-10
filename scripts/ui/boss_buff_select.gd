extends Control
## Boss Buff Select: 보스 페이즈 클리어 후 버프 선택 UI

signal buff_selected(buff: Dictionary)
signal skip_pressed

@onready var _title: Label = $Dim/Panel/Margin/VBox/Title
@onready var _list: VBoxContainer = $Dim/Panel/Margin/VBox/List
@onready var _btn_skip: Button = $Dim/Panel/Margin/VBox/BtnSkip

func _ready() -> void:
	_btn_skip.pressed.connect(_on_skip)

func setup(options: Array[Dictionary], phase: int) -> void:
	if _title:
		_title.text = "페이즈 %d 클리어! 버프 선택" % phase
	for child in _list.get_children():
		child.queue_free()
	for opt: Dictionary in options:
		var btn := Button.new()
		btn.text = "%s" % str(opt.get("name", "?"))
		btn.custom_minimum_size = Vector2(0, 48)
		btn.pressed.connect(_on_select.bind(opt))
		_list.add_child(btn)

func _on_select(buff: Dictionary) -> void:
	buff_selected.emit(buff)

func _on_skip() -> void:
	skip_pressed.emit()
