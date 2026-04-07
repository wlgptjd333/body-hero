extends Node
## 전역 게임 상태 (AutoLoad 싱글톤)
## 접근: GameState.stamina, GameState.consume_stamina(4) 등

# 플레이어
var player_hp: float = 100.0
var player_max_hp: float = 100.0
var stamina: float = 100.0
var stamina_max: float = 100.0

# 스태미너 소모량 (피트니스 복싱 밸런스)
const STAMINA_JAB := 4
const STAMINA_HOOK := 8
const STAMINA_UPPERCUT := 12

# 가만히 있을 때 스태미너 회복 (초당). 가드 유지 중에는 감소/회복 없음(막기 성공 시만 별도 회복)
const STAMINA_PASSIVE_RECOVER_PER_SEC := 10.0
# 가드로 적 공격을 막았을 때 스태미너 회복량 (구: 막기 소모였던 수치를 회복으로 전환)
const STAMINA_ON_BLOCK_RECOVER := 20.0
# 가드 막기 성공 시 HP 소모 (방어 대가, 매우 소량)
const HP_CHIP_ON_GUARD_BLOCK := 1.5

# 가드: 플레이어가 가드 중이면 true
var is_guarding: bool = false

# 칼로리 추정치 (게임 내 상대 지표)
const KCAL_JAB := 0.35
const KCAL_HOOK := 0.50
const KCAL_UPPERCUT := 0.55
const KCAL_DODGE := 0.30
const KCAL_GUARD_PER_SEC := 0.06
const DEFAULT_WEIGHT_KG := 70.0
const DEFAULT_HEIGHT_CM := 170.0
const DEFAULT_AGE := 30
const GENDER_MALE := "male"
const GENDER_FEMALE := "female"
const GENDER_OTHER := "other"

# 통계: 1 가드, 2 왼손 잽, 3 오른손 잽, 4 왼손 어퍼컷, 5 오른손 어퍼컷, 6 왼손 훅, 7 오른손 훅 (누적, 저장됨)
const STATS_KEYS := ["guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
var _punch_counts: Dictionary = {}  # key -> int (현재 세션 + 로드된 누적)
var _daily_calories: Dictionary = {}  # "YYYY-MM-DD" -> float
var _daily_weight_log: Dictionary = {}  # "YYYY-MM-DD" -> float (통계 패널에서 직접 기록)

# 일일 도전과제 (날짜가 바뀌면 과제 3개 재추첨, 진행도 초기화)
const DAILY_CHALLENGE_DEFS: Dictionary = {
	"jabs_25": {"title": "잽 25회 성공", "kind": "jabs", "target": 25},
	"hooks_12": {"title": "훅 12회 성공", "kind": "hooks", "target": 12},
	"uppers_10": {"title": "어퍼컷 10회 성공", "kind": "uppers", "target": 10},
	"guards_15": {"title": "가드 15회", "kind": "guards", "target": 15},
	"kcal_40": {"title": "오늘 누적 40 kcal", "kind": "kcal_today", "target": 40},
	"sessions_1": {"title": "운동 세션 1회 완료", "kind": "sessions_today", "target": 1},
}
const DAILY_CHALLENGE_POOL_IDS: Array[String] = [
	"jabs_25", "hooks_12", "uppers_10", "guards_15", "kcal_40", "sessions_1",
]
var _daily_challenge_date: String = ""
var _daily_challenge_picks: Array[String] = []
var _daily_challenge_progress: Dictionary = {}  # 과제 id -> 누적 (액션 기반만)
var _daily_sessions_completed: int = 0  # 오늘 end_workout_session 호출 횟수
var _session_action_counts: Dictionary = {}
var _session_active: bool = false
var _session_elapsed_sec: float = 0.0
var _session_calories: float = 0.0
var _last_session_calories: float = 0.0
var _weight_kg: float = DEFAULT_WEIGHT_KG
var _intensity_factor: float = 1.0
var _height_cm: float = DEFAULT_HEIGHT_CM
var _age: int = DEFAULT_AGE
var _gender: String = GENDER_MALE
## 0이면 `get_daily_kcal_goal()`에서 BMI 기반 권장값을 씀. 0 초과면 사용자 지정(저장됨)
var _daily_kcal_goal: float = 0.0

const STATS_PATH := "user://body_hero_stats.cfg"

func _init() -> void:
	for k in STATS_KEYS:
		_punch_counts[k] = 0
	for k in ["jab_l", "jab_r", "hook_l", "hook_r", "upper_l", "upper_r", "dodge_l", "dodge_r", "guard"]:
		_session_action_counts[k] = 0
	load_stats()

func get_punch_count(action: String) -> int:
	return _punch_counts.get(action, 0)

func get_all_punch_counts() -> Dictionary:
	return _punch_counts.duplicate()

func add_punch_count(action: String) -> void:
	if action in _punch_counts:
		_punch_counts[action] += 1
		_sync_daily_challenge_calendar()
		_daily_bump_for_punch_action(action)
		save_stats()

func record_guard() -> void:
	if "guard" in _punch_counts:
		_punch_counts["guard"] += 1
		_sync_daily_challenge_calendar()
		_daily_bump_for_kind("guards")
		save_stats()

func reset_punch_counts() -> void:
	# 게임 시작 시 현재 세션만 리셋하지 않고, 누적 통계는 유지 (통계 패널에서만 누적 표시)
	pass

func set_guarding(on: bool) -> void:
	is_guarding = on

func _process(delta: float) -> void:
	if _session_active:
		_session_elapsed_sec += delta
		if is_guarding:
			_session_calories += KCAL_GUARD_PER_SEC * delta
	if not is_guarding:
		if stamina < stamina_max:
			stamina = minf(stamina_max, stamina + STAMINA_PASSIVE_RECOVER_PER_SEC * delta)

func consume_stamina(amount: float) -> bool:
	if stamina < amount:
		return false
	stamina -= amount
	return true


## 적 공격을 가드로 막았을 때: 스태미너 회복 + HP 소량 감소
func apply_guard_block_success() -> void:
	stamina = minf(stamina_max, stamina + STAMINA_ON_BLOCK_RECOVER)
	player_hp = maxf(0.0, player_hp - HP_CHIP_ON_GUARD_BLOCK)

func get_stamina_ratio() -> float:
	if stamina_max <= 0.0:
		return 1.0
	return clampf(stamina / stamina_max, 0.0, 1.0)

func get_player_hp_ratio() -> float:
	if player_max_hp <= 0.0:
		return 1.0
	return clampf(player_hp / player_max_hp, 0.0, 1.0)

func start_workout_session() -> void:
	_session_active = true
	_session_elapsed_sec = 0.0
	_session_calories = 0.0
	for k in _session_action_counts.keys():
		_session_action_counts[k] = 0

func record_action_for_calorie(action: String) -> void:
	if not _session_active:
		return
	if not _session_action_counts.has(action):
		return
	_session_action_counts[action] += 1
	match action:
		"jab_l", "jab_r":
			_session_calories += KCAL_JAB
		"hook_l", "hook_r":
			_session_calories += KCAL_HOOK
		"upper_l", "upper_r":
			_session_calories += KCAL_UPPERCUT
		"dodge_l", "dodge_r":
			_session_calories += KCAL_DODGE
		_:
			pass

func end_workout_session() -> float:
	if not _session_active:
		return _last_session_calories
	_session_active = false
	var minutes := maxf(_session_elapsed_sec / 60.0, 0.1)
	var total_actions: int = 0
	for k in _session_action_counts.keys():
		total_actions += int(_session_action_counts[k])
	var density := float(total_actions) / minutes
	# MET 기반 추정: 복싱 피트니스(중강도~고강도) 범위를 단순화
	var met := clampf(5.5 + 0.08 * (density - 30.0), 5.5, 11.0)
	var met_kcal := met * 3.5 * _weight_kg / 200.0 * minutes
	# 동작 기반 값(기존)과 MET 기반 값을 블렌딩해 과소/과대 추정 완화
	var profile_factor := _get_profile_factor()
	_last_session_calories = maxf(met_kcal, _session_calories * 0.8) * _intensity_factor * profile_factor
	_add_today_calories(_last_session_calories)
	_sync_daily_challenge_calendar()
	_daily_sessions_completed += 1
	save_stats()
	return _last_session_calories

func get_last_session_calories() -> float:
	return _last_session_calories

func get_recent_daily_calories(days: int = 30) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var count := maxi(1, days)
	for i in range(count - 1, -1, -1):
		var ts := Time.get_unix_time_from_system() - (86400 * i)
		var date_key := _date_key_from_unix(ts)
		result.append({
			"date": date_key,
			"calories": float(_daily_calories.get(date_key, 0.0))
		})
	return result


func get_recent_daily_weight_log(days: int = 30) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var count := maxi(1, days)
	for i in range(count - 1, -1, -1):
		var ts := Time.get_unix_time_from_system() - (86400 * i)
		var date_key := _date_key_from_unix(ts)
		var w: float = float(_daily_weight_log.get(date_key, 0.0))
		result.append({"date": date_key, "weight": w})
	return result


## 오늘 날짜에 체중 기록(kg). 칼로리 계산용 프로필 체중도 같이 갱신.
func log_today_weight_kg(kg: float) -> void:
	if kg <= 0.0:
		return
	kg = clampf(kg, 30.0, 180.0)
	_daily_weight_log[_today_key()] = kg
	set_weight_kg(kg)


func get_today_logged_weight_kg() -> float:
	return float(_daily_weight_log.get(_today_key(), 0.0))


func get_today_calories() -> float:
	return float(_daily_calories.get(_today_key(), 0.0))

func set_weight_kg(v: float) -> void:
	if v <= 0.0:
		_weight_kg = DEFAULT_WEIGHT_KG
	else:
		_weight_kg = clampf(v, 30.0, 180.0)
	save_stats()

func get_weight_kg() -> float:
	return _weight_kg

func set_intensity_factor(v: float) -> void:
	_intensity_factor = clampf(v, 0.8, 1.3)
	save_stats()

func get_intensity_factor() -> float:
	return _intensity_factor

func set_height_cm(v: float) -> void:
	if v <= 0.0:
		_height_cm = DEFAULT_HEIGHT_CM
	else:
		_height_cm = clampf(v, 120.0, 220.0)
	save_stats()

func get_height_cm() -> float:
	return _height_cm

func set_age(v: int) -> void:
	if v <= 0:
		_age = DEFAULT_AGE
	else:
		_age = clampi(v, 10, 100)
	save_stats()

func get_age() -> int:
	return _age

func set_gender(v: String) -> void:
	if v != GENDER_MALE and v != GENDER_FEMALE and v != GENDER_OTHER:
		_gender = GENDER_MALE
	else:
		_gender = v
	save_stats()

func get_gender() -> String:
	return _gender


func get_bmi() -> float:
	var h_m: float = get_height_cm() / 100.0
	if h_m <= 0.001:
		return 0.0
	return get_weight_kg() / (h_m * h_m)


func get_bmi_category_label() -> String:
	var b: float = get_bmi()
	if b <= 0.0:
		return "—"
	if b < 18.5:
		return "저체중"
	if b < 25.0:
		return "정상"
	if b < 30.0:
		return "과체중"
	return "비만"


## BMI·BMR을 참고한 하루 운동(추가 소모) 목표 kcal 추정. 의료·감량 처방 아님.
func get_recommended_daily_kcal_goal() -> float:
	var bmi: float = get_bmi()
	var bmr: float = _estimate_bmr_kcal_per_day()
	if bmr <= 0.0:
		bmr = 1500.0
	var rec: float
	if bmi <= 0.0:
		rec = clampf(0.12 * bmr, 150.0, 350.0)
	elif bmi < 18.5:
		rec = clampf(0.08 * bmr, 90.0, 220.0)
	elif bmi < 25.0:
		rec = clampf(0.12 * bmr, 150.0, 380.0)
	elif bmi < 30.0:
		rec = clampf(0.15 * bmr, 200.0, 450.0)
	else:
		rec = clampf(0.18 * bmr, 250.0, 550.0)
	return float(roundi(rec))


func has_custom_daily_kcal_goal() -> bool:
	return _daily_kcal_goal > 0.0


func get_daily_kcal_goal() -> float:
	if _daily_kcal_goal > 0.0:
		return _daily_kcal_goal
	return get_recommended_daily_kcal_goal()


func set_daily_kcal_goal(kcal: float) -> void:
	_daily_kcal_goal = clampf(kcal, 50.0, 2000.0)
	save_stats()


## 권장 식으로 목표를 덮어쓰고 저장 (BMI·프로필 변경 후 다시 맞출 때)
func apply_recommended_daily_kcal_goal() -> void:
	_daily_kcal_goal = get_recommended_daily_kcal_goal()
	save_stats()


## 오늘 목표 대비 남은 칼로리를 동작별 상수로 나눈 이론상 횟수 (세션 MET 보정 없음)
func get_daily_goal_punch_hints() -> Dictionary:
	var goal: float = get_daily_kcal_goal()
	var today: float = get_today_calories()
	var rem: float = maxf(0.0, goal - today)
	var avg_three: float = (KCAL_JAB + KCAL_HOOK + KCAL_UPPERCUT) / 3.0
	if rem <= 0.0001:
		return {
			"remaining": 0.0,
			"goal": goal,
			"today": today,
			"jab_only": 0,
			"hook_only": 0,
			"upper_only": 0,
			"dodge_only": 0,
			"mixed_same": 0,
		}
	return {
		"remaining": rem,
		"goal": goal,
		"today": today,
		"jab_only": int(ceilf(rem / KCAL_JAB)),
		"hook_only": int(ceilf(rem / KCAL_HOOK)),
		"upper_only": int(ceilf(rem / KCAL_UPPERCUT)),
		"dodge_only": int(ceilf(rem / KCAL_DODGE)),
		"mixed_same": int(ceilf(rem / avg_three)),
	}


func _estimate_bmr_kcal_per_day() -> float:
	# Mifflin-St Jeor 기반 대략치 (개인 보정용, 의료용 아님)
	var base := 10.0 * _weight_kg + 6.25 * _height_cm - 5.0 * float(_age)
	if _gender == GENDER_FEMALE:
		return base - 161.0
	if _gender == GENDER_MALE:
		return base + 5.0
	return base - 78.0  # male/female 중간값 근사

func _get_profile_factor() -> float:
	var bmr := _estimate_bmr_kcal_per_day()
	# 기준 프로필(70kg, 170cm, 30세, 남성) 대비 보정
	var ref_bmr := 10.0 * 70.0 + 6.25 * 170.0 - 5.0 * 30.0 + 5.0
	if ref_bmr <= 0.0:
		return 1.0
	return clampf(bmr / ref_bmr, 0.85, 1.2)

func _add_today_calories(kcal: float) -> void:
	if kcal <= 0.0:
		return
	var key := _today_key()
	_daily_calories[key] = float(_daily_calories.get(key, 0.0)) + kcal

func _today_key() -> String:
	return _date_key_from_unix(Time.get_unix_time_from_system())


func _sync_daily_challenge_calendar() -> void:
	if _daily_challenge_date == _today_key():
		return
	_roll_fresh_daily_challenges()


func _roll_fresh_daily_challenges() -> void:
	_daily_challenge_date = _today_key()
	_daily_challenge_picks.clear()
	_daily_challenge_progress.clear()
	_daily_sessions_completed = 0
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(_daily_challenge_date)
	var pool: Array[String] = DAILY_CHALLENGE_POOL_IDS.duplicate()
	for _t in range(3):
		if pool.is_empty():
			break
		var idx: int = rng.randi_range(0, pool.size() - 1)
		_daily_challenge_picks.append(pool[idx])
		pool.remove_at(idx)
	save_stats()


func _daily_bump_for_punch_action(action: String) -> void:
	var kind: String = ""
	match action:
		"jab_l", "jab_r":
			kind = "jabs"
		"hook_l", "hook_r":
			kind = "hooks"
		"upper_l", "upper_r":
			kind = "uppers"
		_:
			return
	_daily_bump_for_kind(kind)


func _daily_bump_for_kind(kind: String) -> void:
	for cid: String in _daily_challenge_picks:
		var def: Variant = DAILY_CHALLENGE_DEFS.get(cid, null)
		if def == null or typeof(def) != TYPE_DICTIONARY:
			continue
		if str(def.get("kind", "")) != kind:
			continue
		var t: int = int(def.get("target", 1))
		var cur: int = int(_daily_challenge_progress.get(cid, 0))
		if cur >= t:
			continue
		_daily_challenge_progress[cid] = mini(cur + 1, t)


func _daily_challenge_current_for_id(challenge_id: String) -> int:
	var def: Variant = DAILY_CHALLENGE_DEFS.get(challenge_id, null)
	if def == null or typeof(def) != TYPE_DICTIONARY:
		return 0
	var kind: String = str(def.get("kind", ""))
	match kind:
		"kcal_today":
			return int(floorf(get_today_calories()))
		"sessions_today":
			return _daily_sessions_completed
		_:
			return int(_daily_challenge_progress.get(challenge_id, 0))


## 메인 메뉴 등 UI용: 오늘의 도전 3개 (제목, 현재, 목표, 완료 여부)
func get_daily_challenges_for_ui() -> Array[Dictionary]:
	_sync_daily_challenge_calendar()
	var out: Array[Dictionary] = []
	for cid: String in _daily_challenge_picks:
		var def: Variant = DAILY_CHALLENGE_DEFS.get(cid, null)
		if def == null or typeof(def) != TYPE_DICTIONARY:
			continue
		var target: int = int(def.get("target", 1))
		var cur: int = _daily_challenge_current_for_id(cid)
		out.append({
			"id": cid,
			"title": str(def.get("title", cid)),
			"current": mini(cur, target),
			"target": target,
			"completed": cur >= target,
		})
	return out

func _date_key_from_unix(ts: float) -> String:
	var dt := Time.get_datetime_dict_from_unix_time(int(ts))
	var y: int = int(dt.get("year", 1970))
	var m: int = int(dt.get("month", 1))
	var d: int = int(dt.get("day", 1))
	return "%04d-%02d-%02d" % [y, m, d]

func save_stats() -> void:
	var cfg := ConfigFile.new()
	for k in STATS_KEYS:
		cfg.set_value("stats", k, _punch_counts.get(k, 0))
	cfg.set_value("workout", "last_session_calories", _last_session_calories)
	cfg.set_value("workout", "weight_kg", _weight_kg)
	cfg.set_value("workout", "intensity_factor", _intensity_factor)
	cfg.set_value("workout", "height_cm", _height_cm)
	cfg.set_value("workout", "age", _age)
	cfg.set_value("workout", "gender", _gender)
	cfg.set_value("workout", "daily_kcal_goal", _daily_kcal_goal)
	for date_key in _daily_calories.keys():
		cfg.set_value("daily_calories", date_key, _daily_calories[date_key])
	for date_key in _daily_weight_log.keys():
		cfg.set_value("daily_weight_log", date_key, _daily_weight_log[date_key])
	cfg.set_value("daily_challenges", "date", _daily_challenge_date)
	cfg.set_value("daily_challenges", "sessions_completed", _daily_sessions_completed)
	for i: int in range(_daily_challenge_picks.size()):
		cfg.set_value("daily_challenges", "pick_%d" % i, _daily_challenge_picks[i])
	for k: String in _daily_challenge_progress.keys():
		cfg.set_value("daily_challenge_progress", k, _daily_challenge_progress[k])
	cfg.save(STATS_PATH)


func load_stats() -> void:
	if not FileAccess.file_exists(STATS_PATH):
		return
	var cfg := ConfigFile.new()
	if cfg.load(STATS_PATH) != OK:
		return
	for k in STATS_KEYS:
		if cfg.has_section_key("stats", k):
			_punch_counts[k] = cfg.get_value("stats", k, 0)
	if cfg.has_section_key("workout", "last_session_calories"):
		_last_session_calories = float(cfg.get_value("workout", "last_session_calories", 0.0))
	if cfg.has_section_key("workout", "weight_kg"):
		_weight_kg = maxf(30.0, float(cfg.get_value("workout", "weight_kg", DEFAULT_WEIGHT_KG)))
	if cfg.has_section_key("workout", "intensity_factor"):
		_intensity_factor = clampf(float(cfg.get_value("workout", "intensity_factor", 1.0)), 0.8, 1.3)
	if cfg.has_section_key("workout", "height_cm"):
		_height_cm = clampf(float(cfg.get_value("workout", "height_cm", DEFAULT_HEIGHT_CM)), 120.0, 220.0)
	if cfg.has_section_key("workout", "age"):
		_age = clampi(int(cfg.get_value("workout", "age", DEFAULT_AGE)), 10, 100)
	if cfg.has_section_key("workout", "gender"):
		var g := str(cfg.get_value("workout", "gender", GENDER_MALE))
		if g == GENDER_MALE or g == GENDER_FEMALE or g == GENDER_OTHER:
			_gender = g
	if cfg.has_section_key("workout", "daily_kcal_goal"):
		_daily_kcal_goal = clampf(float(cfg.get_value("workout", "daily_kcal_goal", 0.0)), 0.0, 2000.0)
	if cfg.has_section("daily_calories"):
		for date_key in cfg.get_section_keys("daily_calories"):
			_daily_calories[date_key] = float(cfg.get_value("daily_calories", date_key, 0.0))
	if cfg.has_section("daily_weight_log"):
		for date_key in cfg.get_section_keys("daily_weight_log"):
			_daily_weight_log[date_key] = float(cfg.get_value("daily_weight_log", date_key, 0.0))
	var ch_date: String = ""
	if cfg.has_section_key("daily_challenges", "date"):
		ch_date = str(cfg.get_value("daily_challenges", "date", ""))
	if ch_date == _today_key() and cfg.has_section("daily_challenges"):
		_daily_challenge_date = ch_date
		_daily_sessions_completed = int(cfg.get_value("daily_challenges", "sessions_completed", 0))
		_daily_challenge_picks.clear()
		for i: int in range(3):
			var pk := "pick_%d" % i
			if cfg.has_section_key("daily_challenges", pk):
				_daily_challenge_picks.append(str(cfg.get_value("daily_challenges", pk, "")))
		_daily_challenge_progress.clear()
		if cfg.has_section("daily_challenge_progress"):
			for pk2: String in cfg.get_section_keys("daily_challenge_progress"):
				_daily_challenge_progress[pk2] = int(cfg.get_value("daily_challenge_progress", pk2, 0))
		if _daily_challenge_picks.size() != 3:
			_roll_fresh_daily_challenges()
	else:
		_roll_fresh_daily_challenges()
