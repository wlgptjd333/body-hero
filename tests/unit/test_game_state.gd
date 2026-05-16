extends GutTest

var _state: Node = null
var _saved_achievements: Dictionary = {}
var _saved_progress: Dictionary = {}
var _saved_sweat: int = 0
var _saved_shop_owned: Dictionary = {}
var _saved_shop_inventory: Dictionary = {}
var _saved_stage_stars: Dictionary = {}
var _saved_stage_records: Dictionary = {}
var _saved_last_played: String = ""
var _saved_boss_buffs: Array = []
var _saved_player_hp: float = 0.0
var _saved_stamina: float = 0.0


func before_each() -> void:
	_state = GameState
	_saved_achievements = _state._achievements._unlocked.duplicate()
	_saved_progress = _state._achievements._progress.duplicate()
	_saved_sweat = _state._upgrade_system._sweat
	_saved_shop_owned = _state._shop_module._owned_items.duplicate()
	_saved_shop_inventory = _state._shop_module._inventory.duplicate()
	_saved_stage_stars = _state._stage_progress._stars.duplicate()
	_saved_stage_records = _state._stage_progress._records.duplicate(true)
	_saved_last_played = _state._stage_progress._last_played_id
	_saved_boss_buffs = _state._boss._buffs_selected.duplicate()
	_saved_player_hp = _state.player_hp
	_saved_stamina = _state.stamina

	_state._achievements._unlocked.clear()
	_state._achievements._progress.clear()
	_state._upgrade_system._sweat = 0
	_state._shop_module._owned_items.clear()
	_state._shop_module._inventory.clear()
	_state._stage_progress._stars.clear()
	_state._stage_progress._records.clear()
	_state.player_hp = _state.player_max_hp
	_state.stamina = _state.stamina_max


func after_each() -> void:
	_state._achievements._unlocked = _saved_achievements
	_state._achievements._progress = _saved_progress
	_state._upgrade_system._sweat = _saved_sweat
	_state._shop_module._owned_items = _saved_shop_owned
	_state._shop_module._inventory = _saved_shop_inventory
	_state._stage_progress._stars = _saved_stage_stars
	_state._stage_progress._records = _saved_stage_records
	_state._stage_progress._last_played_id = _saved_last_played
	_state._boss._buffs_selected = _saved_boss_buffs
	_state.player_hp = _saved_player_hp
	_state.stamina = _saved_stamina
	_state = null


# =============================================================================
# 업적: 콤보 — "단일 세션 최대값" 규칙이 핵심
# 누적 합산으로 해제되면 안 된다는 게 비자명한 비즈니스 룰
# =============================================================================

func test_combo_30_requires_single_session_not_cumulative() -> void:
	# 20 + 15 = 35 ≥ 30 이지만, 단일 세션으로는 둘 다 30 미달
	_state.check_and_unlock_achievements_after_session(60.0, 20, 0.0, true)
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 15, 0.0, true)
	assert_does_not_have(unlocked, "combo_30", "누적 35이더라도 단일 세션 30이 필요")

func test_combo_50_requires_single_session_not_cumulative() -> void:
	# 25 + 25 = 50 이지만 단일 세션으로는 미달
	_state.check_and_unlock_achievements_after_session(60.0, 25, 0.0, true)
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 25, 0.0, true)
	assert_does_not_have(unlocked, "combo_50", "누적 50이더라도 단일 세션 50이 필요")

func test_combo_30_cascade_also_unlocks_combo_10() -> void:
	# 30 달성 시 combo_10도 같이 해제돼야 함
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 30, 0.0, true)
	assert_has(unlocked, "combo_30")
	assert_has(unlocked, "combo_10", "combo_30 달성 시 combo_10도 함께 해제")
	assert_does_not_have(unlocked, "combo_50")

func test_combo_50_cascade_unlocks_all_three() -> void:
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 50, 0.0, true)
	assert_has(unlocked, "combo_50")
	assert_has(unlocked, "combo_30")
	assert_has(unlocked, "combo_10")

func test_already_unlocked_achievement_not_returned_again() -> void:
	# 한 번 해제된 업적은 newly_unlocked에 다시 나오면 안 됨
	_state.check_and_unlock_achievements_after_session(60.0, 30, 0.0, true)
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 30, 0.0, true)
	assert_does_not_have(unlocked, "combo_30", "이미 해제된 업적은 재반환 안 됨")


# =============================================================================
# 업적: first_blood / no_damage — 실제 버그가 있었던 로직
# =============================================================================

func test_first_blood_unlocks_on_first_clear() -> void:
	# bump_achievement_progress 내부에서 unlock을 먼저 호출하는 구조적 함정
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 0, 50.0, true)
	assert_has(unlocked, "first_blood", "첫 클리어 시 반드시 newly_unlocked에 포함")

func test_first_blood_requires_clear() -> void:
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 0, 50.0, false)
	assert_does_not_have(unlocked, "first_blood", "클리어 실패 시 first_blood 해제 안 됨")

func test_no_damage_unlocks_at_exact_zero() -> void:
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 0, 0.0, true)
	assert_has(unlocked, "no_damage")

func test_no_damage_does_not_unlock_with_any_damage() -> void:
	# 0.01이라도 맞으면 해제 안 됨 — 경계값 버그가 있었던 곳
	var unlocked: Array[String] = _state.check_and_unlock_achievements_after_session(60.0, 0, 0.01, true)
	assert_does_not_have(unlocked, "no_damage", "0.01 데미지는 피격으로 간주")


# =============================================================================
# 업적: bump progress — 자동 해제 사이드이펙트
# =============================================================================

func test_bump_achievement_progress_caps_at_target() -> void:
	_state.bump_achievement_progress("combo_50", 100)
	assert_eq(_state.get_achievement_progress("combo_50"), 50, "target=50에서 캡")

func test_bump_triggers_unlock_when_target_reached() -> void:
	_state.bump_achievement_progress("combo_50", 50)
	assert_true(_state.is_achievement_unlocked("combo_50"), "progress 도달 시 자동 해제")


# =============================================================================
# HP / 스태미너 — 게임 규칙 불변식
# =============================================================================

func test_player_hp_cannot_go_below_zero() -> void:
	_state.apply_player_damage(99999.0)
	assert_almost_eq(_state.player_hp, 0.0, 0.001, "HP는 0 미만 불가")

func test_consume_stamina_blocked_when_insufficient() -> void:
	_state.stamina = 5.0
	var ok: bool = _state.consume_stamina(10.0)
	assert_false(ok, "스태미너 부족 시 소모 거부")
	assert_almost_eq(_state.stamina, 5.0, 0.001, "거부 시 스태미너 변경 없음")

func test_squat_heal_cannot_exceed_max_hp() -> void:
	_state.player_hp = _state.player_max_hp
	_state.apply_squat_heal(1.0)
	assert_almost_eq(_state.player_hp, _state.player_max_hp, 0.001, "최대 HP 초과 불가")


# =============================================================================
# 별점 / 스테이지 기록 — "최고 기록 유지" 불변식
# =============================================================================

func test_stage_stars_keeps_best_not_latest() -> void:
	_state.record_stage_stars("stage_1", 3)
	_state.record_stage_stars("stage_1", 1)  # 더 나쁜 결과
	assert_eq(_state.get_stage_stars("stage_1"), 3, "별은 항상 최고값 유지")

func test_evaluate_stage_stars_all_conditions() -> void:
	# 공식: base 1 + sec≤45 + combo≥20 + dmg≤30 → clamp(4, 0, 3) = 3
	assert_eq(_state.evaluate_stage_stars(30.0, 25, 10.0), 3)

func test_evaluate_stage_stars_none_met() -> void:
	# 조건 하나도 안 맞으면 base 1점만
	assert_eq(_state.evaluate_stage_stars(100.0, 5, 100.0), 1)

func test_stage_record_best_time_never_worsens() -> void:
	_state.update_stage_record("stage_1", 40.0, 10, 50.0)
	_state.update_stage_record("stage_1", 60.0, 10, 50.0)  # 더 느린 기록
	var rec: Dictionary = _state.get_stage_record("stage_1")
	assert_almost_eq(float(rec.get("best_time", -1.0)), 40.0, 0.001, "더 느린 기록은 무시")

func test_stage_record_best_combo_never_worsens() -> void:
	_state.update_stage_record("stage_1", 60.0, 30, 50.0)
	_state.update_stage_record("stage_1", 60.0, 5, 50.0)
	var rec: Dictionary = _state.get_stage_record("stage_1")
	assert_eq(int(rec.get("best_combo", 0)), 30, "더 낮은 콤보는 무시")

func test_stage_record_least_damage_never_worsens() -> void:
	_state.update_stage_record("stage_1", 60.0, 10, 10.0)
	_state.update_stage_record("stage_1", 60.0, 10, 99.0)
	var rec: Dictionary = _state.get_stage_record("stage_1")
	assert_almost_eq(float(rec.get("least_dmg", -1.0)), 10.0, 0.001, "더 큰 피해는 무시")


# =============================================================================
# 스테이지 선택 / 보스 버프 — 위임 wrapper 누락 방지
# =============================================================================

func test_last_played_stage_id_roundtrip() -> void:
	_state.set_last_played_stage_id("stage_3")
	assert_eq(_state.get_last_played_stage_id(), "stage_3", "set_last_played_stage_id → get_last_played_stage_id")

func test_add_boss_buff_persists() -> void:
	var buff: Dictionary = {"name": "테스트 버프", "effect": {"test": 1.0}}
	_state.add_boss_buff(buff)
	var selected: Array = _state.get_boss_buffs_selected()
	assert_eq(selected.size(), 1, "버프 추가 후 선택 목록 1개")
	assert_eq(str(selected[0].get("name", "")), "테스트 버프", "버프 내용 일치")


# =============================================================================
# 상점 — 구매 규칙
# =============================================================================

func test_purchase_blocked_with_no_sweat() -> void:
	_state._upgrade_system._sweat = 0
	assert_false(_state.try_purchase_item("glove_red"), "스웨트 없으면 구매 불가")

func test_purchase_deducts_sweat() -> void:
	_state._upgrade_system._sweat = 10
	_state.try_purchase_item("glove_red")  # price = 5
	assert_eq(_state.get_sweat(), 5)

func test_skin_cannot_be_purchased_twice() -> void:
	_state._upgrade_system._sweat = 20
	_state.try_purchase_item("glove_red")
	assert_false(_state.try_purchase_item("glove_red"), "이미 소유한 스킨 재구매 불가")

func test_consumable_stacks_in_inventory() -> void:
	_state._upgrade_system._sweat = 20
	_state.try_purchase_item("buff_speed")
	_state.try_purchase_item("buff_speed")
	assert_eq(_state.get_item_inventory_count("buff_speed"), 2, "소모품은 중복 구매 가능")

func test_equip_fails_without_ownership() -> void:
	assert_false(_state.equip_glove_skin("glove_red"), "미소유 스킨 장착 불가")

func test_negative_sweat_add_is_ignored() -> void:
	_state._upgrade_system._sweat = 10
	_state.add_sweat(-5)
	assert_eq(_state.get_sweat(), 10, "음수 스웨트 추가는 무시")


# =============================================================================
# 스태미너 상수 정합성: game_state.gd와 upgrade_system.gd 일치
# =============================================================================

func test_stamina_recover_constant_in_sync() -> void:
	assert_eq(
		GameState.BASE_STAMINA_PASSIVE_RECOVER,
		_state._upgrade_system.BASE_STAMINA_PASSIVE_RECOVER,
		"game_state.gd와 upgrade_system.gd의 BASE_STAMINA_PASSIVE_RECOVER 일치"
	)


func test_stamina_recovery_base_constant_is_10() -> void:
	assert_eq(GameState.BASE_STAMINA_PASSIVE_RECOVER, 10.0, "기본 회복 상수 10.0")


# =============================================================================
# GameState → 모듈 delegation 계약: 모든 public 위임 함수가 실제 모듈에 구현되어 있는지 검증
# =============================================================================

func test_get_recent_daily_calories_returns_without_error() -> void:
	var result: Array = _state.get_recent_daily_calories(5)
	assert_true(result.size() > 0, "최근 5일 데이터 반환")
	assert_has(result[0], "date", "각 항목에 date 키")
	assert_has(result[0], "calories", "각 항목에 calories 키")


func test_workout_delegation_methods_exist() -> void:
	var pairs: Array[Dictionary] = [
		{"method": "get_last_session_calories", "module": "_workout"},
		{"method": "get_recent_daily_calories", "module": "_workout"},
		{"method": "get_recent_daily_weight_log", "module": "_workout"},
		{"method": "get_today_calories", "module": "_workout"},
		{"method": "get_weight_kg", "module": "_workout"},
		{"method": "get_height_cm", "module": "_workout"},
		{"method": "get_age", "module": "_workout"},
		{"method": "get_gender", "module": "_workout"},
		{"method": "get_bmi", "module": "_workout"},
		{"method": "get_intensity_factor", "module": "_workout"},
		{"method": "get_bmi_category_label", "module": "_workout"},
		{"method": "get_recommended_daily_kcal_goal", "module": "_workout"},
		{"method": "get_daily_kcal_goal", "module": "_workout"},
		{"method": "get_daily_goal_punch_hints", "module": "_workout"},
	]
	for pair: Dictionary in pairs:
		var mod = _state.get(pair["module"])
		assert_not_null(mod, "모듈 %s 로드됨" % pair["module"])
		assert_true(mod.has_method(pair["method"]), "%s.%s 존재" % [pair["module"], pair["method"]])


func test_upgrade_delegation_methods_exist() -> void:
	var pairs: Array[Dictionary] = [
		{"method": "get_sweat", "module": "_upgrade_system"},
		{"method": "add_sweat", "module": "_upgrade_system"},
		{"method": "set_sweat", "module": "_upgrade_system"},
		{"method": "get_hp_level", "module": "_upgrade_system"},
		{"method": "get_stamina_level", "module": "_upgrade_system"},
		{"method": "get_recover_level", "module": "_upgrade_system"},
		{"method": "try_purchase", "module": "_upgrade_system"},
		{"method": "reset_all", "module": "_upgrade_system"},
	]
	for pair: Dictionary in pairs:
		var mod = _state.get(pair["module"])
		assert_not_null(mod, "모듈 %s 로드됨" % pair["module"])
		assert_true(mod.has_method(pair["method"]), "%s.%s 존재" % [pair["module"], pair["method"]])


func test_stage_progress_delegation_methods_exist() -> void:
	var pairs: Array[Dictionary] = [
		{"method": "record_clear_time", "module": "_stage_progress"},
		{"method": "get_best_clear_sec", "module": "_stage_progress"},
		{"method": "get_last_clear_sec", "module": "_stage_progress"},
		{"method": "get_stars", "module": "_stage_progress"},          # GameState.get_stage_stars → get_stars
		{"method": "record_stars", "module": "_stage_progress"},      # GameState.record_stage_stars → record_stars
		{"method": "evaluate_stars", "module": "_stage_progress"},    # GameState.evaluate_stage_stars → evaluate_stars
		{"method": "update_record", "module": "_stage_progress"},     # GameState.update_stage_record → update_record
		{"method": "get_record", "module": "_stage_progress"},        # GameState.get_stage_record → get_record
		{"method": "has_next", "module": "_stage_progress"},
		{"method": "format_clear_time", "module": "_stage_progress"},
	]
	for pair: Dictionary in pairs:
		var mod = _state.get(pair["module"])
		assert_not_null(mod, "모듈 %s 로드됨" % pair["module"])
		assert_true(mod.has_method(pair["method"]), "%s.%s 존재" % [pair["module"], pair["method"]])


func test_daily_challenges_delegation_methods_exist() -> void:
	var pairs: Array[Dictionary] = [
		{"method": "get_challenges_for_ui", "module": "_daily"},
		{"method": "get_progress", "module": "_daily"},
		{"method": "sync_calendar", "module": "_daily"},
		{"method": "bump_for_punch_action", "module": "_daily"},
		{"method": "bump_for_kind", "module": "_daily"},
	]
	for pair: Dictionary in pairs:
		var mod = _state.get(pair["module"])
		assert_not_null(mod, "모듈 %s 로드됨" % pair["module"])
		assert_true(mod.has_method(pair["method"]), "%s.%s 존재" % [pair["module"], pair["method"]])


func test_achievements_and_boss_and_shop_delegation_methods_exist() -> void:
	var pairs: Array[Dictionary] = [
		{"method": "check_after_session", "module": "_achievements"},        # GameState.check_and_unlock_achievements_after_session
		{"method": "is_unlocked", "module": "_achievements"},                # GameState.is_achievement_unlocked
		{"method": "bump", "module": "_achievements"},                       # GameState.bump_achievement_progress
		{"method": "get_progress", "module": "_achievements"},               # GameState.get_achievement_progress
		{"method": "get_defs", "module": "_achievements"},                   # GameState.get_all_achievements
		{"method": "add_buff", "module": "_boss"},                           # GameState.add_boss_buff
		{"method": "get_buffs_selected", "module": "_boss"},                 # GameState.get_boss_buffs_selected
		{"method": "reset_all", "module": "_boss"},
		{"method": "try_purchase_item", "module": "_shop_module"},
		{"method": "is_item_owned", "module": "_shop_module"},               # GameState uses this internally
		{"method": "get_equipped_glove_skin", "module": "_shop_module"},
		{"method": "get_equipped_hit_effect", "module": "_shop_module"},
		{"method": "equip_glove_skin", "module": "_shop_module"},
		{"method": "equip_hit_effect", "module": "_shop_module"},
	]
	for pair: Dictionary in pairs:
		var mod = _state.get(pair["module"])
		assert_not_null(mod, "모듈 %s 로드됨" % pair["module"])
		assert_true(mod.has_method(pair["method"]), "%s.%s 존재" % [pair["module"], pair["method"]])
