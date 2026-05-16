import re

with open("scripts/game_state.gd", "r", encoding="utf-8") as f:
    c = f.read()

# 1. Preloads & Instances
c = c.replace(
    'const _WebcamBridge = preload("res://scripts/game_state/webcam_bridge_internal.gd")',
    'const _WebcamBridge = preload("res://scripts/game_state/webcam_bridge_internal.gd")\n'
    'const _WorkoutTracker = preload("res://scripts/game_state/workout_tracker.gd")\n'
    'const _Shop = preload("res://scripts/game_state/shop.gd")\n'
    'const _DailyChallenges = preload("res://scripts/game_state/daily_challenges.gd")\n'
    'const _Persistence = preload("res://scripts/game_state/persistence.gd")'
)

c = c.replace(
    'var _webcam_bridge = _WebcamBridge.new()',
    'var _webcam_bridge = _WebcamBridge.new()\n'
    'var _workout = _WorkoutTracker.new()\n'
    'var _shop_module = _Shop.new()\n'
    'var _daily = _DailyChallenges.new()'
)

# 2. _init
init_old = """func _init() -> void:
	for k: String in STATS_KEYS:
		_punch_counts[k] = 0
	for k: String in ["punch_l", "punch_r", "upper_l", "upper_r", "squat", "guard"]:
		_session_action_counts[k] = 0
	load_stats()
	_load_display_settings_from_disk()"""

init_new = """func _init() -> void:
	for k: String in STATS_KEYS:
		_punch_counts[k] = 0
	# Session variables are now in _workout
	_workout.set_save_fn(save_stats)
	_shop_module.set_save_fn(save_stats)
	_daily.set_save_fn(save_stats)
	_daily.set_today_calories_fn(_workout.get_today_calories)
	_daily.set_today_key_fn(_workout._today_key)
	load_stats()
	_load_display_settings_from_disk()"""

c = c.replace(init_old, init_new)

# 3. Variables
c = re.sub(r'var _daily_calories: Dictionary = \{\}.*?\n', '', c)
c = re.sub(r'var _daily_weight_log: Dictionary = \{\}.*?\n', '', c)
c = re.sub(r'(?sm)var _session_action_counts.*?var _daily_kcal_goal: float = 0\.0\n', '', c)

# 4. _process
proc_old = """func _process(delta: float) -> void:
	if _session_active:
		_session_elapsed_sec += delta
		if is_guarding:
			_session_calories += KCAL_GUARD_PER_SEC * delta"""
proc_new = """func _process(delta: float) -> void:
	if is_guarding:
		_workout.process_guard_calories(delta)"""
c = c.replace(proc_old, proc_new)

# 5. Functions
funcs_old = r"(?sm)func start_workout_session\(\) -> void:.*?func _date_key_from_unix\(ts: float\) -> String:\n\tvar dt := Time\.get_datetime_dict_from_unix_time\(int\(ts\)\)\n\tvar y: int = int\(dt\.get\(\"year\", 1970\)\)\n\tvar m: int = int\(dt\.get\(\"month\", 1\)\)\n\tvar d: int = int\(dt\.get\(\"day\", 1\)\)\n\treturn \"%04d-%02d-%02d\" % \[y, m, d\]\n"
funcs_new = """func start_workout_session() -> void:
	_workout.start_session()

func record_action_for_calorie(action: String) -> void:
	_workout.record_action(action)

func end_workout_session() -> float:
	var cal = _workout.end_session()
	_sync_daily_challenge_calendar()
	_daily_sessions_completed += 1
	save_stats()
	return cal

func get_last_session_calories() -> float:
	return _workout.get_last_session_calories()

func get_recent_daily_calories(days: int = 30) -> Array[Dictionary]:
	return _workout.get_recent_daily_calories(days)

func get_recent_daily_weight_log(days: int = 30) -> Array[Dictionary]:
	return _workout.get_recent_daily_weight_log(days)

func log_today_weight_kg(kg: float) -> void:
	_workout.log_today_weight_kg(kg)

func get_today_logged_weight_kg() -> float:
	return _workout.get_today_logged_weight_kg()

func get_today_calories() -> float:
	return _workout.get_today_calories()

func set_weight_kg(v: float) -> void:
	_workout.set_weight_kg(v)

func get_weight_kg() -> float:
	return _workout.get_weight_kg()

func set_intensity_factor(v: float) -> void:
	_workout.set_intensity_factor(v)

func get_intensity_factor() -> float:
	return _workout.get_intensity_factor()

func set_height_cm(v: float) -> void:
	_workout.set_height_cm(v)

func get_height_cm() -> float:
	return _workout.get_height_cm()

func set_age(v: int) -> void:
	_workout.set_age(v)

func get_age() -> int:
	return _workout.get_age()

func set_gender(v: String) -> void:
	_workout.set_gender(v)

func get_gender() -> String:
	return _workout.get_gender()

func get_bmi() -> float:
	return _workout.get_bmi()

func get_bmi_category_label() -> String:
	return _workout.get_bmi_category_label()

func get_recommended_daily_kcal_goal() -> float:
	return _workout.get_recommended_daily_kcal_goal()

func has_custom_daily_kcal_goal() -> bool:
	return _workout.has_custom_daily_kcal_goal()

func get_daily_kcal_goal() -> float:
	return _workout.get_daily_kcal_goal()

func set_daily_kcal_goal(kcal: float) -> void:
	_workout.set_daily_kcal_goal(kcal)

func apply_recommended_daily_kcal_goal() -> void:
	_workout.apply_recommended_daily_kcal_goal()

func get_daily_goal_punch_hints() -> Dictionary:
	return _workout.get_daily_goal_punch_hints()

"""
c = re.sub(funcs_old, funcs_new, c)

# 6. _today_key reference (since it's deleted)
c = c.replace('_daily_challenge_date == _today_key()', '_daily_challenge_date == _workout._today_key()')
c = c.replace('_daily_challenge_date = _today_key()', '_daily_challenge_date = _workout._today_key()')

# 7. save_stats
c = c.replace('cfg.set_value("workout", "last_session_calories", _last_session_calories)', 'cfg.set_value("workout", "last_session_calories", _workout.get_last_session_calories())')
c = c.replace('cfg.set_value("workout", "weight_kg", _weight_kg)', 'cfg.set_value("workout", "weight_kg", _workout.get_weight_kg())')
c = c.replace('cfg.set_value("workout", "intensity_factor", _intensity_factor)', 'cfg.set_value("workout", "intensity_factor", _workout.get_intensity_factor())')
c = c.replace('cfg.set_value("workout", "height_cm", _height_cm)', 'cfg.set_value("workout", "height_cm", _workout.get_height_cm())')
c = c.replace('cfg.set_value("workout", "age", _age)', 'cfg.set_value("workout", "age", _workout.get_age())')
c = c.replace('cfg.set_value("workout", "gender", _gender)', 'cfg.set_value("workout", "gender", _workout.get_gender())')
c = c.replace('cfg.set_value("workout", "daily_kcal_goal", _daily_kcal_goal)', 'cfg.set_value("workout", "daily_kcal_goal", _workout._daily_kcal_goal)')

c = c.replace('for date_key: String in _daily_calories.keys():', 'for date_key: String in _workout._daily_calories.keys():\n\t\tcfg.set_value("daily_calories", date_key, _workout._daily_calories[date_key])\n\tfor date_key: String in _workout._daily_weight_log.keys():\n\t\tcfg.set_value("daily_weight_log", date_key, _workout._daily_weight_log[date_key])\n\t#')
c = re.sub(r'\tfor date_key: String in _daily_weight_log\.keys\(\):\n\t\tcfg\.set_value\("daily_weight_log", date_key, _daily_weight_log\[date_key\]\)\n', '', c)

# 8. load_stats
c = c.replace(
    '\t\t_last_session_calories = float(cfg.get_value("workout", "last_session_calories", 0.0))',
    '\t\t_workout._last_session_calories = float(cfg.get_value("workout", "last_session_calories", 0.0))'
)
c = c.replace(
    '\t\t_weight_kg = maxf(30.0, float(cfg.get_value("workout", "weight_kg", 70.0)))',
    '\t\t_workout.set_weight_kg(float(cfg.get_value("workout", "weight_kg", 70.0)))'
)
c = c.replace(
    '\t\t_intensity_factor = clampf(float(cfg.get_value("workout", "intensity_factor", 1.0)), 0.8, 1.3)',
    '\t\t_workout.set_intensity_factor(float(cfg.get_value("workout", "intensity_factor", 1.0)))'
)
c = c.replace(
    '\t\t_height_cm = clampf(float(cfg.get_value("workout", "height_cm", 170.0)), 120.0, 220.0)',
    '\t\t_workout.set_height_cm(float(cfg.get_value("workout", "height_cm", 170.0)))'
)
c = c.replace(
    '\t\t_age = clampi(int(cfg.get_value("workout", "age", 30)), 10, 100)',
    '\t\t_workout.set_age(int(cfg.get_value("workout", "age", 30)))'
)
c = c.replace(
    '\t\t_gender = str(cfg.get_value("workout", "gender", "male"))',
    '\t\t_workout.set_gender(str(cfg.get_value("workout", "gender", "male")))'
)
c = c.replace(
    '\t\t_daily_kcal_goal = clampf(float(cfg.get_value("workout", "daily_kcal_goal", 0.0)), 0.0, 2000.0)',
    '\t\t_workout.set_daily_kcal_goal(float(cfg.get_value("workout", "daily_kcal_goal", 0.0)))'
)

c = c.replace('_daily_calories.clear()', '_workout._daily_calories.clear()')
c = c.replace('_daily_calories[date_key]', '_workout._daily_calories[date_key]')
c = c.replace('_daily_weight_log.clear()', '_workout._daily_weight_log.clear()')
c = c.replace('_daily_weight_log[date_key]', '_workout._daily_weight_log[date_key]')

with open("scripts/game_state.gd", "w", encoding="utf-8") as f:
    f.write(c)

print("Done")
