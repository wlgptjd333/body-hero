extends Control
## 게임 설명 패널: 조작법·규칙, 왼쪽 상단 뒤로가기

signal back_pressed

@onready var _back_btn: Button = $Panel/VBox/BackButton


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)


func _on_back() -> void:
	back_pressed.emit()
