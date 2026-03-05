extends Node2D
## 고정 글러브 + 행동 트리거 애니 (Leftovers KO! 스타일)
## play_action("jab_l"|"jab_r"|"upper_l"|"upper_r"|"hook_l"|"hook_r"|"guard") 호출 시 해당 Tween 재생, 액티브 구간에만 히트박스 ON

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


func _ready() -> void:
	_left_default_pos = left_glove.position
	_right_default_pos = right_glove.position
	_left_default_scale = left_glove.scale
	_right_default_scale = right_glove.scale
	_set_glove_hit(left_glove, false)
	_set_glove_hit(right_glove, false)


func _process(_delta: float) -> void:
	# 키보드 폴백: 5가지 액션 테스트
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
	elif Input.is_action_just_pressed("guard"):
		play_action("guard")


func play_action(action: String) -> void:
	if _busy and action != "guard_end" and action != "dodge_l" and action != "dodge_r":
		return
	match action:
		"jab_l":
			if not GameState.consume_stamina(GameState.STAMINA_JAB):
				return
			_busy = true
			_play_jab(left_glove, _left_default_pos, _left_default_scale, func(): _busy = false)
		"jab_r":
			if not GameState.consume_stamina(GameState.STAMINA_JAB):
				return
			_busy = true
			_play_jab(right_glove, _right_default_pos, _right_default_scale, func(): _busy = false)
		"upper_l":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return
			_busy = true
			_play_uppercut(left_glove, _left_default_pos, _left_default_scale, func(): _busy = false)
		"upper_r":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return
			_busy = true
			_play_uppercut(right_glove, _right_default_pos, _right_default_scale, func(): _busy = false)
		"hook_l":
			if not GameState.consume_stamina(GameState.STAMINA_HOOK):
				return
			_busy = true
			_play_hook(left_glove, _left_default_pos, _left_default_scale, true, func(): _busy = false)
		"hook_r":
			if not GameState.consume_stamina(GameState.STAMINA_HOOK):
				return
			_busy = true
			_play_hook(right_glove, _right_default_pos, _right_default_scale, false, func(): _busy = false)
		"dodge_l":
			_busy = true
			_play_dodge(true, func(): _busy = false)
		"dodge_r":
			_busy = true
			_play_dodge(false, func(): _busy = false)
		"guard":
			if _guarding:
				return
			_guarding = true
			_play_guard_enter()
		"guard_end":
			if not _guarding:
				return
			_guarding = false
			_busy = true
			_play_guard_exit(func(): _busy = false)
		"jog":
			# 제자리걸음은 스태미너만 GameState에서 회복, 시각 연출 없음
			pass
		_:
			pass


func _set_glove_hit(glove: Area2D, enabled: bool) -> void:
	if not glove:
		return
	glove.set_collision_layer_value(HIT_LAYER_BIT, enabled)


func _play_jab(glove: Area2D, default_pos: Vector2, default_scale: Vector2, on_finished: Callable) -> void:
	glove.position = default_pos
	glove.scale = default_scale
	_set_glove_hit(glove, false)
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(glove, "scale", PUNCH_SCALE, JAB_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_callback(func(): _set_glove_hit(glove, true))
	tween.tween_interval(0.03)
	tween.tween_callback(func(): _set_glove_hit(glove, false))
	tween.tween_property(glove, "scale", default_scale, JAB_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.tween_callback(on_finished)


func _play_hook(glove: Area2D, default_pos: Vector2, default_scale: Vector2, is_left: bool, on_finished: Callable) -> void:
	var offset := HOOK_OFFSET_LEFT if is_left else HOOK_OFFSET_RIGHT
	glove.position = default_pos
	glove.scale = default_scale
	_set_glove_hit(glove, false)
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + offset, HOOK_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", HOOK_SCALE, HOOK_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(func(): _set_glove_hit(glove, true))
	tween.tween_interval(0.035)
	tween.tween_callback(func(): _set_glove_hit(glove, false))
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos, HOOK_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", default_scale, HOOK_DURATION_IN).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(on_finished)


func _play_uppercut(glove: Area2D, default_pos: Vector2, default_scale: Vector2, on_finished: Callable) -> void:
	glove.position = default_pos
	glove.scale = default_scale
	_set_glove_hit(glove, false)
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + UPPERCUT_OFFSET, UPPERCUT_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.tween_property(glove, "scale", UPPERCUT_SCALE, UPPERCUT_DURATION_OUT).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(func(): _set_glove_hit(glove, true))
	tween.tween_interval(0.04)
	tween.tween_callback(func(): _set_glove_hit(glove, false))
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
