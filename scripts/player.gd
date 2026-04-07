extends Node2D
## 고정 글러브 + 행동 트리거 애니 (Leftovers KO! 스타일)
## 피격 판정: 히트박스 없음. 임팩트 시점에 punch_impact 시그널만 발생 → Main에서 적 회피 여부로 hit/miss 처리

signal punch_impact(damage: float, punch_type: String)  # punch_type: "jab_l" | "jab_r" | "upper_l" | "upper_r" | "hook_l" | "hook_r"

# 적 HP 100 기준, 1/3 수준으로 조정 (약 20~25타 정도로 KO)
const DAMAGE_JAB := 3.0
const DAMAGE_UPPERCUT := 5.0
const DAMAGE_HOOK := 5.0

const PUNCH_SCALE := Vector2(2.2, 2.2)
const JAB_DURATION_OUT := 0.05
const JAB_DURATION_IN := 0.08
const UPPERCUT_SCALE := Vector2(2.0, 2.4)
const UPPERCUT_OFFSET := Vector2(0, -40)
const UPPERCUT_DURATION_OUT := 0.04
const UPPERCUT_DURATION_IN := 0.06
const GUARD_SCALE := Vector2(1.4, 1.4)
const GUARD_DURATION_IN := 0.05
const GUARD_DURATION_OUT := 0.06
# 가드 최소 유지 시간(초). 이 시간 지나야 guard_end로 해제 가능
const GUARD_MIN_DURATION := 0.25
const HOOK_SCALE := Vector2(2.1, 2.1)
const HOOK_OFFSET_LEFT := Vector2(-38, 0)   # 왼손 훅: 옆으로 말아 들어오는 궤적
const HOOK_OFFSET_RIGHT := Vector2(38, 0)   # 오른손 훅
const HOOK_DURATION_OUT := 0.05
const HOOK_DURATION_IN := 0.07
const PUNCH_TRANS := Tween.TRANS_QUINT

const HIT_LAYER_BIT := 2  # collision_layer 2 = 글러브

@onready var left_glove: Area2D = $LeftGlove
@onready var right_glove: Area2D = $RightGlove

var _left_default_pos: Vector2
var _right_default_pos: Vector2
var _left_default_scale: Vector2
var _right_default_scale: Vector2
var _busy := false
var _guarding := false
var _guard_enter_time: float = -999.0
## 웹캠(UDP)으로 가드 들어간 경우: 키를 안 눌러도 유지, guard_end(UDP)까지 유지
var _guard_via_udp: bool = false


func _ready() -> void:
	_left_default_pos = left_glove.position
	_right_default_pos = right_glove.position
	_left_default_scale = left_glove.scale
	_right_default_scale = right_glove.scale
	_set_glove_hit(left_glove, false)
	_set_glove_hit(right_glove, false)


func _process(_delta: float) -> void:
	# 키보드 가드만: 키를 뗐으면 즉시 해제. 웹캠(UDP) 가드는 guard_end 패킷으로만 해제
	if _guarding and not _guard_via_udp and not Input.is_action_pressed("guard"):
		_guarding = false
		GameState.set_guarding(false)
		_busy = true
		_play_guard_exit(func(): _busy = false)
		return
	if _busy:
		return
	if Input.is_action_just_pressed("punch_left"):
		play_action("jab_l")
	elif Input.is_action_just_pressed("punch_right"):
		play_action("jab_r")
	elif Input.is_action_just_pressed("upper_left"):
		play_action("upper_l")
	elif Input.is_action_just_pressed("upper_right"):
		play_action("upper_r")
	elif Input.is_action_just_pressed("hook_left"):
		play_action("hook_l")
	elif Input.is_action_just_pressed("hook_right"):
		play_action("hook_r")
	elif Input.is_action_just_pressed("guard"):
		play_action("guard")


func play_action(action: String, via_udp: bool = false) -> bool:
	if _busy and action != "guard_end" and action != "dodge_l" and action != "dodge_r":
		return false
	match action:
		"jab_l":
			if not GameState.consume_stamina(GameState.STAMINA_JAB):
				return false
			_busy = true
			GameState.record_action_for_calorie("jab_l")
			_play_jab(left_glove, _left_default_pos, _left_default_scale, "jab_l", func(): _busy = false)
			return true
		"jab_r":
			if not GameState.consume_stamina(GameState.STAMINA_JAB):
				return false
			_busy = true
			GameState.record_action_for_calorie("jab_r")
			_play_jab(right_glove, _right_default_pos, _right_default_scale, "jab_r", func(): _busy = false)
			return true
		"upper_l":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return false
			_busy = true
			GameState.record_action_for_calorie("upper_l")
			_play_uppercut(left_glove, _left_default_pos, _left_default_scale, "upper_l", func(): _busy = false)
			return true
		"upper_r":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return false
			_busy = true
			GameState.record_action_for_calorie("upper_r")
			_play_uppercut(right_glove, _right_default_pos, _right_default_scale, "upper_r", func(): _busy = false)
			return true
		"hook_l":
			if not GameState.consume_stamina(GameState.STAMINA_HOOK):
				return false
			_busy = true
			GameState.record_action_for_calorie("hook_l")
			_play_hook(left_glove, _left_default_pos, _left_default_scale, true, "hook_l", func(): _busy = false)
			return true
		"hook_r":
			if not GameState.consume_stamina(GameState.STAMINA_HOOK):
				return false
			_busy = true
			GameState.record_action_for_calorie("hook_r")
			_play_hook(right_glove, _right_default_pos, _right_default_scale, false, "hook_r", func(): _busy = false)
			return true
		"dodge_l":
			_busy = true
			GameState.record_action_for_calorie("dodge_l")
			_play_dodge(true, func(): _busy = false)
			return true
		"dodge_r":
			_busy = true
			GameState.record_action_for_calorie("dodge_r")
			_play_dodge(false, func(): _busy = false)
			return true
		"guard":
			if _guarding:
				return false
			_guard_via_udp = via_udp
			_guarding = true
			GameState.record_action_for_calorie("guard")
			GameState.set_guarding(true)
			_guard_enter_time = Time.get_ticks_msec() / 1000.0
			GameState.record_guard()
			_play_guard_enter()
			return true
		"guard_end":
			if not _guarding:
				return false
			# 가드 최소 유지 시간 지나야 해제 가능 (짧게 누르면 무시)
			var elapsed: float = Time.get_ticks_msec() / 1000.0 - _guard_enter_time
			if elapsed < GUARD_MIN_DURATION:
				return false
			_guard_via_udp = false
			_guarding = false
			GameState.set_guarding(false)
			_busy = true
			_play_guard_exit(func(): _busy = false)
			return true
		_:
			return false


func _set_glove_hit(glove: Area2D, enabled: bool) -> void:
	if not glove:
		return
	glove.set_collision_layer_value(HIT_LAYER_BIT, enabled)


func _reset_guard_visual() -> void:
	if left_glove:
		left_glove.scale = _left_default_scale
	if right_glove:
		right_glove.scale = _right_default_scale


func _play_jab(glove: Area2D, default_pos: Vector2, default_scale: Vector2, action: String, on_finished: Callable) -> void:
	glove.position = default_pos
	glove.scale = default_scale
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(glove, "scale", PUNCH_SCALE, JAB_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_callback(func(): punch_impact.emit(DAMAGE_JAB, action))
	tween.tween_interval(0.03)
	tween.tween_property(glove, "scale", default_scale, JAB_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.tween_callback(on_finished)


func _play_hook(glove: Area2D, default_pos: Vector2, default_scale: Vector2, is_left: bool, action: String, on_finished: Callable) -> void:
	var offset := HOOK_OFFSET_LEFT if is_left else HOOK_OFFSET_RIGHT
	glove.position = default_pos
	glove.scale = default_scale
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + offset, HOOK_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", HOOK_SCALE, HOOK_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(func(): punch_impact.emit(DAMAGE_HOOK, action))
	tween.tween_interval(0.035)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos, HOOK_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", default_scale, HOOK_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(on_finished)


func _play_uppercut(glove: Area2D, default_pos: Vector2, default_scale: Vector2, action: String, on_finished: Callable) -> void:
	glove.position = default_pos
	glove.scale = default_scale
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + UPPERCUT_OFFSET, UPPERCUT_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", UPPERCUT_SCALE, UPPERCUT_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(func(): punch_impact.emit(DAMAGE_UPPERCUT, action))
	tween.tween_interval(0.04)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos, UPPERCUT_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", default_scale, UPPERCUT_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(on_finished)


func _play_guard_enter() -> void:
	left_glove.position = _left_default_pos
	right_glove.position = _right_default_pos
	_set_glove_hit(left_glove, false)
	_set_glove_hit(right_glove, false)
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(left_glove, "scale", GUARD_SCALE, GUARD_DURATION_IN).set_trans(Tween.TRANS_QUAD)
	tween.tween_property(right_glove, "scale", GUARD_SCALE, GUARD_DURATION_IN).set_trans(Tween.TRANS_QUAD)
	tween.set_parallel(false)


func _play_guard_exit(on_finished: Callable) -> void:
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(left_glove, "scale", _left_default_scale, GUARD_DURATION_OUT).set_trans(Tween.TRANS_QUAD)
	tween.tween_property(right_glove, "scale", _right_default_scale, GUARD_DURATION_OUT).set_trans(Tween.TRANS_QUAD)
	tween.set_parallel(false)
	tween.tween_callback(on_finished)


func _play_dodge(is_left: bool, on_finished: Callable) -> void:
	var start_pos := position
	var dir := -1.0 if is_left else 1.0
	var shift := Vector2(dir * 35.0, 0.0)
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "position", start_pos + shift, 0.06).set_trans(Tween.TRANS_QUAD)
	tween.tween_property(self, "position", start_pos, 0.08).set_trans(Tween.TRANS_QUAD)
	tween.tween_callback(on_finished)


## 레거시: Main에서 실시간 좌표 모드일 때만 사용 (현재는 사용 안 함)
func update_gloves_position(left_pos: Vector2, right_pos: Vector2) -> void:
	left_glove.position = left_pos
	right_glove.position = right_pos
