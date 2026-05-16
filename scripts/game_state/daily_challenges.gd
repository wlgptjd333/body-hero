extends RefCounted
## Daily challenge system: rolling, progress tracking, calendar sync.
## Pure state logic — no Node/scene-tree dependency.

const DAILY_CHALLENGE_DEFS: Dictionary = {
	"punches_25": {"title": "펀치 25회 성공", "kind": "punches", "target": 25},
	"punches_12": {"title": "펀치 12회 성공", "kind": "punches", "target": 12},
	"uppers_10": {"title": "어퍼컷 10회 성공", "kind": "uppers", "target": 10},
	"guards_15": {"title": "가드 15회", "kind": "guards", "target": 15},
	"kcal_40": {"title": "오늘 누적 40 kcal", "kind": "kcal_today", "target": 40},
	"sessions_1": {"title": "운동 세션 1회 완료", "kind": "sessions_today", "target": 1},
}
const DAILY_CHALLENGE_POOL_IDS: Array[String] = [
	"punches_25", "punches_12", "uppers_10", "guards_15", "kcal_40", "sessions_1",
]

var _challenge_date: String = ""
var _challenge_picks: Array[String] = []
var _challenge_progress: Dictionary = {}  # 과제 id -> 누적 (액션 기반만)
var _sessions_completed: int = 0  # 오늘 end_workout_session 호출 횟수

## Callable supplied by GameState to trigger save after mutations.
var _save_fn: Callable = Callable()
## Callable to get today's total calories (from workout tracker).
var _get_today_calories_fn: Callable = Callable()
## Callable to get today_key string.
var _today_key_fn: Callable = Callable()


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn

func set_today_calories_fn(fn: Callable) -> void:
	_get_today_calories_fn = fn

func set_today_key_fn(fn: Callable) -> void:
	_today_key_fn = fn

func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


# --- Accessors for persistence ---

func get_date() -> String:
	return _challenge_date

func get_picks() -> Array[String]:
	return _challenge_picks

func get_progress() -> Dictionary:
	return _challenge_progress

func get_sessions_completed() -> int:
	return _sessions_completed

func set_date(d: String) -> void:
	_challenge_date = d

func set_picks(p: Array[String]) -> void:
	_challenge_picks = p

func set_progress(p: Dictionary) -> void:
	_challenge_progress = p

func set_sessions_completed(n: int) -> void:
	_sessions_completed = n


# --- Calendar sync ---

func sync_calendar() -> void:
	if _challenge_date == _today_key():
		return
	_roll_fresh()


func _today_key() -> String:
	if _today_key_fn.is_valid():
		return _today_key_fn.call()
	# fallback
	var dt := Time.get_datetime_dict_from_unix_time(int(Time.get_unix_time_from_system()))
	return "%04d-%02d-%02d" % [int(dt.get("year", 1970)), int(dt.get("month", 1)), int(dt.get("day", 1))]


func _roll_fresh() -> void:
	_challenge_date = _today_key()
	_challenge_picks.clear()
	_challenge_progress.clear()
	_sessions_completed = 0
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(_challenge_date)
	var pool: Array[String] = DAILY_CHALLENGE_POOL_IDS.duplicate()
	for _t: int in range(3):
		if pool.is_empty():
			break
		var idx: int = rng.randi_range(0, pool.size() - 1)
		_challenge_picks.append(pool[idx])
		pool.remove_at(idx)
	_save()


# --- Progress ---

func bump_for_punch_action(action: String) -> void:
	var kind: String = ""
	match action:
		"punch_l", "punch_r":
			kind = "punches"
		"upper_l", "upper_r":
			kind = "uppers"
		"squat":
			kind = "squats"
		_:
			return
	bump_for_kind(kind)


func bump_for_kind(kind: String) -> void:
	for cid: String in _challenge_picks:
		var def: Variant = DAILY_CHALLENGE_DEFS.get(cid, null)
		if def == null or typeof(def) != TYPE_DICTIONARY:
			continue
		if str(def.get("kind", "")) != kind:
			continue
		var t: int = int(def.get("target", 1))
		var cur: int = int(_challenge_progress.get(cid, 0))
		if cur >= t:
			continue
		_challenge_progress[cid] = mini(cur + 1, t)


func increment_sessions() -> void:
	_sessions_completed += 1


func _current_for_id(challenge_id: String) -> int:
	var def: Variant = DAILY_CHALLENGE_DEFS.get(challenge_id, null)
	if def == null or typeof(def) != TYPE_DICTIONARY:
		return 0
	var kind: String = str(def.get("kind", ""))
	match kind:
		"kcal_today":
			if _get_today_calories_fn.is_valid():
				return int(floorf(_get_today_calories_fn.call()))
			return 0
		"sessions_today":
			return _sessions_completed
		_:
			return int(_challenge_progress.get(challenge_id, 0))


## 메인 메뉴 등 UI용: 오늘의 도전 3개 (제목, 현재, 목표, 완료 여부)
func get_save_data() -> Dictionary:
	return {
		"date": _challenge_date,
		"sessions_completed": _sessions_completed,
		"picks": _challenge_picks,
		"progress": _challenge_progress,
	}


func reset_all() -> void:
	_challenge_date = ""
	_challenge_picks.clear()
	_challenge_progress.clear()
	_sessions_completed = 0


func get_challenges_for_ui():
	sync_calendar()
	var out: Array[Dictionary] = []
	for cid: String in _challenge_picks:
		var def: Variant = DAILY_CHALLENGE_DEFS.get(cid, null)
		if def == null or typeof(def) != TYPE_DICTIONARY:
			continue
		var target: int = int(def.get("target", 1))
		var cur: int = _current_for_id(cid)
		out.append({
			"id": cid,
			"title": str(def.get("title", cid)),
			"current": mini(cur, target),
			"target": target,
			"completed": cur >= target,
		})
	return out
