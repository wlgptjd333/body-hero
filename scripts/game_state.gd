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

# 제자리걸음 회복량 (초당)
const STAMINA_RECOVER_PER_SEC := 20.0

# 제자리걸음/회피: UDP에서 오는 액션으로 설정됨
var is_jogging: bool = false
var _last_jog_time: float = -999.0
const JOG_GRACE_SEC := 0.5  # 이 시간 안에 jog 다시 안 오면 jogging 해제

func _process(delta: float) -> void:
	# 제자리걸음 중일 때만 스태미너 회복
	if is_jogging and stamina < stamina_max:
		stamina = minf(stamina_max, stamina + STAMINA_RECOVER_PER_SEC * delta)
	# jog 신호가 일정 시간 안에 안 오면 jogging 해제
	if is_jogging and (Time.get_ticks_msec() / 1000.0 - _last_jog_time) > JOG_GRACE_SEC:
		is_jogging = false

func set_jogging(on: bool) -> void:
	is_jogging = on
	if on:
		_last_jog_time = Time.get_ticks_msec() / 1000.0

func tick_jog() -> void:
	is_jogging = true
	_last_jog_time = Time.get_ticks_msec() / 1000.0

func consume_stamina(amount: float) -> bool:
	if stamina < amount:
		return false
	stamina -= amount
	return true

func get_stamina_ratio() -> float:
	if stamina_max <= 0.0:
		return 1.0
	return clampf(stamina / stamina_max, 0.0, 1.0)

func get_player_hp_ratio() -> float:
	if player_max_hp <= 0.0:
		return 1.0
	return clampf(player_hp / player_max_hp, 0.0, 1.0)
