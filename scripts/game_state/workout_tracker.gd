extends RefCounted
## Workout session tracking, calorie estimation, body profile, daily calorie log.
## Pure computation — no Node/scene-tree dependency.

# Calorie estimation constants (approximate, not medical advice)
const KCAL_PUNCH := 0.42
const KCAL_UPPERCUT := 0.55
const KCAL_SQUAT := 0.30
const KCAL_GUARD_PER_SEC := 0.06
const DEFAULT_WEIGHT_KG := 70.0
const DEFAULT_HEIGHT_CM := 170.0
const DEFAULT_AGE := 30
const GENDER_MALE := "male"
const GENDER_FEMALE := "female"
const GENDER_OTHER := "other"

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
## 0이면 BMI 기반 권장값을 씀. 0 초과면 사용자 지정(저장됨)
var _daily_kcal_goal: float = 0.0

var _daily_calories: Dictionary = {}  # "YYYY-MM-DD" -> float
var _daily_weight_log: Dictionary = {}  # "YYYY-MM-DD" -> float

## Callable supplied by GameState to trigger save after mutations.
var _save_fn: Callable = Callable()


func _init() -> void:
	for k: String in ["punch_l", "punch_r", "upper_l", "upper_r", "squat", "guard"]:
		_session_action_counts[k] = 0


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


# --- Session lifecycle ---

func start_session() -> void:
	_session_active = true
	_session_elapsed_sec = 0.0
	_session_calories = 0.0
	for k: String in _session_action_counts.keys():
		_session_action_counts[k] = 0


func record_action(action: String) -> void:
	if not _session_active:
		return
	if not _session_action_counts.has(action):
		return
	_session_action_counts[action] += 1
	match action:
		"punch_l", "punch_r":
			_session_calories += KCAL_PUNCH
		"upper_l", "upper_r":
			_session_calories += KCAL_UPPERCUT
		"squat":
			_session_calories += KCAL_SQUAT
		_:
			pass


func process_guard_calories(delta: float) -> void:
	if _session_active:
		_session_elapsed_sec += delta
		_session_calories += KCAL_GUARD_PER_SEC * delta


func end_session() -> float:
	if not _session_active:
		return _last_session_calories
	_session_active = false
	var minutes := maxf(_session_elapsed_sec / 60.0, 0.1)
	var total_actions: int = 0
	for k: String in _session_action_counts.keys():
		total_actions += int(_session_action_counts[k])
	var density := float(total_actions) / minutes
	# MET 기반 추정: 복싱 피트니스(중강도~고강도) 범위를 단순화
	var met := clampf(5.5 + 0.08 * (density - 30.0), 5.5, 11.0)
	var met_kcal := met * 3.5 * _weight_kg / 200.0 * minutes
	# 동작 기반 값(기존)과 MET 기반 값을 블렌딩해 과소/과대 추정 완화
	var profile_factor := _get_profile_factor()
	_last_session_calories = maxf(met_kcal, _session_calories * 0.8) * _intensity_factor * profile_factor
	_add_today_calories(_last_session_calories)
	return _last_session_calories


func is_session_active() -> bool:
	return _session_active


func get_last_session_calories() -> float:
	return _last_session_calories

# --- Weight log ---

func get_recent_daily_calories(days: int = 30) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var count := maxi(1, days)
	for i: int in range(count - 1, -1, -1):
		var ts := Time.get_unix_time_from_system() - (86400 * i)
		var date_key := _date_key_from_unix(ts)
		var c: float = float(_daily_calories.get(date_key, 0.0))
		result.append({"date": date_key, "calories": c})
	return result


func get_recent_daily_weight_log(days: int = 30) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var count := maxi(1, days)
	for i: int in range(count - 1, -1, -1):
		var ts := Time.get_unix_time_from_system() - (86400 * i)
		var date_key := _date_key_from_unix(ts)
		var w: float = float(_daily_weight_log.get(date_key, 0.0))
		result.append({"date": date_key, "weight": w})
	return result


func get_today_calories() -> float:
	return float(_daily_calories.get(_today_key(), 0.0))


## 오늘 날짜에 체중 기록(kg). 칼로리 계산용 프로필 체중도 같이 갱신.
func log_today_weight_kg(kg: float) -> void:
	if kg <= 0.0:
		return
	kg = clampf(kg, 30.0, 180.0)
	_daily_weight_log[_today_key()] = kg
	set_weight_kg(kg)


func get_today_logged_weight_kg() -> float:
	return float(_daily_weight_log.get(_today_key(), 0.0))


# --- Body profile ---

func set_weight_kg(v: float) -> void:
	if v <= 0.0:
		_weight_kg = DEFAULT_WEIGHT_KG
	else:
		_weight_kg = clampf(v, 30.0, 180.0)
	_save()

func get_weight_kg() -> float:
	return _weight_kg

func set_intensity_factor(v: float) -> void:
	_intensity_factor = clampf(v, 0.8, 1.3)
	_save()

func get_intensity_factor() -> float:
	return _intensity_factor

func set_height_cm(v: float) -> void:
	if v <= 0.0:
		_height_cm = DEFAULT_HEIGHT_CM
	else:
		_height_cm = clampf(v, 120.0, 220.0)
	_save()

func get_height_cm() -> float:
	return _height_cm

func set_age(v: int) -> void:
	if v <= 0:
		_age = DEFAULT_AGE
	else:
		_age = clampi(v, 10, 100)
	_save()

func get_age() -> int:
	return _age

func set_gender(v: String) -> void:
	if v != GENDER_MALE and v != GENDER_FEMALE and v != GENDER_OTHER:
		_gender = GENDER_MALE
	else:
		_gender = v
	_save()

func get_gender() -> String:
	return _gender


# --- BMI / BMR ---

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


# --- Daily kcal goal ---

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
	_save()


## 권장 식으로 목표를 덮어쓰고 저장 (BMI·프로필 변경 후 다시 맞출 때)
func apply_recommended_daily_kcal_goal() -> void:
	_daily_kcal_goal = get_recommended_daily_kcal_goal()
	_save()


## 오늘 목표 대비 남은 칼로리를 동작별 상수로 나눈 이론상 횟수 (세션 MET 보정 없음)
func get_daily_goal_punch_hints() -> Dictionary:
	var goal: float = get_daily_kcal_goal()
	var today: float = get_today_calories()
	var rem: float = maxf(0.0, goal - today)
	var avg_three: float = (KCAL_PUNCH + KCAL_PUNCH + KCAL_UPPERCUT) / 3.0
	if rem <= 0.0001:
		return {
			"remaining": 0.0,
			"goal": goal,
			"today": today,
			"punch_only": 0,
			"upper_only": 0,
			"guard_hold_sec": 0,
			"mixed_same": 0,
		}
	return {
		"remaining": rem,
		"goal": goal,
		"today": today,
		"punch_only": int(ceilf(rem / KCAL_PUNCH)),
		"upper_only": int(ceilf(rem / KCAL_UPPERCUT)),
		"guard_hold_sec": int(ceilf(rem / KCAL_GUARD_PER_SEC)),
		"mixed_same": int(ceilf(rem / avg_three)),
	}


# --- Internal ---

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

func _date_key_from_unix(ts: float) -> String:
	var dt := Time.get_datetime_dict_from_unix_time(int(ts))
	var y: int = int(dt.get("year", 1970))
	var m: int = int(dt.get("month", 1))
	var d: int = int(dt.get("day", 1))
	return "%04d-%02d-%02d" % [y, m, d]


func reset_all() -> void:
	_session_active = false
	_session_elapsed_sec = 0.0
	_session_calories = 0.0
	_last_session_calories = 0.0
	_weight_kg = DEFAULT_WEIGHT_KG
	_intensity_factor = 1.0
	_height_cm = DEFAULT_HEIGHT_CM
	_age = DEFAULT_AGE
	_gender = GENDER_MALE
	_daily_kcal_goal = 0.0
	_daily_calories.clear()
	_daily_weight_log.clear()
	for k: String in _session_action_counts.keys():
		_session_action_counts[k] = 0
