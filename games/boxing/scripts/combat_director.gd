extends Node
## Combat Director: 전투 판정, 콤보, 훈련장, 승/패 조건을 담당.
## UI나 UDP를 직접 다루지 않고, 신호를 통해 Main에 알림.

signal stage_cleared(clear_sec: float)
signal game_over_triggered
signal combo_changed(count: int)
signal training_hud_needs_update(training_mode: bool, kill_count: int, action_counts: Dictionary)
signal bars_need_update

@export var stage_id: String = "stage_1"

@onready var _player: Node2D = $"../Player"
@onready var _enemy: Node2D = $"../Enemy"

var _stage_timer_active: bool = true
var _stage_elapsed_sec: float = 0.0
var _combo_count: int = 0
var _max_combo_this_session: int = 0
var _damage_taken_this_session: float = 0.0
var _training_mode: bool = false
var _training_kill_count: int = 0
var _training_action_counts: Dictionary = {
	"punch_l": 0,
	"punch_r": 0,
	"upper_l": 0,
	"upper_r": 0,
	"guard": 0,
	"squat": 0,
}
var _win_shown: bool = false
var _newly_unlocked_achievements: Array[String] = []

const COMBO_DAMAGE_MUL_BASE := 1.0
const COMBO_DAMAGE_MUL_PER_10 := 0.08


func setup(training: bool) -> void:
	_training_mode = training
	if _training_mode and _enemy:
		_enemy.ai_enabled = false
	_stage_timer_active = true
	_stage_elapsed_sec = 0.0
	_combo_count = 0
	_max_combo_this_session = 0
	_damage_taken_this_session = 0.0
	_win_shown = false
	_newly_unlocked_achievements.clear()
	for k: String in _training_action_counts.keys():
		_training_action_counts[k] = 0


func _process(delta: float) -> void:
	if _stage_timer_active:
		_stage_elapsed_sec += delta


# --- 플레이어 액션 처리 ---

func on_player_punch_impact(damage: float, punch_type: String) -> void:
	if not _enemy:
		return
	if _enemy.has_method("is_dead") and _enemy.is_dead():
		return
	if _enemy.has_method("is_evading") and _enemy.is_evading():
		return
	if _enemy.has_method("take_damage"):
		var mul: float = get_combo_damage_multiplier()
		var final_dmg: float = damage * mul
		_enemy.take_damage(final_dmg, punch_type)
		GameState.add_punch_count(punch_type)
		_register_combo_hit()
		GameState.bump_achievement_progress("punch_100", 1)
		GameState.bump_achievement_progress("punch_500", 1)
		if punch_type.begins_with("upper"):
			GameState.bump_achievement_progress("upper_50", 1)


func on_player_action_performed(action: String) -> void:
	if not _training_mode:
		return
	if not _training_action_counts.has(action):
		return
	_training_action_counts[action] = int(_training_action_counts[action]) + 1
	training_hud_needs_update.emit(_training_mode, _training_kill_count, _training_action_counts)


# --- 적 공격 / 피격 / 사망 처리 ---

func on_enemy_attack(damage: float) -> void:
	if _training_mode:
		return
	if GameState.is_guarding:
		var reduction: float = GameState.get_guard_damage_reduction_factor()
		var taken: float = damage * (1.0 - reduction)
		if taken > 0.0:
			GameState.apply_player_damage(taken)
			_damage_taken_this_session += taken
		GameState.apply_guard_block_success()
		if _player and _player.has_method("play_guard_block_fx"):
			_player.play_guard_block_fx()
		GameState.bump_achievement_progress("guard_50", 1)
	else:
		_reset_combo()
		GameState.apply_player_damage(damage)
		_damage_taken_this_session += damage
		if GameState.player_hp <= 0.0:
			game_over_triggered.emit()
		if _player and _player.has_method("play_take_damage_fx"):
			_player.play_take_damage_fx()
	bars_need_update.emit()


func on_enemy_hit(_damage: float) -> void:
	bars_need_update.emit()


func on_enemy_died() -> void:
	bars_need_update.emit()
	if _training_mode:
		_training_kill_count += 1
		_reset_combo()
		training_hud_needs_update.emit(_training_mode, _training_kill_count, _training_action_counts)
		_respawn_training_dummy()
		return
	if _win_shown:
		return
	GameState.add_sweat(1)
	_reset_combo()
	_stage_timer_active = false
	GameState.record_stage_clear_time(_stage_elapsed_sec)
	# 별 / 기록 / 업적 처리
	var stars: int = GameState.evaluate_stage_stars(_stage_elapsed_sec, _max_combo_this_session, _damage_taken_this_session)
	GameState.record_stage_stars(stage_id, stars)
	GameState.update_stage_record(stage_id, _stage_elapsed_sec, _max_combo_this_session, _damage_taken_this_session)
	_newly_unlocked_achievements = GameState.check_and_unlock_achievements_after_session(_stage_elapsed_sec, _max_combo_this_session, _damage_taken_this_session, true)
	_begin_ko_intro_then_win()


func _begin_ko_intro_then_win() -> void:
	await get_tree().create_timer(1.5).timeout
	if not is_inside_tree() or _win_shown:
		return
	stage_cleared.emit(_stage_elapsed_sec)
	_win_shown = true


func is_win_shown() -> bool:
	return _win_shown


func get_stage_elapsed_sec() -> float:
	return _stage_elapsed_sec


func is_timer_active() -> bool:
	return _stage_timer_active


func stop_timer() -> void:
	_stage_timer_active = false


# --- 콤보 ---

func _register_combo_hit() -> void:
	_combo_count += 1
	if _combo_count > _max_combo_this_session:
		_max_combo_this_session = _combo_count
	combo_changed.emit(_combo_count)

func get_combo_damage_multiplier() -> float:
	return COMBO_DAMAGE_MUL_BASE + (float(_combo_count) / 10.0) * COMBO_DAMAGE_MUL_PER_10

func get_max_combo() -> int:
	return _max_combo_this_session

func get_damage_taken() -> float:
	return _damage_taken_this_session

func set_newly_unlocked_achievements(achievements: Array[String]) -> void:
	_newly_unlocked_achievements = achievements

func get_newly_unlocked_achievements() -> Array[String]:
	return _newly_unlocked_achievements.duplicate()

func get_training_action_counts() -> Dictionary:
	return _training_action_counts


func reset_combo() -> void:
	_reset_combo()


func _reset_combo() -> void:
	_combo_count = 0
	combo_changed.emit(_combo_count)


# --- 훈련장 리스폰 ---

func _respawn_training_dummy() -> void:
	await get_tree().create_timer(0.6).timeout
	if not is_inside_tree():
		return
	if not _enemy or not _enemy.has_method("reset_for_respawn"):
		return
	_enemy.reset_for_respawn()
	bars_need_update.emit()
