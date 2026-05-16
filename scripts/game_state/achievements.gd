extends RefCounted

var _save_fn: Callable = Callable()

const ACHIEVEMENT_DEFS: Dictionary = {
	"first_blood": {"title": "첫 KO", "desc": "처음으로 적을 처치하세요", "kind": "kills", "target": 1},
	"combo_10": {"title": "콤보 초보", "desc": "10콤보 달성", "kind": "combo", "target": 10},
	"combo_30": {"title": "콤보 마스터", "desc": "30콤보 달성", "kind": "combo", "target": 30},
	"combo_50": {"title": "콤보의 신", "desc": "50콤보 달성", "kind": "combo", "target": 50},
	"punch_100": {"title": "주먹 단련", "desc": "누적 펀치 1000회", "kind": "punches_total", "target": 1000},
	"punch_500": {"title": "복싱 중독", "desc": "누적 펀치 10000회", "kind": "punches_total", "target": 10000},
	"guard_50": {"title": "철벽 수비", "desc": "누적 가드 500회", "kind": "guards_total", "target": 500},
	"speedrun": {"title": "스피드러너", "desc": "30초 이내 스테이지 클리어", "kind": "clear_time", "target": 30},
	"no_damage": {"title": "무적", "desc": "플레이어가 한 번도 맞지 않고 클리어", "kind": "no_damage_clear", "target": 1},
	"upper_50": {"title": "어퍼킹", "desc": "누적 어퍼컷 500회", "kind": "uppers_total", "target": 500},
}

var _unlocked: Dictionary = {}
var _progress: Dictionary = {}


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


func get_defs() -> Dictionary:
	return ACHIEVEMENT_DEFS.duplicate()


func is_unlocked(id: String) -> bool:
	return _unlocked.get(id, false)


func get_progress(id: String) -> int:
	return _progress.get(id, 0)


func unlock(id: String) -> bool:
	if not ACHIEVEMENT_DEFS.has(id):
		return false
	if _unlocked.get(id, false):
		return false
	_unlocked[id] = true
	_save()
	return true


func bump(id: String, amount: int = 1) -> void:
	if not ACHIEVEMENT_DEFS.has(id):
		return
	var cur: int = _progress.get(id, 0)
	var def: Dictionary = ACHIEVEMENT_DEFS[id]
	var target: int = int(def.get("target", 1))
	_progress[id] = mini(cur + amount, target)
	if _progress[id] >= target:
		unlock(id)


func check_after_session(clear_sec: float, max_combo: int, damage_taken: float, is_clear: bool) -> Array[String]:
	var newly_unlocked: Array[String] = []
	if is_clear:
		_progress["first_blood"] = 1
		if _progress.get("first_blood", 0) >= 1 and unlock("first_blood"):
			newly_unlocked.append("first_blood")
		if clear_sec <= 30.0 and unlock("speedrun"):
			newly_unlocked.append("speedrun")
		if damage_taken <= 0.0 and unlock("no_damage"):
			newly_unlocked.append("no_damage")
	_progress["combo_10"] = maxi(_progress.get("combo_10", 0), max_combo)
	_progress["combo_30"] = maxi(_progress.get("combo_30", 0), max_combo)
	_progress["combo_50"] = maxi(_progress.get("combo_50", 0), max_combo)
	for aid in ["combo_10", "combo_30", "combo_50"]:
		if _progress.get(aid, 0) >= ACHIEVEMENT_DEFS[aid]["target"] and unlock(aid):
			newly_unlocked.append(aid)
	_save()
	return newly_unlocked


func get_save_data() -> Dictionary:
	return {"unlocked": _unlocked, "progress": _progress}


func load_save_data(data: Dictionary) -> void:
	_unlocked = data.get("unlocked", {})
	_progress = data.get("progress", {})


func reset_all() -> void:
	_unlocked.clear()
	_progress.clear()
