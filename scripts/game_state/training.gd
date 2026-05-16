extends RefCounted

var _training_mode: bool = false


func set_training(on: bool) -> void:
	_training_mode = on


func is_active() -> bool:
	return _training_mode
