extends RefCounted

var _save_fn: Callable = Callable()
var _sweat: int = 0
var _upgrade_hp: int = 0
var _upgrade_stamina: int = 0
var _upgrade_recover: int = 0
var _on_refresh: Callable = func(_p_max_hp: float, _p_sta_max: float, _p_rec: float): pass

const BASE_PLAYER_MAX_HP := 200.0
const BASE_STAMINA_MAX := 100.0
const BASE_STAMINA_PASSIVE_RECOVER := 10.0
const UPGRADE_MAX_STEPS := 20
const UPGRADE_HP_PER_STEP := 5.0
const UPGRADE_STAMINA_PER_STEP := 5.0
const UPGRADE_RECOVER_PER_STEP := 0.5


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func set_on_refresh(fn: Callable) -> void:
	_on_refresh = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


func get_sweat() -> int:
	return _sweat


func set_sweat(v: int) -> void:
	_sweat = maxi(0, v)
	_save()


func add_sweat(amount: int) -> void:
	if amount <= 0:
		return
	_sweat = maxi(0, _sweat + amount)
	_save()


func get_hp_level() -> int:
	return _upgrade_hp


func get_stamina_level() -> int:
	return _upgrade_stamina


func get_recover_level() -> int:
	return _upgrade_recover


func try_purchase(kind: String) -> bool:
	if _sweat < 1:
		return false
	match kind:
		"hp":
			if _upgrade_hp >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_hp += 1
			_recalc_and_notify()
			return true
		"stamina":
			if _upgrade_stamina >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_stamina += 1
			_recalc_and_notify()
			return true
		"recover":
			if _upgrade_recover >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_recover += 1
			_recalc_and_notify()
			return true
		_:
			return false


func reset_all(refund_sweat: bool = true) -> bool:
	var spent: int = _upgrade_hp + _upgrade_stamina + _upgrade_recover
	if spent <= 0:
		return false
	_upgrade_hp = 0
	_upgrade_stamina = 0
	_upgrade_recover = 0
	if refund_sweat:
		_sweat += spent
	_recalc_and_notify()
	_save()
	return true


func _recalc_and_notify() -> void:
	var max_hp: float = BASE_PLAYER_MAX_HP + float(_upgrade_hp) * UPGRADE_HP_PER_STEP
	var sta_max: float = BASE_STAMINA_MAX + float(_upgrade_stamina) * UPGRADE_STAMINA_PER_STEP
	var rec: float = BASE_STAMINA_PASSIVE_RECOVER + float(_upgrade_recover) * UPGRADE_RECOVER_PER_STEP
	_on_refresh.call(max_hp, sta_max, rec)
	_save()


func get_save_data() -> Dictionary:
	return {
		"sweat": _sweat,
		"up_hp": _upgrade_hp,
		"up_stamina": _upgrade_stamina,
		"up_recover": _upgrade_recover,
	}


func load_save_data(data: Dictionary) -> void:
	_sweat = data.get("sweat", 0)
	_upgrade_hp = clampi(data.get("up_hp", 0), 0, UPGRADE_MAX_STEPS)
	_upgrade_stamina = clampi(data.get("up_stamina", 0), 0, UPGRADE_MAX_STEPS)
	_upgrade_recover = clampi(data.get("up_recover", 0), 0, UPGRADE_MAX_STEPS)
	_recalc_and_notify()
