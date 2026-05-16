extends RefCounted

var _save_fn: Callable = Callable()
var _phase: int = 0
var _buffs_selected: Array = []

const BUFF_OPTIONS: Array[Dictionary] = [
	{"name": "공격력 증가", "effect": {"player_damage_mul": 1.25}},
	{"name": "스태미너 효율", "effect": {"stamina_cost_mul": 0.8}},
	{"name": "철벽", "effect": {"guard_chip_reduction": 0.5}},
	{"name": "급속 회복", "effect": {"stamina_recover_mul": 1.3}},
	{"name": "천하장사", "effect": {"max_hp_mul": 1.2}},
	{"name": "콤보 유지", "effect": {"combo_reset_time_bonus": 2.0}},
]


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


func get_phase() -> int:
	return _phase


func set_phase(p: int) -> void:
	_phase = p
	_save()


func get_buffs_selected():
	return _buffs_selected.duplicate()


func get_options():
	return BUFF_OPTIONS.duplicate()


func get_active_effects() -> Dictionary:
	var result: Dictionary = {}
	for buff: Dictionary in _buffs_selected:
		var eff: Dictionary = buff.get("effect", {})
		for k: String in eff.keys():
			if result.has(k):
				result[k] = maxf(result[k], eff[k])
			else:
				result[k] = eff[k]
	return result


func get_save_data() -> Dictionary:
	return {
		"phase": _phase,
		"buffs": _buffs_selected,
	}


func load_save_data(data: Dictionary) -> void:
	_phase = data.get("phase", 0)
	_buffs_selected = data.get("buffs", []).duplicate()


func add_buff(buff: Dictionary) -> void:
	_buffs_selected.append(buff)
	_save()


func reset_all() -> void:
	_phase = 0
	_buffs_selected.clear()
