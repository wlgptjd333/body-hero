extends RefCounted

const EASY := "easy"
const NORMAL := "normal"
const HARD := "hard"

var _difficulty: String = NORMAL
var _save_fn: Callable = Callable()


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


func get_difficulty() -> String:
	return _difficulty


func set_d(d: String) -> void:
	if d == EASY or d == NORMAL or d == HARD:
		_difficulty = d
		_save()


func get_label() -> String:
	match _difficulty:
		EASY: return "EASY"
		HARD: return "HARD"
		_: return "NORMAL"


func get_enemy_stat_mul() -> float:
	match _difficulty:
		EASY: return 0.75
		HARD: return 1.4
		_: return 1.0


func get_save_data() -> String:
	return _difficulty


func load_save_data(data: String) -> void:
	if data == EASY or data == NORMAL or data == HARD:
		_difficulty = data
	else:
		_difficulty = NORMAL
