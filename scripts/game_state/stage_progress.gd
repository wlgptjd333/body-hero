extends RefCounted

var _save_fn: Callable = Callable()

var _stars: Dictionary = {}
var _records: Dictionary = {}
var _last_played_id: String = "stage_1"
var _best_clear_sec: float = -1.0
var _last_clear_sec: float = -1.0
var _clear_history: Array = []
const HISTORY_MAX := 15

const STAGE_DEFS: Array[Dictionary] = [
	{
		"id": "stage_1",
		"name": "Stage 1",
		"scene": "res://games/boxing/scenes/stage_1.tscn",
		"monster_name": "BULGOGI BURGER",
		"monster_image": "res://assets/textures/characters/enemies/burger/burger_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage1_burger.png",
		"description": "불고기 햄버거가 진화한 몬스터다. 느리지만 묵직한 펀치를 날린다. 가드를 굳히고 타이밍을 노려라.",
	},
	{
		"id": "stage_2",
		"name": "Stage 2",
		"scene": "res://games/boxing/scenes/stage_2.tscn",
		"monster_name": "COLA MONSTER",
		"monster_image": "res://assets/textures/characters/enemies/cola/cola_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage2_cola_arena.png",
		"description": "콜라 캔에서 깨어난 몬스터다. 버거보다 빠르고 강력한 공격을 퍼붓는다. 가드 타이밍이 관건.",
	},
	{
		"id": "stage_3",
		"name": "Stage 3",
		"scene": "res://games/boxing/scenes/stage_3.tscn",
		"monster_name": "FRIES MONSTER",
		"monster_image": "res://assets/textures/characters/enemies/fries/fries_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage3_fries.png",
		"description": "감자튀김 무리에서 태어난 몬스터다. 빠르고 날카로운 연속 공격이 특징. 집중력을 잃지 마라.",
	},
	{
		"id": "stage_4",
		"name": "Stage 4",
		"scene": "res://games/boxing/scenes/stage_4.tscn",
		"monster_name": "PIZZA MONSTER",
		"monster_image": "res://assets/textures/characters/enemies/pizza/pizza_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage4_pizza.png",
		"description": "뜨거운 피자가 화염 방사처럼 펀치를 퍼붓는다. 강력한 내구도를 자랑하지만 움직임은 둔하다. 끝까지 밀어붙여라.",
	},
	{
		"id": "stage_5",
		"name": "Stage 5",
		"scene": "res://games/boxing/scenes/stage_5.tscn",
		"monster_name": "CHICKEN MONSTER",
		"monster_image": "res://assets/textures/characters/enemies/chicken/chicken_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage5_chicken.png",
		"description": "바삭한 치킨에서 태어난 최강의 몬스터. 모든 스탯이 극한에 달했다. 방심은 곧 패배다.",
	},
	{
		"id": "stage_6",
		"name": "BOSS",
		"scene": "res://games/boxing/scenes/stage_6.tscn",
		"monster_name": "MALA TANG BOSS",
		"monster_image": "res://assets/textures/characters/enemies/malatang/malatang_idle_01.png",
		"bg_image": "res://assets/textures/bg/bg_stage6_mara.png",
		"description": "매운 마라탕의 정수에서 태어난 보스. 압도적인 화력과 스피드로 덤벼든다. 모든 것을 걸어라.",
	},
]


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


func get_defs():
	return STAGE_DEFS.duplicate()


func get_def(stage_id: String) -> Dictionary:
	for def: Dictionary in STAGE_DEFS:
		if def.get("id", "") == stage_id:
			return def.duplicate()
	return {}


func get_next_id(current: String) -> String:
	for i: int in range(STAGE_DEFS.size()):
		if STAGE_DEFS[i].get("id", "") == current:
			if i + 1 < STAGE_DEFS.size():
				return str(STAGE_DEFS[i + 1].get("id", ""))
			return ""
	return ""


func get_next_scene(current: String) -> String:
	var next_id: String = get_next_id(current)
	if next_id.is_empty():
		return ""
	var def_dict: Dictionary = get_def(next_id)
	return str(def_dict.get("scene", ""))


func has_next(stage_id: String) -> bool:
	return not get_next_id(stage_id).is_empty()


func get_stars(stage_id: String) -> int:
	return _stars.get(stage_id, 0)


func get_all_stars() -> Dictionary:
	return _stars.duplicate()


func record_stars(stage_id: String, stars: int) -> void:
	var prev: int = _stars.get(stage_id, 0)
	_stars[stage_id] = maxi(prev, clampi(stars, 0, 3))
	_save()


func evaluate_stars(clear_sec: float, max_combo: int, damage_taken: float) -> int:
	var s: int = 1
	if clear_sec <= 45.0:
		s += 1
	if max_combo >= 20:
		s += 1
	if damage_taken <= 30.0:
		s += 1
	return clampi(s, 0, 3)


func get_record(stage_id: String) -> Dictionary:
	return _records.get(stage_id, {}).duplicate()


func update_record(stage_id: String, clear_sec: float, max_combo: int, damage_taken: float) -> void:
	if not _records.has(stage_id):
		_records[stage_id] = {}
	var rec: Dictionary = _records[stage_id]
	var bt: float = rec.get("best_time", -1.0)
	if bt < 0.0 or clear_sec < bt:
		rec["best_time"] = clear_sec
	var bc: int = rec.get("best_combo", 0)
	rec["best_combo"] = maxi(bc, max_combo)
	var ld: float = rec.get("least_dmg", -1.0)
	if ld < 0.0 or damage_taken < ld:
		rec["least_dmg"] = damage_taken
	_save()


func record_clear_time(seconds: float) -> void:
	if seconds <= 0.0 or not is_finite(seconds):
		return
	_last_clear_sec = seconds
	if _best_clear_sec < 0.0 or seconds < _best_clear_sec:
		_best_clear_sec = seconds
	_clear_history.insert(0, seconds)
	while _clear_history.size() > HISTORY_MAX:
		_clear_history.pop_back()
	_save()


func get_best_clear_sec() -> float:
	return _best_clear_sec


func get_last_clear_sec() -> float:
	return _last_clear_sec


func get_clear_history():
	return _clear_history.duplicate()


func format_clear_time(seconds: float) -> String:
	if seconds < 0.0 or not is_finite(seconds):
		return "기록 없음"
	var m: int = int(seconds / 60.0)
	var s: float = seconds - float(m) * 60.0
	if m > 0:
		return "%d분 %.2f초" % [m, s]
	return "%.2f초" % s


func get_last_played_id() -> String:
	return _last_played_id


func set_last_played_id(stage_id: String) -> void:
	_last_played_id = stage_id
	_save()


func get_save_data() -> Dictionary:
	return {
		"stars": _stars,
		"records": _records,
		"last_played": _last_played_id,
		"best_sec": _best_clear_sec,
		"last_sec": _last_clear_sec,
		"history": _clear_history,
	}


func load_save_data(data: Dictionary) -> void:
	_stars = data.get("stars", {})
	_records = data.get("records", {})
	_last_played_id = data.get("last_played", "stage_1")
	_best_clear_sec = data.get("best_sec", -1.0)
	_last_clear_sec = data.get("last_sec", -1.0)
	_clear_history = data.get("history", []).duplicate()


func reset_all() -> void:
	_stars.clear()
	_records.clear()
	_best_clear_sec = -1.0
	_last_clear_sec = -1.0
	_clear_history.clear()
