extends GutTest

var _enemy: Node2D = null
var _hit_received_count: int = 0
var _last_hit_damage: float = 0.0
var _died_count: int = 0
var _phase_changed_count: int = 0
var _last_phase: int = 0
var _attack_count: int = 0


func before_each() -> void:
	var script := load("res://games/boxing/scripts/enemy.gd")
	_enemy = Node2D.new()
	_enemy.set_script(script)
	_enemy.ai_enabled = false

	_enemy.hit_received.connect(_on_hit_received)
	_enemy.died.connect(_on_died)
	_enemy.phase_changed.connect(_on_phase_changed)
	_enemy.enemy_attack.connect(_on_enemy_attack)

	_hit_received_count = 0
	_last_hit_damage = 0.0
	_died_count = 0
	_phase_changed_count = 0
	_last_phase = 0
	_attack_count = 0

	_enemy.max_hp = 100.0
	_enemy.current_hp = 100.0
	_enemy.attack_delay_min = 9999.0
	_enemy.attack_delay_max = 9999.0
	_enemy.evade_idle_min = 9999.0
	_enemy.evade_idle_max = 9999.0
	add_child_autofree(_enemy)


func after_each() -> void:
	_enemy = null


func _on_hit_received(damage: float) -> void:
	_hit_received_count += 1
	_last_hit_damage = damage


func _on_died() -> void:
	_died_count += 1


func _on_phase_changed(new_phase: int) -> void:
	_phase_changed_count += 1
	_last_phase = new_phase


func _on_enemy_attack(_damage: float) -> void:
	_attack_count += 1


func _get_state() -> int:
	return _enemy.get("_current_state")


func _set_state(s: int) -> void:
	_enemy.set("_current_state", s)


# =============================================================================
# 초기 상태
# =============================================================================

func test_initial_state_is_idle() -> void:
	assert_eq(_get_state(), 0, "EnemyState.IDLE = 0")


func test_initial_hp_is_max() -> void:
	assert_eq(_enemy.current_hp, _enemy.max_hp)


# =============================================================================
# take_damage → HIT 전환
# =============================================================================

func test_take_damage_transitions_to_hit() -> void:
	_enemy.take_damage(10.0)
	assert_eq(_get_state(), 3, "EnemyState.HIT = 3")


func test_take_damage_emits_hit_received() -> void:
	_enemy.take_damage(15.0)
	assert_eq(_hit_received_count, 1)
	assert_almost_eq(_last_hit_damage, 15.0, 0.001)


func test_take_damage_reduces_hp() -> void:
	_enemy.take_damage(30.0)
	assert_almost_eq(_enemy.current_hp, 70.0, 0.001)


# =============================================================================
# 사망 처리
# =============================================================================

func test_lethal_damage_transitions_to_dead() -> void:
	_enemy.take_damage(9999.0)
	assert_eq(_get_state(), 4, "EnemyState.DEAD = 4")


func test_lethal_damage_emits_died() -> void:
	_enemy.take_damage(9999.0)
	assert_eq(_get_state(), 4, "DEAD state")
	assert_eq(_died_count, 1, "사망 시 died 시그널 발생")


func test_take_damage_while_dead_is_no_op() -> void:
	_enemy.take_damage(9999.0)
	_enemy.take_damage(10.0)
	assert_eq(_died_count, 1, "추가 사망 시그널 없음")
	assert_eq(_hit_received_count, 0, "죽은 상태에서 hit_received 없음")


func test_hp_does_not_go_below_zero() -> void:
	_enemy.take_damage(9999.0)
	assert_almost_eq(_enemy.current_hp, 0.0, 0.001)


# =============================================================================
# TRAINING RESPAWN — KO 콜백 스테일 방지
# =============================================================================

func test_reset_respawn_cleans_up_ko_callback() -> void:
	_enemy.take_damage(9999.0)
	assert_eq(_get_state(), 4, "DEAD")
	_enemy.reset_for_respawn()
	assert_eq(_get_state(), 0, "리스폰 후 IDLE")
	assert_eq(_died_count, 1, "리스폰 후 추가 died(스테일 콜백) 없음")

	_enemy.take_damage(10.0)
	assert_ne(_get_state(), 4, "재피격 시 DEAD 아님")
	assert_eq(_get_state(), 3, "재피격 시 HIT 진입 (데드락 없음)")
	assert_eq(_hit_received_count, 1, "hit_received 정상")


# =============================================================================
# HIT 재진입 (콤보)
# =============================================================================

func test_hit_refreshes_stagger_on_re_damage() -> void:
	_enemy.take_damage(10.0)
	var state_before: int = _get_state()
	_enemy.take_damage(10.0)
	assert_eq(_get_state(), state_before, "HIT 유지")
	assert_eq(_hit_received_count, 2, "hit_received 재발생")


# =============================================================================
# is_evading / is_dead
# =============================================================================

func test_is_evading_true_only_in_evade_state() -> void:
	assert_false(_enemy.is_evading(), "초기 IDLE은 회피 아님")
	_set_state(2)  # EVADE
	assert_true(_enemy.is_evading(), "EVADE 상태에서 회피")
	_set_state(0)
	assert_false(_enemy.is_evading(), "IDLE로 복귀 후 회피 아님")


func test_is_dead_true_only_in_dead_state() -> void:
	assert_false(_enemy.is_dead(), "초기엔 사망 아님")
	_enemy.take_damage(9999.0)
	assert_true(_enemy.is_dead(), "사망 시 true")
	_enemy.reset_for_respawn()
	assert_false(_enemy.is_dead(), "리스폰 후 false")


# =============================================================================
# reset_for_respawn
# =============================================================================

func test_reset_for_respawn_returns_to_idle() -> void:
	_enemy.take_damage(9999.0)
	assert_eq(_get_state(), 4, "DEAD")
	_enemy.reset_for_respawn()
	assert_eq(_get_state(), 0, "리스폰 후 IDLE")


func test_reset_for_respawn_restores_hp() -> void:
	_enemy.take_damage(50.0)
	_enemy.reset_for_respawn()
	assert_almost_eq(_enemy.current_hp, _enemy.max_hp, 0.001)


func test_reset_for_respawn_resets_sprite() -> void:
	_enemy.take_damage(9999.0)
	_enemy.reset_for_respawn()
	assert_eq(_enemy.get("_is_dead"), false)
	assert_eq(_enemy.get("_is_attacking"), false)
	assert_eq(_enemy.get("_is_evading"), false)


# =============================================================================
# Boss 페이즈 전환
# =============================================================================

func test_boss_phase_up_on_lethal_damage() -> void:
	_enemy.is_boss = true
	_enemy.boss_phases = 2
	_enemy.max_hp = 100.0
	_enemy.current_hp = 100.0
	_enemy.take_damage(9999.0)
	assert_eq(_phase_changed_count, 1, "phase_changed 발생")
	assert_eq(_last_phase, 2)
	assert_eq(_died_count, 0, "사망 아님")
	assert_gt(_enemy.current_hp, 0, "HP 회복됨")


func test_boss_final_phase_kills() -> void:
	_enemy.is_boss = true
	_enemy.boss_phases = 2
	_enemy.set("_current_phase", 2)
	_enemy.take_damage(9999.0)
	assert_eq(_died_count, 1, "최종 페이즈 사망")


# =============================================================================
# AI 비활성화
# =============================================================================

func test_ai_disabled_idle_timers_dont_count() -> void:
	_enemy.ai_enabled = false
	_enemy.attack_delay_min = 0.01
	_enemy.attack_delay_max = 0.01
	_enemy.set("_attack_idle_timer", 0.01)
	_enemy.set("_evade_idle_timer", 999.0)
	for _i in range(10):
		_enemy._process(0.1)
	assert_eq(_get_state(), 0, "ai_enabled=false면 IDLE 유지")


func test_ai_enabled_idle_transitions_to_attack() -> void:
	_enemy.ai_enabled = true
	_enemy.attack_delay_min = 0.01
	_enemy.attack_delay_max = 0.01
	_enemy.set("_attack_idle_timer", 0.01)
	_enemy.set("_evade_idle_timer", 999.0)
	_enemy._process(0.1)
	assert_eq(_get_state(), 1, "EnemyState.ATTACK = 1")


# =============================================================================
# take_damage → hit_received signal
# =============================================================================

func test_hit_stagger_countdown_returns_to_idle() -> void:
	_enemy.take_damage(10.0)
	assert_eq(_get_state(), 3, "HIT 진입")
	_enemy.set("hit_stagger_duration", 0.1)
	_enemy.set("_hit_timer", 0.1)
	for _i in range(5):
		_enemy._process(0.05)
	assert_eq(_get_state(), 0, "stagger 종료 후 IDLE 복귀")


func test_evade_last_full_duration_then_returns_to_idle() -> void:
	_enemy.ai_enabled = true
	_enemy.evade_idle_min = 0.01
	_enemy.evade_idle_max = 0.01
	_enemy.evade_duration = 0.1
	_enemy.set("_evade_idle_timer", 0.01)
	_enemy.set("_attack_idle_timer", 999.0)

	_enemy._process(0.05)
	assert_eq(_get_state(), 2, "EVADE 진입")

	_enemy._process(0.03)
	assert_eq(_get_state(), 2, "아직 duration 내")

	_enemy._process(0.03)
	assert_eq(_get_state(), 2, "아직 duration 내 (0.06 누적)")

	_enemy._process(0.05)
	assert_eq(_get_state(), 0, "duration 초과, sprite 없음 -> 즉시 IDLE")


func test_return_from_evade_called_once() -> void:
	_enemy.ai_enabled = true
	_enemy.evade_idle_min = 0.01
	_enemy.evade_idle_max = 0.01
	_enemy.evade_duration = 0.01
	_enemy.set("_evade_idle_timer", 0.01)
	_enemy.set("_attack_idle_timer", 999.0)

	_enemy._process(0.05)
	assert_eq(_get_state(), 2, "EVADE 진입")

	_enemy.set("_evade_timer", 0.0)
	_enemy._process(0.05)
	assert_eq(_get_state(), 0, "timer 만료 + sprite 없음 -> 즉시 IDLE")

	_enemy._process(0.05)
	_enemy._process(0.05)
	assert_eq(_get_state(), 0, "IDLE 유지 (반복 호출 안전)")
