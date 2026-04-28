extends Node
## 전역 게임 상태 (AutoLoad 싱글톤)
## 접근: GameState.stamina, GameState.consume_stamina(4) 등

# 플레이어 (최대 체력·스태미너·초당 회복은 업그레이드 반영 후 `refresh_combat_derived_from_upgrades`가 갱신)
var player_hp: float = 200.0
var player_max_hp: float = 200.0
var stamina: float = 100.0
var stamina_max: float = 100.0
## 가만히 있을 때 초당 스태미너 회복량 (업그레이드 반영)
var stamina_passive_recover_per_sec: float = 10.0

# 스태미너 소모량 (피트니스 복싱 밸런스). 잽:어퍼 ≈ 1:2 유지
const STAMINA_PUNCH := 3
const STAMINA_UPPERCUT := 6

# 업그레이드(스웨트) — 스테이지 클리어 시 +1, 각 업그레이드 1 소모
const BASE_PLAYER_MAX_HP := 200.0
const BASE_STAMINA_MAX := 100.0
const BASE_STAMINA_PASSIVE_RECOVER := 10.0
const UPGRADE_MAX_STEPS := 20
const UPGRADE_HP_PER_STEP := 5.0
const UPGRADE_STAMINA_PER_STEP := 5.0
const UPGRADE_RECOVER_PER_STEP := 0.5

var _sweat: int = 0
var _upgrade_hp: int = 0
var _upgrade_stamina: int = 0
var _upgrade_recover: int = 0

# 가드 막기 성공 시 HP 소모 (방어 대가, 매우 소량)
const HP_CHIP_ON_GUARD_BLOCK := 1.5

# 가드: 플레이어가 가드 중이면 true
var is_guarding: bool = false

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

# 통계: 가드, 왼/오 펀치, 왼/오 어퍼 (누적, 저장됨)
const STATS_KEYS := ["guard", "punch_l", "punch_r", "upper_l", "upper_r"]
var _punch_counts: Dictionary = {}  # key -> int (현재 세션 + 로드된 누적)
var _daily_calories: Dictionary = {}  # "YYYY-MM-DD" -> float
var _daily_weight_log: Dictionary = {}  # "YYYY-MM-DD" -> float (통계 패널에서 직접 기록)

# 일일 도전과제 (날짜가 바뀌면 과제 3개 재추첨, 진행도 초기화)
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


func _migrate_daily_challenge_id(challenge_id: String) -> String:
	match challenge_id:
		"jabs_25":
			return "punches_25"
		"hooks_12":
			return "punches_12"
		_:
			return challenge_id


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

# 타임어택: 메인 스테이지 KO까지 경과 시간(일시정지 제외). -1 = 기록 없음
const STAGE_CLEAR_HISTORY_MAX := 15
var _best_stage_clear_sec: float = -1.0
var _last_stage_clear_sec: float = -1.0
var _stage_clear_history: Array[float] = []

const STATS_PATH := "user://body_hero_stats.cfg"
const DISPLAY_SETTINGS_PATH := "user://display_settings.cfg"
const DISPLAY_MIN_W := 640
const DISPLAY_MIN_H := 360

## 저장된 창 크기(0이면 기본값 유지). 설정 패널에서 적용 시 갱신.
var _saved_window_width: int = 0
var _saved_window_height: int = 0
## OpenCV 카메라 인덱스 (USB 웹캠은 보통 1 이상).
var _camera_index: int = 0
## udp_send_webcam_ml.py 의 --camera-backend (auto|dshow|msmf|default).
var _camera_backend: String = "auto"
## udp_send_webcam_ml.py 의 --profile (balanced|fast_react|fast_combo|max_speed).
var _ml_speed_profile: String = "max_speed"
## 복싱 씬을 나가도 유지: 인덱스·백엔드·프로필 같으면 재시작 시 프로세스 재사용.
var _webcam_ml_bridge_pid: int = -1
var _webcam_ml_launched_camera: int = -999
var _webcam_ml_launched_backend: String = ""
var _webcam_ml_launched_profile: String = ""

const CAMERA_BACKEND_VALUES := ["auto", "dshow", "msmf", "default"]
## tools/udp_send_webcam_ml.py 의 --profile 과 동일한 값만 허용.
const ML_SPEED_PROFILE_VALUES: Array[String] = ["balanced", "fast_react", "fast_combo", "max_speed"]

## true면 메뉴 대기 중 웹캠 ML을 미리 띄웁니다.
const PREWARM_WEBCAM_ML_BRIDGE := true
## Godot·씬 첫 로드와 동시에 Python을 띄우면 디스크 경쟁으로 TensorFlow 첫 기동이 수배로 느려질 수 있어 지연합니다.
const PREWARM_WEBCAM_ML_DELAY_SEC := 8.0

func _init() -> void:
	for k in STATS_KEYS:
		_punch_counts[k] = 0
	for k in ["punch_l", "punch_r", "upper_l", "upper_r", "dodge", "guard"]:
		_session_action_counts[k] = 0
	load_stats()
	_load_display_settings_from_disk()


func _ready() -> void:
	call_deferred("_apply_saved_window_size_deferred")
	call_deferred("_connect_close_requested_for_webcam_bridge")
	if PREWARM_WEBCAM_ML_BRIDGE:
		call_deferred("_defer_prewarm_webcam_ml_bridge")


func _defer_prewarm_webcam_ml_bridge() -> void:
	await get_tree().create_timer(PREWARM_WEBCAM_ML_DELAY_SEC).timeout
	for _i in range(2):
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


## 스테이지 클리어(KO) 시 호출. 짧을수록 좋은 기록으로 최고 기록 갱신
func record_stage_clear_time(seconds: float) -> void:
	if seconds <= 0.0 or not is_finite(seconds):
		return
	_last_stage_clear_sec = seconds
	if _best_stage_clear_sec < 0.0 or seconds < _best_stage_clear_sec:
		_best_stage_clear_sec = seconds
	_stage_clear_history.insert(0, seconds)
	while _stage_clear_history.size() > STAGE_CLEAR_HISTORY_MAX:
		_stage_clear_history.pop_back()
	save_stats()


func get_best_stage_clear_sec() -> float:
	return _best_stage_clear_sec


func get_last_stage_clear_sec() -> float:
	return _last_stage_clear_sec


func get_stage_clear_history() -> Array[float]:
	return _stage_clear_history.duplicate()


func format_stage_clear_time(seconds: float) -> String:
	if seconds < 0.0 or not is_finite(seconds):
		return "기록 없음"
	var m: int = int(seconds / 60.0)
	var s: float = seconds - float(m) * 60.0
	if m > 0:
		return "%d분 %.2f초" % [m, s]
	return "%.2f초" % s

func set_guarding(on: bool) -> void:
	is_guarding = on

func _process(delta: float) -> void:
	if _session_active:
		_session_elapsed_sec += delta
		if is_guarding:
			_session_calories += KCAL_GUARD_PER_SEC * delta
	# 가드 중에는 스태미너 초당 회복 없음 (막기 성공 시 `apply_guard_block_success`에서 1초 분량 회복)
	if not is_guarding:
		if stamina < stamina_max:
			stamina = minf(stamina_max, stamina + stamina_passive_recover_per_sec * delta)

func consume_stamina(amount: float) -> bool:
	if stamina < amount:
		return false
	stamina -= amount
	return true


## 적 공격을 가드로 막았을 때: 스태미너를 초당 회복과 동일한 양만큼 한 번 회복 + HP 소량 감소
func apply_guard_block_success() -> void:
	stamina = minf(stamina_max, stamina + stamina_passive_recover_per_sec)
	player_hp = maxf(0.0, player_hp - HP_CHIP_ON_GUARD_BLOCK)

func get_stamina_ratio() -> float:
	if stamina_max <= 0.0:
		return 1.0
	return clampf(stamina / stamina_max, 0.0, 1.0)

func get_player_hp_ratio() -> float:
	if player_max_hp <= 0.0:
		return 1.0
	return clampf(player_hp / player_max_hp, 0.0, 1.0)


func refresh_combat_derived_from_upgrades() -> void:
	player_max_hp = BASE_PLAYER_MAX_HP + float(_upgrade_hp) * UPGRADE_HP_PER_STEP
	stamina_max = BASE_STAMINA_MAX + float(_upgrade_stamina) * UPGRADE_STAMINA_PER_STEP
	stamina_passive_recover_per_sec = (
		BASE_STAMINA_PASSIVE_RECOVER + float(_upgrade_recover) * UPGRADE_RECOVER_PER_STEP
	)
	player_hp = minf(player_hp, player_max_hp)
	stamina = minf(stamina, stamina_max)


func get_sweat() -> int:
	return _sweat


func add_sweat(amount: int) -> void:
	if amount <= 0:
		return
	_sweat = maxi(0, _sweat + amount)
	save_stats()


func get_upgrade_hp_level() -> int:
	return _upgrade_hp


func get_upgrade_stamina_level() -> int:
	return _upgrade_stamina


func get_upgrade_recover_level() -> int:
	return _upgrade_recover


## kind: "hp" | "stamina" | "recover"
func try_purchase_upgrade(kind: String) -> bool:
	if _sweat < 1:
		return false
	match kind:
		"hp":
			if _upgrade_hp >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_hp += 1
			refresh_combat_derived_from_upgrades()
			player_hp = minf(player_hp + UPGRADE_HP_PER_STEP, player_max_hp)
		"stamina":
			if _upgrade_stamina >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_stamina += 1
			refresh_combat_derived_from_upgrades()
			stamina = minf(stamina + UPGRADE_STAMINA_PER_STEP, stamina_max)
		"recover":
			if _upgrade_recover >= UPGRADE_MAX_STEPS:
				return false
			_sweat -= 1
			_upgrade_recover += 1
			refresh_combat_derived_from_upgrades()
		_:
			return false
	save_stats()
	return true


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
		"punch_l", "punch_r":
			_session_calories += KCAL_PUNCH
		"upper_l", "upper_r":
			_session_calories += KCAL_UPPERCUT
		"dodge":
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
		"punch_l", "punch_r":
			kind = "punches"
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
	cfg.set_value("time_attack", "best_sec", _best_stage_clear_sec)
	cfg.set_value("time_attack", "last_sec", _last_stage_clear_sec)
	var hist_csv: String = ""
	for i: int in range(_stage_clear_history.size()):
		if i > 0:
			hist_csv += ","
		hist_csv += str(_stage_clear_history[i])
	cfg.set_value("time_attack", "history_csv", hist_csv)
	cfg.set_value("meta", "sweat", _sweat)
	cfg.set_value("meta", "up_hp", _upgrade_hp)
	cfg.set_value("meta", "up_sta", _upgrade_stamina)
	cfg.set_value("meta", "up_rec", _upgrade_recover)
	cfg.save(STATS_PATH)


func load_stats() -> void:
	if not FileAccess.file_exists(STATS_PATH):
		refresh_combat_derived_from_upgrades()
		return
	var cfg := ConfigFile.new()
	if cfg.load(STATS_PATH) != OK:
		refresh_combat_derived_from_upgrades()
		return
	for k in STATS_KEYS:
		if cfg.has_section_key("stats", k):
			_punch_counts[k] = cfg.get_value("stats", k, 0)
	# 구 저장(stats: jab_l/jab_r/hook_l/hook_r) → 펀치로 합산
	if cfg.has_section("stats"):
		if cfg.has_section_key("stats", "jab_l"):
			_punch_counts["punch_l"] += int(cfg.get_value("stats", "jab_l", 0))
		if cfg.has_section_key("stats", "hook_l"):
			_punch_counts["punch_l"] += int(cfg.get_value("stats", "hook_l", 0))
		if cfg.has_section_key("stats", "jab_r"):
			_punch_counts["punch_r"] += int(cfg.get_value("stats", "jab_r", 0))
		if cfg.has_section_key("stats", "hook_r"):
			_punch_counts["punch_r"] += int(cfg.get_value("stats", "hook_r", 0))
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
				var raw_pick: String = str(cfg.get_value("daily_challenges", pk, ""))
				_daily_challenge_picks.append(_migrate_daily_challenge_id(raw_pick))
		_daily_challenge_progress.clear()
		if cfg.has_section("daily_challenge_progress"):
			for pk2: String in cfg.get_section_keys("daily_challenge_progress"):
				var nk: String = _migrate_daily_challenge_id(pk2)
				var prev: int = int(_daily_challenge_progress.get(nk, 0))
				_daily_challenge_progress[nk] = (
					prev + int(cfg.get_value("daily_challenge_progress", pk2, 0))
				)
		var picks_invalid: bool = _daily_challenge_picks.size() != 3
		if not picks_invalid:
			for pid: String in _daily_challenge_picks:
				if not DAILY_CHALLENGE_DEFS.has(pid):
					picks_invalid = true
					break
		if picks_invalid:
			_roll_fresh_daily_challenges()
	else:
		_roll_fresh_daily_challenges()
	if cfg.has_section_key("time_attack", "best_sec"):
		_best_stage_clear_sec = float(cfg.get_value("time_attack", "best_sec", -1.0))
	if cfg.has_section_key("time_attack", "last_sec"):
		_last_stage_clear_sec = float(cfg.get_value("time_attack", "last_sec", -1.0))
	_stage_clear_history.clear()
	if cfg.has_section_key("time_attack", "history_csv"):
		var csv: String = str(cfg.get_value("time_attack", "history_csv", ""))
		if not csv.is_empty():
			for part: String in csv.split(","):
				var p: String = part.strip_edges()
				if not p.is_empty():
					var v: float = float(p)
					if is_finite(v) and v > 0.0:
						_stage_clear_history.append(v)
	if cfg.has_section_key("meta", "sweat"):
		_sweat = maxi(0, int(cfg.get_value("meta", "sweat", 0)))
	if cfg.has_section_key("meta", "up_hp"):
		_upgrade_hp = clampi(int(cfg.get_value("meta", "up_hp", 0)), 0, UPGRADE_MAX_STEPS)
	if cfg.has_section_key("meta", "up_sta"):
		_upgrade_stamina = clampi(int(cfg.get_value("meta", "up_sta", 0)), 0, UPGRADE_MAX_STEPS)
	if cfg.has_section_key("meta", "up_rec"):
		_upgrade_recover = clampi(int(cfg.get_value("meta", "up_rec", 0)), 0, UPGRADE_MAX_STEPS)
	refresh_combat_derived_from_upgrades()


# --- 창 크기·웹캠(카메라 인덱스) 저장 (통계 cfg와 분리) ---


## 디스크의 display_settings.cfg 를 다시 읽습니다(복싱 진입 직전 웹캠 브리지 기동 시 호출).
func reload_display_settings_from_disk() -> void:
	_load_display_settings_from_disk()


func _load_display_settings_from_disk() -> void:
	if not FileAccess.file_exists(DISPLAY_SETTINGS_PATH):
		if OS.get_name() == "Windows":
			_camera_backend = "dshow"
		return
	var cfg := ConfigFile.new()
	if cfg.load(DISPLAY_SETTINGS_PATH) != OK:
		if OS.get_name() == "Windows":
			_camera_backend = "dshow"
		return
	if cfg.has_section_key("display", "width") and cfg.has_section_key("display", "height"):
		var w := int(cfg.get_value("display", "width", 0))
		var h := int(cfg.get_value("display", "height", 0))
		if w >= DISPLAY_MIN_W and h >= DISPLAY_MIN_H:
			_saved_window_width = w
			_saved_window_height = h
	if cfg.has_section_key("camera", "index"):
		_camera_index = clampi(int(cfg.get_value("camera", "index", 0)), 0, 9)
	if cfg.has_section_key("camera", "backend"):
		_camera_backend = _sanitize_camera_backend(str(cfg.get_value("camera", "backend", "auto")))
	elif OS.get_name() == "Windows":
		# 저장 없음: USB 인식에 DirectShow가 자주 필요
		_camera_backend = "dshow"
	else:
		_camera_backend = "auto"
	if cfg.has_section_key("camera", "ml_speed_profile"):
		_ml_speed_profile = _sanitize_ml_speed_profile(str(cfg.get_value("camera", "ml_speed_profile", "balanced")))


func _apply_saved_window_size_deferred() -> void:
	var win := get_tree().root.get_window()
	if win == null:
		return
	if _saved_window_width < DISPLAY_MIN_W or _saved_window_height < DISPLAY_MIN_H:
		return
	win.set_mode(Window.MODE_WINDOWED)
	win.call_deferred("set_size", Vector2i(_saved_window_width, _saved_window_height))


func save_display_settings(
	width: int,
	height: int,
	camera_index: int,
	camera_backend: String = "auto",
	ml_speed_profile: String = "",
) -> void:
	var old_cam := _camera_index
	var old_back := _camera_backend
	var old_prof := _ml_speed_profile
	_saved_window_width = maxi(DISPLAY_MIN_W, width)
	_saved_window_height = maxi(DISPLAY_MIN_H, height)
	_camera_index = clampi(camera_index, 0, 9)
	_camera_backend = _sanitize_camera_backend(camera_backend)
	if ml_speed_profile.strip_edges() != "":
		_ml_speed_profile = _sanitize_ml_speed_profile(ml_speed_profile)
	var cfg := ConfigFile.new()
	if FileAccess.file_exists(DISPLAY_SETTINGS_PATH):
		cfg.load(DISPLAY_SETTINGS_PATH)
	cfg.set_value("display", "width", _saved_window_width)
	cfg.set_value("display", "height", _saved_window_height)
	cfg.set_value("camera", "index", _camera_index)
	cfg.set_value("camera", "backend", _camera_backend)
	cfg.set_value("camera", "ml_speed_profile", _ml_speed_profile)
	cfg.save(DISPLAY_SETTINGS_PATH)
	if old_cam != _camera_index or old_back != _camera_backend or old_prof != _ml_speed_profile:
		shutdown_webcam_ml_bridge()


func get_camera_index() -> int:
	return _camera_index


func get_camera_backend() -> String:
	return _camera_backend


func get_ml_speed_profile() -> String:
	return _ml_speed_profile


func _sanitize_ml_speed_profile(s: String) -> String:
	var t := s.strip_edges()
	for v in ML_SPEED_PROFILE_VALUES:
		if t == v:
			return t
	return "balanced"


func _sanitize_camera_backend(s: String) -> String:
	var t := s.strip_edges().to_lower()
	for v in CAMERA_BACKEND_VALUES:
		if t == v:
			return t
	return "auto"


func _is_process_running_safe(pid: int) -> bool:
	if pid <= 0:
		return false
	return OS.is_process_running(pid)


## 복싱 메인에서 호출: 이미 같은 인덱스·백엔드로 떠 있으면 유지(다시하기 시 끊김 방지).
func ensure_webcam_ml_bridge(auto_launch: bool) -> void:
	if not auto_launch:
		return
	if _webcam_ml_bridge_pid > 0 and not _is_process_running_safe(_webcam_ml_bridge_pid):
		_webcam_ml_bridge_pid = -1
	if not has_webcam_ml_runtime_files():
		push_warning("웹캠 ML: 스크립트 없음 — %s" % get_udp_send_webcam_ml_script_path())
		return
	reload_display_settings_from_disk()
	var cam: int = get_camera_index()
	var backend: String = get_camera_backend()
	var profile: String = get_ml_speed_profile()
	if _webcam_ml_bridge_pid > 0 and _is_process_running_safe(_webcam_ml_bridge_pid):
		if (
			_webcam_ml_launched_camera == cam
			and _webcam_ml_launched_backend == backend
			and _webcam_ml_launched_profile == profile
		):
			print(
				"웹캠 ML 브리지 유지 (PID=%d, index=%d, backend=%s, profile=%s)"
				% [_webcam_ml_bridge_pid, cam, backend, profile]
			)
			return
		var kerr: Error = OS.kill(_webcam_ml_bridge_pid)
		if kerr != OK:
			push_warning("이전 웹캠 ML 브리지 종료 실패 PID=%d" % _webcam_ml_bridge_pid)
		_webcam_ml_bridge_pid = -1
	var py: String = resolve_python_executable_for_ml()
	var script: String = get_udp_send_webcam_ml_script_path()
	var args := PackedStringArray([
		script,
		"--camera-index",
		str(cam),
		"--camera-backend",
		backend,
		"--profile",
		profile,
	])
	print("웹캠 ML 실행 시도: python=", py, " script=", script, " profile=", profile)
	_webcam_ml_bridge_pid = OS.create_process(py, args, false)
	if _webcam_ml_bridge_pid <= 0:
		push_warning(
			"웹캠 ML 브리지 시작 실패(OS.create_process). "
			+ "PowerShell에서 tools 로 이동 후 python udp_send_webcam_ml.py 수동 실행하거나, "
			+ "환경변수 BODY_HERO_PYTHON_EXE 에 python.exe 전체 경로를 설정하세요."
		)
		_webcam_ml_launched_camera = -999
		_webcam_ml_launched_backend = ""
		_webcam_ml_launched_profile = ""
	else:
		_webcam_ml_launched_camera = cam
		_webcam_ml_launched_backend = backend
		_webcam_ml_launched_profile = profile
		print(
			"웹캠 ML 브리지 시작 PID=",
			_webcam_ml_bridge_pid,
			" index=",
			cam,
			" backend=",
			backend,
			" profile=",
			profile,
		)


func get_webcam_ml_bridge_pid() -> int:
	return _webcam_ml_bridge_pid


func is_webcam_ml_bridge_running() -> bool:
	return _is_process_running_safe(_webcam_ml_bridge_pid)


func shutdown_webcam_ml_bridge() -> void:
	if _webcam_ml_bridge_pid > 0:
		var kerr: Error = OS.kill(_webcam_ml_bridge_pid)
		if kerr != OK:
			push_warning("웹캠 ML 브리지 종료 실패 PID=%d" % _webcam_ml_bridge_pid)
	_webcam_ml_bridge_pid = -1
	_webcam_ml_launched_camera = -999
	_webcam_ml_launched_backend = ""
	_webcam_ml_launched_profile = ""


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
