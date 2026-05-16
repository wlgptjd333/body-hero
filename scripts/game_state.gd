extends Node
## 전역 게임 상태 (AutoLoad 싱글톤)
## 접근: GameState.stamina, GameState.consume_stamina(4) 등

signal stamina_changed(new_stamina: float)
signal player_hp_changed(new_hp: float)

const _WebcamBridge = preload("res://scripts/game_state/webcam_bridge_internal.gd")
const _WorkoutTracker = preload("res://scripts/game_state/workout_tracker.gd")
const _Shop = preload("res://scripts/game_state/shop.gd")
const _DailyChallenges = preload("res://scripts/game_state/daily_challenges.gd")
const _Persistence = preload("res://scripts/game_state/persistence.gd")
const _Achievements = preload("res://scripts/game_state/achievements.gd")
const _Difficulty = preload("res://scripts/game_state/difficulty.gd")
const _StageProgress = preload("res://scripts/game_state/stage_progress.gd")
const _BossManager = preload("res://scripts/game_state/boss_manager.gd")
const _WebcamSettings = preload("res://scripts/game_state/webcam_settings.gd")
const _Training = preload("res://scripts/game_state/training.gd")
const _UpgradeSystem = preload("res://scripts/game_state/upgrade_system.gd")

# 플레이어 (최대 체력·스태미너·초당 회복은 업그레이드 반영 후 `refresh_combat_derived_from_upgrades`가 갱신)
var player_hp: float = BASE_PLAYER_MAX_HP
var player_max_hp: float = BASE_PLAYER_MAX_HP
var stamina: float = BASE_STAMINA_MAX
var stamina_max: float = BASE_STAMINA_MAX
var stamina_passive_recover_per_sec: float = BASE_STAMINA_PASSIVE_RECOVER

# 스태미너 소모량 (피트니스 복싱 밸런스). 잽:어퍼 ≈ 1:2 유지
const STAMINA_PUNCH := 5
const STAMINA_UPPERCUT := 10
const STAMINA_SQUAT := 5

# Exported constants for external callers (values mirrored from modules)
const DIFFICULTY_EASY := "easy"
const DIFFICULTY_NORMAL := "normal"
const DIFFICULTY_HARD := "hard"
const BASE_PLAYER_MAX_HP := 200.0
const BASE_STAMINA_MAX := 100.0
const BASE_STAMINA_PASSIVE_RECOVER := 10.0
const UPGRADE_HP_PER_STEP := 5.0
const UPGRADE_STAMINA_PER_STEP := 5.0
const UPGRADE_RECOVER_PER_STEP := 0.5
const UPGRADE_MAX_STEPS := 20
const ML_SPEED_PROFILE_VALUES: Array[String] = ["balanced", "fast_react", "fast_combo", "max_speed"]
const CAMERA_BACKEND_VALUES := ["auto", "dshow", "msmf", "default"]

# 가드: 플레이어가 가드 중이면 true
var is_guarding: bool = false
var _has_guard_mastery: bool = false
var _demo_mode: bool = false

# 칼로리 추정치 (게임 내 상대 지표)
const KCAL_PUNCH := 0.42
const KCAL_UPPERCUT := 0.55
const KCAL_DODGE := 0.30
const KCAL_GUARD_PER_SEC := 0.06
const DEFAULT_WEIGHT_KG := 70.0
const DEFAULT_HEIGHT_CM := 170.0
const DEFAULT_AGE := 30
const GENDER_MALE := "male"
const GENDER_FEMALE := "female"
const GENDER_OTHER := "other"

# 통계: 가드, 스쿼트, 왼/오 펀치, 왼/오 어퍼 (누적, 저장됨)
const STATS_KEYS := ["guard", "squat", "punch_l", "punch_r", "upper_l", "upper_r"]
var _punch_counts: Dictionary = {}  # key -> int (현재 세션 + 로드된 누적)

# DAILY_CHALLENGE_DEFS/POOL_IDS moved to daily_challenges.gd
# STAGE_DEFS moved to stage_progress.gd
# Achievements moved to achievements.gd
# Shop items moved to shop.gd
# Boss buff options moved to boss_manager.gd
# Camera/display settings moved to webcam_settings.gd
# Difficulty moved to difficulty.gd
# Upgrade/sweat system moved to upgrade_system.gd
# Training mode moved to training.gd



# Stage progress / clear time / difficulty moved to stage_progress.gd and difficulty.gd

# 업적/상점/보스 moved to respective modules (achievements.gd, shop.gd, boss_manager.gd)

var _webcam_bridge = _WebcamBridge.new()
var _workout = _WorkoutTracker.new()
var _shop_module = _Shop.new()
var _daily = _DailyChallenges.new()
var _achievements = _Achievements.new()
var _difficulty = _Difficulty.new()
var _stage_progress = _StageProgress.new()
var _boss = _BossManager.new()
var _webcam_settings = _WebcamSettings.new()
var _training = _Training.new()
var _upgrade_system = _UpgradeSystem.new()

const PREWARM_WEBCAM_ML_BRIDGE := true
const PREWARM_WEBCAM_ML_DELAY_SEC := 0.0

func _init() -> void:
	for k: String in STATS_KEYS:
		_punch_counts[k] = 0
	_workout.set_save_fn(save_stats)
	_shop_module.set_save_fn(save_stats)
	_daily.set_save_fn(save_stats)
	_daily.set_today_calories_fn(_workout.get_today_calories)
	_daily.set_today_key_fn(_workout._today_key)
	_achievements.set_save_fn(save_stats)
	_difficulty.set_save_fn(save_stats)
	_stage_progress.set_save_fn(save_stats)
	_boss.set_save_fn(save_stats)
	_upgrade_system.set_save_fn(save_stats)
	_upgrade_system.set_on_refresh(func(p_max_hp: float, p_sta_max: float, p_rec: float) -> void:
		player_max_hp = p_max_hp
		stamina_max = p_sta_max
		stamina_passive_recover_per_sec = p_rec
		var prev_hp: float = player_hp
		player_hp = minf(player_hp, player_max_hp)
		var prev_sta: float = stamina
		stamina = minf(stamina, stamina_max)
		if player_hp != prev_hp:
			player_hp_changed.emit(player_hp)
		if stamina != prev_sta:
			stamina_changed.emit(stamina)
		)
	_webcam_settings.set_bridgify_fn(shutdown_webcam_ml_bridge)
	load_stats()
	_webcam_settings.load_from_disk()


func _ready() -> void:
	call_deferred("_apply_saved_window_size_deferred")
	call_deferred("_connect_close_requested_for_webcam_bridge")
	_webcam_settings.set_webcam_bridge(_webcam_bridge)
	if PREWARM_WEBCAM_ML_BRIDGE:
		call_deferred("_defer_prewarm_webcam_ml_bridge")


func _defer_prewarm_webcam_ml_bridge() -> void:
	await get_tree().create_timer(PREWARM_WEBCAM_ML_DELAY_SEC).timeout
	for _i: int in range(2):
		await get_tree().process_frame
	if not has_webcam_ml_runtime_files():
		return
	ensure_webcam_ml_bridge(true)


func get_punch_count(action: String) -> int:
	return _punch_counts.get(action, 0)

func get_all_punch_counts() -> Dictionary:
	return _punch_counts.duplicate()

func add_punch_count(action: String) -> void:
	if action in _punch_counts:
		_punch_counts[action] += 1
		_daily.sync_calendar()
		_daily.bump_for_punch_action(action)
		save_stats()

func record_guard() -> void:
	if "guard" in _punch_counts:
		_punch_counts["guard"] += 1
		_daily.sync_calendar()
		_daily.bump_for_kind("guards")
		save_stats()

func reset_punch_counts() -> void:
	# 게임 시작 시 현재 세션만 리셋하지 않고, 누적 통계는 유지 (통계 패널에서만 누적 표시)
	pass


## 스테이지 클리어(KO) 시 호출. 짧을수록 좋은 기록으로 최고 기록 갱신
func record_stage_clear_time(seconds: float) -> void:
	_stage_progress.record_clear_time(seconds)


func get_best_stage_clear_sec() -> float:
	return _stage_progress.get_best_clear_sec()


func get_last_stage_clear_sec() -> float:
	return _stage_progress.get_last_clear_sec()


func get_last_played_stage_id() -> String:
	return _stage_progress.get_last_played_id()


func set_last_played_stage_id(stage_id: String) -> void:
	_stage_progress.set_last_played_id(stage_id)


func get_stage_clear_history():
	return _stage_progress.get_clear_history()


func format_stage_clear_time(seconds: float) -> String:
	return _stage_progress.format_clear_time(seconds)

func set_guarding(on: bool) -> void:
	is_guarding = on

func has_guard_mastery() -> bool:
	return _has_guard_mastery

func set_has_guard_mastery(v: bool) -> void:
	_has_guard_mastery = v

func get_guard_damage_reduction_factor() -> float:
	return 1.0 if _has_guard_mastery else 0.8

func _process(delta: float) -> void:
	if is_guarding:
		_workout.process_guard_calories(delta)
	# 가드 중에는 스태미너 초당 회복 없음 (막기 성공 시 `apply_guard_block_success`에서 1초 분량 회복)
	if not is_guarding:
		if stamina < stamina_max:
			var prev_stamina: float = stamina
			stamina = minf(stamina_max, stamina + stamina_passive_recover_per_sec * delta)
			if stamina != prev_stamina:
				stamina_changed.emit(stamina)

func consume_stamina(amount: float) -> bool:
	if stamina < amount:
		return false
	stamina -= amount
	stamina_changed.emit(stamina)
	return true


## 적 공격을 가드로 막았을 때: 스태미너를 초당 회복과 비례한 양만큼 한 번 회복
func apply_guard_block_success() -> void:
	var prev_stamina: float = stamina
	stamina = minf(stamina_max, stamina + (stamina_passive_recover_per_sec * 2.0))
	if stamina != prev_stamina:
		stamina_changed.emit(stamina)


## 스쿼트(기존 회피 입력) 시 즉시 HP를 최대치의 일정 비율만큼 회복.
func apply_squat_heal(heal_ratio: float = 0.10) -> void:
	var r: float = clampf(heal_ratio, 0.0, 1.0)
	var amount: float = player_max_hp * r
	var prev_hp: float = player_hp
	player_hp = minf(player_max_hp, player_hp + amount)
	if player_hp != prev_hp:
		player_hp_changed.emit(player_hp)


func apply_player_damage(amount: float) -> void:
	if amount <= 0.0:
		return
	var prev_hp: float = player_hp
	player_hp = maxf(0.0, player_hp - amount)
	if player_hp != prev_hp:
		player_hp_changed.emit(player_hp)

func get_stamina_ratio() -> float:
	if stamina_max <= 0.0:
		return 1.0
	return clampf(stamina / stamina_max, 0.0, 1.0)

func get_player_hp_ratio() -> float:
	if player_max_hp <= 0.0:
		return 1.0
	return clampf(player_hp / player_max_hp, 0.0, 1.0)


func refresh_combat_derived_from_upgrades() -> void:
	_upgrade_system._recalc_and_notify()


func get_sweat() -> int:
	return _upgrade_system.get_sweat()

func add_sweat(amount: int) -> void:
	_upgrade_system.add_sweat(amount)


func set_sweat(amount: int) -> void:
	_upgrade_system.set_sweat(amount)

func get_upgrade_hp_level() -> int:
	return _upgrade_system.get_hp_level()

func get_upgrade_stamina_level() -> int:
	return _upgrade_system.get_stamina_level()

func get_upgrade_recover_level() -> int:
	return _upgrade_system.get_recover_level()

func try_purchase_upgrade(kind: String) -> bool:
	var success: bool = _upgrade_system.try_purchase(kind)
	if success:
		var hp_bonus: float = 5.0
		var sta_bonus: float = 5.0
		match kind:
			"hp":
				var prev_hp: float = player_hp
				player_hp = minf(player_hp + hp_bonus, player_max_hp)
				if player_hp != prev_hp:
					player_hp_changed.emit(player_hp)
			"stamina":
				var prev_sta: float = stamina
				stamina = minf(stamina + sta_bonus, stamina_max)
				if stamina != prev_sta:
					stamina_changed.emit(stamina)
	return success

func reset_all_upgrades(refund_sweat: bool = true) -> bool:
	return _upgrade_system.reset_all(refund_sweat)


func start_workout_session() -> void:
	_workout.start_session()

func record_action_for_calorie(action: String) -> void:
	_workout.record_action(action)

func end_workout_session() -> float:
	var cal = _workout.end_session()
	_daily.sync_calendar()
	_daily.increment_sessions()
	save_stats()
	return cal

func get_last_session_calories() -> float:
	return _workout.get_last_session_calories()

func get_recent_daily_calories(days: int = 30):
	return _workout.get_recent_daily_calories(days)


func get_recent_daily_weight_log(days: int = 30):
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


func get_daily_challenges_for_ui() -> Array[Dictionary]:
	return _daily.get_challenges_for_ui()



func save_stats() -> void:
	var wd: Dictionary = {}
	wd["last_session_calories"] = _workout.get_last_session_calories()
	wd["weight_kg"] = _workout.get_weight_kg()
	wd["intensity_factor"] = _workout.get_intensity_factor()
	wd["height_cm"] = _workout.get_height_cm()
	wd["age"] = _workout.get_age()
	wd["gender"] = _workout.get_gender()
	wd["daily_kcal_goal"] = _workout._daily_kcal_goal
	wd["daily_calories"] = _workout._daily_calories
	wd["daily_weight_log"] = _workout._daily_weight_log

	_Persistence.save_all(
		{"punch_counts": _punch_counts, "stats_keys": STATS_KEYS},
		wd,
		_daily.get_save_data(),
		_shop_module.get_save_data(),
		_achievements.get_save_data(),
		_difficulty.get_save_data(),
		_stage_progress.get_save_data(),
		_boss.get_save_data(),
		_upgrade_system.get_save_data(),
	)


func load_stats() -> void:
	var data: Dictionary = _Persistence.load_all(STATS_KEYS)
	if data.is_empty():
		_upgrade_system._recalc_and_notify()
		return

	if data.has("punch_counts"):
		_punch_counts = data["punch_counts"]

	var wd: Dictionary = data.get("workout", {})
	_workout._last_session_calories = wd.get("last_session_calories", 0.0)
	_workout.set_weight_kg(wd.get("weight_kg", 70.0))
	_workout.set_intensity_factor(wd.get("intensity_factor", 1.0))
	_workout.set_height_cm(wd.get("height_cm", 170.0))
	_workout.set_age(wd.get("age", 30))
	_workout.set_gender(wd.get("gender", "male"))
	_workout.set_daily_kcal_goal(wd.get("daily_kcal_goal", 0.0))
	_workout._daily_calories = wd.get("daily_calories", {})
	_workout._daily_weight_log = wd.get("daily_weight_log", {})

	var cd: Dictionary = data.get("challenges", {})
	_daily.set_date(cd.get("date", ""))
	_daily.set_sessions_completed(cd.get("sessions_completed", 0))
	var picks: Array[String] = cd.get("picks", [])
	if cd.get("picks_invalid", false) or picks.size() != 3:
		_daily.sync_calendar()
	else:
		_daily.set_picks(picks)
	_daily.set_progress(cd.get("progress", {}))

	var spd: Dictionary = data.get("stage_progress", {})
	_stage_progress.load_save_data(spd)

	if data.has("upgrade"):
		_upgrade_system.load_save_data(data["upgrade"])
	if data.has("difficulty"):
		_difficulty.load_save_data(data["difficulty"])
	if data.has("achievements"):
		_achievements.load_save_data(data["achievements"])
	if data.has("shop"):
		var sd: Dictionary = data["shop"]
		_shop_module._owned_items = sd.get("owned", {})
		_shop_module._inventory = sd.get("inventory", {})
		_shop_module.equip_glove_skin(sd.get("equipped_glove_skin", ""))
		_shop_module.equip_hit_effect(sd.get("equipped_hit_effect", ""))
	if data.has("boss"):
		_boss.load_save_data(data["boss"])


# --- 창 크기·웹캠 (위임) ---


func reload_display_settings_from_disk() -> void:
	_webcam_settings.load_from_disk()


func _apply_saved_window_size_deferred() -> void:
	_webcam_settings.apply_saved_window_size()


func save_display_settings(
	width: int,
	height: int,
	camera_index: int,
	camera_backend: String = "auto",
	ml_speed_profile: String = "",
	roi_mode: bool = false,
	center_zone_margin: float = 0.3,
	skip_guard_single: bool = false,
	full_body_squat: bool = false,
) -> void:
	_webcam_settings.save_to_disk(width, height, camera_index, camera_backend, ml_speed_profile, roi_mode, center_zone_margin, skip_guard_single, full_body_squat)


func get_camera_index() -> int:
	return _webcam_settings.get_camera_index()

func get_camera_backend() -> String:
	return _webcam_settings.get_camera_backend()

func get_ml_speed_profile() -> String:
	return _webcam_settings.get_ml_speed_profile()

func get_roi_mode() -> bool:
	return _webcam_settings.get_roi_mode()

func get_center_zone_margin() -> float:
	return _webcam_settings.get_center_zone_margin()

func get_skip_guard_single() -> bool:
	return _webcam_settings.get_skip_guard_single()

func get_full_body_squat() -> bool:
	return _webcam_settings.get_full_body_squat()

func get_window_mode() -> int:
	return _webcam_settings.get_window_mode()

func set_window_mode(mode: int) -> void:
	_webcam_settings.set_window_mode(mode)


## 복싱 메인에서 호출: 이미 같은 인덱스·백엔드로 떠 있으면 유지(다시하기 시 끊김 방지).
func ensure_webcam_ml_bridge(auto_launch: bool) -> void:
	if not auto_launch:
		return
	if not has_webcam_ml_runtime_files():
		push_warning("웹캠 ML: 스크립트 없음 — %s" % get_udp_send_webcam_ml_script_path())
		return
	reload_display_settings_from_disk()
	_webcam_bridge.ensure(
		auto_launch,
		get_camera_index(),
		get_camera_backend(),
		get_ml_speed_profile(),
		get_roi_mode(),
		get_center_zone_margin(),
		get_skip_guard_single(),
		get_full_body_squat(),
		resolve_python_executable_for_ml(),
		get_udp_send_webcam_ml_script_path(),
	)


func get_webcam_ml_bridge_pid() -> int:
	return _webcam_bridge.get_pid()


func is_webcam_ml_bridge_running() -> bool:
	return _webcam_bridge.is_running()


func shutdown_webcam_ml_bridge() -> void:
	_webcam_bridge.shutdown()


func _connect_close_requested_for_webcam_bridge() -> void:
	var root := get_tree().root
	if root and not root.close_requested.is_connected(_on_root_close_requested_shutdown_webcam):
		root.close_requested.connect(_on_root_close_requested_shutdown_webcam)


func _on_root_close_requested_shutdown_webcam() -> void:
	shutdown_webcam_ml_bridge()


func get_tools_absolute_dir() -> String:
	if OS.has_feature("editor"):
		return ProjectSettings.globalize_path("res://tools")
	return OS.get_executable_path().get_base_dir().path_join("tools")


func get_venv_python_executable() -> String:
	var tools := get_tools_absolute_dir()
	if OS.get_name() == "Windows":
		return tools.path_join("venv_ml").path_join("Scripts").path_join("python.exe")
	return tools.path_join("venv_ml").path_join("bin").path_join("python")


## venv_ml 우선, 없으면 BODY_HERO_PYTHON_EXE, 없으면 PATH의 python (Windows: python.exe).
func resolve_python_executable_for_ml() -> String:
	var env_path := OS.get_environment("BODY_HERO_PYTHON_EXE").strip_edges()
	if env_path != "":
		if FileAccess.file_exists(env_path):
			return env_path
		push_warning("BODY_HERO_PYTHON_EXE 가 가리키는 파일이 없습니다: %s" % env_path)
	var venv_py := get_venv_python_executable()
	if FileAccess.file_exists(venv_py):
		return venv_py
	if OS.get_name() == "Windows":
		return "python.exe"
	return "python3"


func has_webcam_ml_runtime_files() -> bool:
	var script := get_udp_send_webcam_ml_script_path()
	return FileAccess.file_exists(script)


func get_udp_send_webcam_ml_script_path() -> String:
	return get_tools_absolute_dir().path_join("udp_send_webcam_ml.py")


func get_list_cameras_script_path() -> String:
	return get_tools_absolute_dir().path_join("list_cameras.py")


func set_training_mode(on: bool) -> void:
	_training.set_training(on)

func is_training_mode() -> bool:
	return _training.is_active()


# --- 난이도 (위임) ---

func get_difficulty() -> String:
	return _difficulty.get_difficulty()

func set_difficulty(d: String) -> void:
	_difficulty.set_d(d)

func get_difficulty_label() -> String:
	return _difficulty.get_label()

func get_difficulty_enemy_stat_mul() -> float:
	return _difficulty.get_enemy_stat_mul()


# --- 별/기록 (위임) ---

func get_stage_stars(stage_id: String) -> int:
	return _stage_progress.get_stars(stage_id)

func get_all_stage_stars() -> Dictionary:
	return _stage_progress.get_all_stars()

func record_stage_stars(stage_id: String, stars: int) -> void:
	_stage_progress.record_stars(stage_id, stars)

func evaluate_stage_stars(clear_sec: float, max_combo: int, damage_taken: float) -> int:
	return _stage_progress.evaluate_stars(clear_sec, max_combo, damage_taken)

func get_stage_record(stage_id: String) -> Dictionary:
	return _stage_progress.get_record(stage_id)

func update_stage_record(stage_id: String, clear_sec: float, max_combo: int, damage_taken: float) -> void:
	_stage_progress.update_record(stage_id, clear_sec, max_combo, damage_taken)


# --- 업적 시스템 (위임) ---

func get_achievement_defs() -> Dictionary:
	return _achievements.get_defs()

func is_achievement_unlocked(id: String) -> bool:
	return _achievements.is_unlocked(id)

func get_achievement_progress(id: String) -> int:
	return _achievements.get_progress(id)

func unlock_achievement(id: String) -> bool:
	return _achievements.unlock(id)

func bump_achievement_progress(id: String, amount: int = 1) -> void:
	_achievements.bump(id, amount)

func check_and_unlock_achievements_after_session(clear_sec: float, max_combo: int, damage_taken: float, is_clear: bool) -> Array[String]:
	return _achievements.check_after_session(clear_sec, max_combo, damage_taken, is_clear)


# --- 상점 시스템 ---

func get_shop_items() -> Dictionary:
	return _shop_module.get_shop_items()

func get_shop_inventory() -> Dictionary:
	return _shop_module.get_shop_inventory()

func is_item_owned(item_id: String) -> bool:
	return _shop_module.is_item_owned(item_id)

func get_item_inventory_count(item_id: String) -> int:
	return _shop_module.get_item_inventory_count(item_id)

func equip_glove_skin(skin_id: String) -> bool:
	return _shop_module.equip_glove_skin(skin_id)

func get_equipped_glove_skin() -> String:
	return _shop_module.get_equipped_glove_skin()

func get_hit_effect_themes() -> Dictionary:
	return _shop_module.get_hit_effect_themes()

func get_hit_effect_theme_colors(theme_id: String) -> Dictionary:
	return _shop_module.get_hit_effect_theme_colors(theme_id)

func get_equipped_hit_effect() -> String:
	return _shop_module.get_equipped_hit_effect()

func equip_hit_effect(effect_id: String) -> bool:
	return _shop_module.equip_hit_effect(effect_id)

func try_purchase_item(item_id: String) -> bool:
	var sweat_val: Array[int] = [_upgrade_system.get_sweat()]
	var success = _shop_module.try_purchase_item(item_id, sweat_val)
	if success:
		_upgrade_system.set_sweat(sweat_val[0])
	return success

func consume_buff_for_session() -> Dictionary:
	return _shop_module.consume_buff_for_session()


# --- 보스 스테이지 (위임) ---

func get_boss_phase() -> int:
	return _boss.get_phase()

func set_boss_phase(p: int) -> void:
	_boss.set_phase(p)

func get_boss_buffs_selected():
	return _boss.get_buffs_selected()


func get_boss_buff_options():
	return _boss.get_options()


func add_boss_buff(buff: Dictionary) -> void:
	_boss.add_buff(buff)


func get_stage_defs():
	return _stage_progress.get_defs()

func get_stage_def(stage_id: String) -> Dictionary:
	return _stage_progress.get_def(stage_id)

func get_next_stage_id(current_stage_id: String) -> String:
	return _stage_progress.get_next_id(current_stage_id)

func get_next_stage_scene(current_stage_id: String) -> String:
	return _stage_progress.get_next_scene(current_stage_id)

func has_next_stage(stage_id: String) -> bool:
	return _stage_progress.has_next(stage_id)


func is_demo_mode() -> bool:
	return _demo_mode


func enter_demo_mode(sweat_amount: int = 999) -> void:
	reset_all_data()
	_demo_mode = true
	add_sweat(sweat_amount)


func reset_all_data() -> void:
	_demo_mode = false
	_workout.reset_all()
	_shop_module.reset_all()
	_daily.reset_all()
	_achievements.reset_all()
	_stage_progress.reset_all()
	_boss.reset_all()
	_upgrade_system.reset_all(true)
	_upgrade_system.set_sweat(0)
	_punch_counts = {}
	for k: String in STATS_KEYS:
		_punch_counts[k] = 0
	player_hp = BASE_PLAYER_MAX_HP
	player_max_hp = BASE_PLAYER_MAX_HP
	stamina = BASE_STAMINA_MAX
	stamina_max = BASE_STAMINA_MAX
	stamina_passive_recover_per_sec = BASE_STAMINA_PASSIVE_RECOVER
	is_guarding = false
	_has_guard_mastery = false
	_Persistence.delete_save()
	stamina_changed.emit(stamina)
	player_hp_changed.emit(player_hp)
