extends Node2D
## 고정 글러브 + 행동 트리거 애니 (Leftovers KO! 스타일)
## 피격 판정: 히트박스 없음. 임팩트 시점에 punch_impact 시그널만 발생 → Main에서 적 회피 여부로 hit/miss 처리

signal punch_impact(damage: float, punch_type: String)  # punch_type: "punch_l" | "punch_r" | "upper_l" | "upper_r"
signal action_performed(action: String)

# 기본 배율 1.0일 때 잽/어퍼 — 적 max_hp·공격 간격은 main.tscn·enemy.gd에서 조정
const DAMAGE_PUNCH := 3.0
const DAMAGE_UPPERCUT := 6.0

## 잽: 짧은 윈드업(당김) → 앞·위로 길게 뻗는 스트레이트 (어퍼와 실루엣 분리)
const PUNCH_WINDUP_OFFSET_L := Vector2(-16, 12)
const PUNCH_WINDUP_OFFSET_R := Vector2(16, 12)
const PUNCH_STRIKE_OFFSET_L := Vector2(58, -64)
const PUNCH_STRIKE_OFFSET_R := Vector2(-58, -64)
const PUNCH_STRIKE_SCALE_MUL := Vector2(1.28, 1.18)
const PUNCH_WINDUP_DURATION := 0.035
const PUNCH_STRIKE_DURATION := 0.058
const PUNCH_RETURN_DURATION := 0.082
const PUNCH_WINDUP_SCALE := 0.86

## 어퍼: 몸·주먹을 살짝 내려 받은 뒤 크게 위로 아크 (잽보다 세로·스케일 과장)
const UPPERCUT_DIP_OFFSET := Vector2(0, 26)
const UPPERCUT_ARC_OFFSET_L := Vector2(34, -128)
const UPPERCUT_ARC_OFFSET_R := Vector2(-34, -128)
const UPPERCUT_STRIKE_SCALE_MUL := Vector2(1.38, 1.52)
const UPPERCUT_DIP_DURATION := 0.052
const UPPERCUT_RISE_DURATION := 0.095
const UPPERCUT_RETURN_DURATION := 0.098
const GUARD_SCALE := Vector2(1.4, 1.4)
const GUARD_DURATION_IN := 0.05
const GUARD_DURATION_OUT := 0.06
# 가드 최소 유지 시간(초). 이 시간 지나야 guard_end로 해제 가능
const GUARD_MIN_DURATION := 0.25
const PUNCH_TRANS := Tween.TRANS_QUINT
## 웹캠(UDP) 펀치만 트윈 길이에 곱함. 1보다 작을수록 임팩트까지 시간 단축(키보드 타이밍은 유지).
const UDP_PUNCH_TIME_SCALE := 0.42

const PUNCH_L_BODY_TEX_BASE := "res://work_images/output/burger_punch_l_"
const PUNCH_L_BODY_FRAME_MAX := 8
## SpriteFrames frame duration = relative weight; real seconds = sum_rel / fps.
const PUNCH_L_BODY_REL1 := 0.026
const PUNCH_L_BODY_REL2 := 0.022
const PUNCH_L_BODY_REL3 := 0.022
const PUNCH_L_BODY_REL4 := 0.078

const HIT_LAYER_BIT := 2  # collision_layer 2 = 글러브

@onready var left_glove: Area2D = $LeftGlove
@onready var right_glove: Area2D = $RightGlove
## 왼손 잽 몸통 연출(BodySprite 노드 없으면 글러브만 동작).
@onready var _body_sprite: AnimatedSprite2D = get_node_or_null("BodySprite") as AnimatedSprite2D

var _guard_spark: CPUParticles2D
var _guard_flash: CPUParticles2D
var _hurt_spark: CPUParticles2D
var _hurt_splat: CPUParticles2D
var _sfx_guard: AudioStreamPlayer
var _sfx_hurt: AudioStreamPlayer

var _left_default_pos: Vector2
var _right_default_pos: Vector2
var _left_default_scale: Vector2
var _right_default_scale: Vector2
var _busy_left := false
var _busy_right := false
var _busy_global := false  # guard/dodge 등 전신 동작
var _next_dodge_left: bool = true
var _guarding := false
var _guard_enter_time: float = -999.0
## 웹캠(UDP)으로 가드 들어간 경우: 키를 안 눌러도 유지, guard_end(UDP)까지 유지
var _guard_via_udp: bool = false


func _noop_busy() -> void:
	pass


## 임팩트 직후 busy 해제 → 복귀 트윈이 남아 있어도 같은 손 다음 펀치(UDP)를 바로 받을 수 있음.
func _release_hand_busy_after_impact(action: String) -> void:
	match action:
		"punch_l", "upper_l":
			_busy_left = false
		"punch_r", "upper_r":
			_busy_right = false
		_:
			pass


func _ready() -> void:
	_left_default_pos = left_glove.position
	_right_default_pos = right_glove.position
	_left_default_scale = left_glove.scale
	_right_default_scale = right_glove.scale
	_set_glove_hit(left_glove, false)
	_set_glove_hit(right_glove, false)
	_setup_combat_feedback()
	_setup_punch_l_body_sprite()


func _setup_punch_l_body_sprite() -> void:
	if _body_sprite == null:
		return
	var sf := SpriteFrames.new()
	sf.add_animation("idle")
	sf.set_animation_loop("idle", true)
	var idle_tex: Texture2D = null
	var p1: String = "%s%02d.png" % [PUNCH_L_BODY_TEX_BASE, 1]
	if ResourceLoader.exists(p1):
		idle_tex = ResourceLoader.load(p1, "", ResourceLoader.CACHE_MODE_REPLACE) as Texture2D
	if idle_tex:
		sf.add_frame("idle", idle_tex, 1.0)
	sf.set_animation_speed("idle", 2.0)
	sf.add_animation("punch_l")
	sf.set_animation_loop("punch_l", false)
	var rels: Array[float] = [
		PUNCH_L_BODY_REL1,
		PUNCH_L_BODY_REL2,
		PUNCH_L_BODY_REL3,
		PUNCH_L_BODY_REL4,
	]
	var sum_rel: float = 0.0
	for r: float in rels:
		sum_rel += r
	# Real clip length = sum_rel / animation_fps (SpriteFrames docs).
	var punch_total_sec: float = (
		PUNCH_WINDUP_DURATION + PUNCH_STRIKE_DURATION + 0.016 + PUNCH_RETURN_DURATION
	)
	for idx: int in range(1, PUNCH_L_BODY_FRAME_MAX + 1):
		var path: String = "%s%02d.png" % [PUNCH_L_BODY_TEX_BASE, idx]
		if not ResourceLoader.exists(path):
			continue
		var tex: Texture2D = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as Texture2D
		if tex == null:
			continue
		var fi: int = idx - 1
		var rel: float = rels[fi] if fi < rels.size() else rels[rels.size() - 1]
		sf.add_frame("punch_l", tex, rel)
	if sf.get_frame_count("punch_l") < 1:
		_body_sprite.visible = false
		return
	if sum_rel > 0.0 and punch_total_sec > 0.0:
		sf.set_animation_speed("punch_l", sum_rel / punch_total_sec)
	_body_sprite.sprite_frames = sf
	_body_sprite.speed_scale = 1.0
	_body_sprite.visible = true
	if sf.get_frame_count("idle") > 0:
		_body_sprite.play(&"idle", 1.0)
	else:
		_body_sprite.animation = &"punch_l"
		_body_sprite.set_frame_and_progress(0, 0.0)
		_body_sprite.play(&"punch_l", 1.0)
	if not _body_sprite.animation_finished.is_connected(_on_punch_body_animation_finished):
		_body_sprite.animation_finished.connect(_on_punch_body_animation_finished)


func _on_punch_body_animation_finished() -> void:
	if _body_sprite == null or _body_sprite.sprite_frames == null:
		return
	_body_sprite.speed_scale = 1.0
	if _body_sprite.animation == &"punch_l" and _body_sprite.sprite_frames.has_animation("idle"):
		_body_sprite.play(&"idle", 1.0)


func _play_punch_l_body_motion(glove_time_scale: float = 1.0) -> void:
	if _body_sprite == null or not _body_sprite.visible:
		return
	if _body_sprite.sprite_frames == null:
		return
	if not _body_sprite.sprite_frames.has_animation("punch_l"):
		return
	# 글러브 트윈이 UDP에서 짧아지면 몸통 클립도 같은 비율로 빠르게(싱크 유지).
	var body_scale: float = 1.0 / glove_time_scale if glove_time_scale > 0.001 else 1.0
	_body_sprite.speed_scale = body_scale
	# End of non-loop anim pauses on last frame; reset before replay.
	_body_sprite.stop()
	_body_sprite.animation = &"punch_l"
	_body_sprite.set_frame_and_progress(0, 0.0)
	_body_sprite.play(&"punch_l", 1.0)


func _setup_combat_feedback() -> void:
	_guard_spark = _make_spark_burst(
		"GuardSpark",
		48,
		0.38,
		22.0,
		Color(0.35, 0.95, 1.0),
		140.0,
		320.0,
		3.2,
		7.5
	)
	_guard_flash = _make_spark_burst(
		"GuardFlash",
		22,
		0.22,
		38.0,
		Color(1.0, 1.0, 0.92),
		80.0,
		200.0,
		5.0,
		12.0
	)
	_hurt_spark = _make_spark_burst(
		"HurtSpark",
		40,
		0.32,
		20.0,
		Color(1.0, 0.55, 0.2),
		95.0,
		260.0,
		3.0,
		7.0
	)
	_hurt_splat = _make_spark_burst(
		"HurtSplat",
		28,
		0.26,
		14.0,
		Color(0.95, 0.2, 0.25),
		50.0,
		165.0,
		4.5,
		10.0
	)
	add_child(_guard_spark)
	add_child(_guard_flash)
	add_child(_hurt_spark)
	add_child(_hurt_splat)
	_sfx_guard = AudioStreamPlayer.new()
	_sfx_guard.name = "SfxGuardBlock"
	_sfx_hurt = AudioStreamPlayer.new()
	_sfx_hurt.name = "SfxPlayerHurt"
	for p: AudioStreamPlayer in [_sfx_guard, _sfx_hurt]:
		p.bus = "Master"
		if AudioServer.get_bus_index("SFX") >= 0:
			p.bus = "SFX"
		add_child(p)
	_try_load_hit_stream(_sfx_guard)
	_try_load_hit_stream(_sfx_hurt)


func _try_load_hit_stream(player: AudioStreamPlayer) -> void:
	for path: String in ["res://assets/audio/sfx/sfx_punch_hit.wav"]:
		if ResourceLoader.exists(path):
			var res := load(path)
			if res is AudioStream:
				player.stream = res as AudioStream
				return


func _make_spark_burst(
		p_name: String,
		amount: int,
		lifetime: float,
		emission_r: float,
		col: Color,
		vmin: float,
		vmax: float,
		smin: float,
		smax: float
	) -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.name = p_name
	p.z_index = 12
	p.z_as_relative = false
	p.emitting = false
	p.one_shot = true
	p.explosiveness = 0.9
	p.amount = amount
	p.lifetime = lifetime
	p.lifetime_randomness = 0.35
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = emission_r
	p.direction = Vector2(0, -1)
	p.spread = 180.0
	p.gravity = Vector2(0, 220)
	p.initial_velocity_min = vmin
	p.initial_velocity_max = vmax
	p.scale_amount_min = smin
	p.scale_amount_max = smax
	p.color = col
	p.hue_variation_min = -0.05
	p.hue_variation_max = 0.05
	return p


func _glove_midpoint_local() -> Vector2:
	if left_glove and right_glove:
		return (left_glove.position + right_glove.position) * 0.5
	return Vector2.ZERO


func _burst_particles_at_mid(particles: CPUParticles2D) -> void:
	if particles == null:
		return
	particles.position = _glove_midpoint_local()
	particles.restart()
	particles.emitting = true


## Main: 적 공격을 가드로 막았을 때
func play_guard_block_fx() -> void:
	_burst_particles_at_mid(_guard_spark)
	_burst_particles_at_mid(_guard_flash)
	if _sfx_guard and _sfx_guard.stream:
		_sfx_guard.pitch_scale = 1.38
		_sfx_guard.volume_db = -2.5
		_sfx_guard.play()


## Main: 가드 없이 플레이어가 맞았을 때
func play_take_damage_fx() -> void:
	_burst_particles_at_mid(_hurt_spark)
	_burst_particles_at_mid(_hurt_splat)
	if _sfx_hurt and _sfx_hurt.stream:
		_sfx_hurt.pitch_scale = 0.7
		_sfx_hurt.volume_db = -1.0
		_sfx_hurt.play()
	_flash_gloves_damage()


func _flash_gloves_damage() -> void:
	var sprites: Array[CanvasItem] = []
	for g in [left_glove, right_glove]:
		if g == null:
			continue
		var spr: Node = g.get_node_or_null("Sprite2D")
		if spr is CanvasItem:
			sprites.append(spr as CanvasItem)
	if sprites.is_empty():
		return
	var tw := create_tween()
	tw.set_parallel(true)
	for c in sprites:
		tw.tween_property(c, "modulate", Color(1.0, 0.38, 0.38, 1.0), 0.05)
	tw.set_parallel(false)
	tw.set_parallel(true)
	for c in sprites:
		tw.tween_property(c, "modulate", Color.WHITE, 0.16)


func _process(_delta: float) -> void:
	# 키보드 가드만: 키를 뗐으면 즉시 해제. 웹캠(UDP) 가드는 guard_end 패킷으로만 해제
	if _guarding and not _guard_via_udp and not Input.is_action_pressed("guard"):
		if _busy_global:
			return
		_guarding = false
		GameState.set_guarding(false)
		_busy_global = true
		_play_guard_exit(func(): _busy_global = false)
		return
	if _busy_global:
		return
	if Input.is_action_just_pressed("punch_left"):
		play_action("punch_l")
	elif Input.is_action_just_pressed("punch_right"):
		play_action("punch_r")
	elif Input.is_action_just_pressed("upper_left"):
		play_action("upper_l")
	elif Input.is_action_just_pressed("upper_right"):
		play_action("upper_r")
	elif Input.is_action_just_pressed("guard"):
		play_action("guard")


func play_action(action: String, via_udp: bool = false) -> bool:
	# 연타 체감 개선: 왼손/오른손 동작은 각각의 글러브 busy만 막고, 반대손은 허용.
	# guard/dodge 등 전신 동작은 global busy로 막음.
	if _busy_global and action != "guard_end" and action != "dodge":
		return false
	if action in ["punch_l", "upper_l"] and _busy_left:
		return false
	if action in ["punch_r", "upper_r"] and _busy_right:
		return false
	var punch_scale: float = UDP_PUNCH_TIME_SCALE if via_udp else 1.0
	match action:
		"punch_l":
			if not GameState.consume_stamina(GameState.STAMINA_PUNCH):
				return false
			_busy_left = true
			GameState.record_action_for_calorie("punch_l")
			action_performed.emit("punch_l")
			_play_punch_l_body_motion(punch_scale)
			_play_punch(left_glove, _left_default_pos, _left_default_scale, "punch_l", _noop_busy, punch_scale)
			return true
		"punch_r":
			if not GameState.consume_stamina(GameState.STAMINA_PUNCH):
				return false
			_busy_right = true
			GameState.record_action_for_calorie("punch_r")
			action_performed.emit("punch_r")
			_play_punch(
				right_glove, _right_default_pos, _right_default_scale, "punch_r", _noop_busy, punch_scale
			)
			return true
		"upper_l":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return false
			_busy_left = true
			GameState.record_action_for_calorie("upper_l")
			action_performed.emit("upper_l")
			_play_uppercut(
				left_glove, _left_default_pos, _left_default_scale, "upper_l", _noop_busy, punch_scale
			)
			return true
		"upper_r":
			if not GameState.consume_stamina(GameState.STAMINA_UPPERCUT):
				return false
			_busy_right = true
			GameState.record_action_for_calorie("upper_r")
			action_performed.emit("upper_r")
			_play_uppercut(
				right_glove, _right_default_pos, _right_default_scale, "upper_r", _noop_busy, punch_scale
			)
			return true
		"dodge":
			_busy_global = true
			GameState.record_action_for_calorie("dodge")
			# 회피 판정 대신: 스쿼트 시 플레이어 HP 10% 회복
			GameState.apply_squat_heal(0.10)
			action_performed.emit("squat")
			_play_dodge(_next_dodge_left, func(): _busy_global = false)
			_next_dodge_left = not _next_dodge_left
			return true
		"guard":
			if _guarding:
				return false
			_guard_via_udp = via_udp
			_guarding = true
			GameState.record_action_for_calorie("guard")
			action_performed.emit("guard")
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
			_busy_global = true
			_play_guard_exit(func(): _busy_global = false)
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


func _play_punch(
	glove: Area2D,
	default_pos: Vector2,
	default_scale: Vector2,
	action: String,
	on_finished: Callable,
	time_scale: float = 1.0
) -> void:
	var ts: float = maxf(0.05, time_scale)
	glove.position = default_pos
	glove.scale = default_scale
	var wind: Vector2 = PUNCH_WINDUP_OFFSET_L if action == "punch_l" else PUNCH_WINDUP_OFFSET_R
	var strike: Vector2 = PUNCH_STRIKE_OFFSET_L if action == "punch_l" else PUNCH_STRIKE_OFFSET_R
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	# 1) 당김(어깨·팔꿈치 느낌)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + wind, PUNCH_WINDUP_DURATION * ts).set_trans(
		Tween.TRANS_QUAD
	)
	tween.tween_property(glove, "scale", default_scale * PUNCH_WINDUP_SCALE, PUNCH_WINDUP_DURATION * ts).set_trans(
		Tween.TRANS_QUAD
	)
	tween.set_parallel(false)
	# 2) 앞·위로 스냅
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + strike, PUNCH_STRIKE_DURATION * ts).set_trans(
		Tween.TRANS_EXPO
	)
	tween.tween_property(
		glove,
		"scale",
		Vector2(default_scale.x * PUNCH_STRIKE_SCALE_MUL.x, default_scale.y * PUNCH_STRIKE_SCALE_MUL.y),
		PUNCH_STRIKE_DURATION * ts
	).set_trans(PUNCH_TRANS)
	tween.set_parallel(false)
	tween.tween_callback(func(): punch_impact.emit(DAMAGE_PUNCH, action))
	tween.tween_callback(func(): _release_hand_busy_after_impact(action))
	tween.tween_interval(0.016 * ts)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos, PUNCH_RETURN_DURATION * ts).set_trans(Tween.TRANS_QUAD)
	tween.tween_property(glove, "scale", default_scale, PUNCH_RETURN_DURATION * ts).set_trans(Tween.TRANS_QUAD)
	tween.set_parallel(false)
	tween.tween_callback(on_finished)


func _play_uppercut(
	glove: Area2D,
	default_pos: Vector2,
	default_scale: Vector2,
	action: String,
	on_finished: Callable,
	time_scale: float = 1.0
) -> void:
	var ts: float = maxf(0.05, time_scale)
	glove.position = default_pos
	glove.scale = default_scale
	var arc: Vector2 = UPPERCUT_ARC_OFFSET_L if action == "upper_l" else UPPERCUT_ARC_OFFSET_R
	var tween := create_tween()
	tween.set_ease(Tween.EASE_OUT)
	# 1) 로드: 아래로 살짝 숙임
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + UPPERCUT_DIP_OFFSET, UPPERCUT_DIP_DURATION * ts).set_trans(
		Tween.TRANS_QUAD
	)
	tween.tween_property(glove, "scale", default_scale * 0.88, UPPERCUT_DIP_DURATION * ts).set_trans(
		Tween.TRANS_QUAD
	)
	tween.set_parallel(false)
	# 2) 크게 위로 아크
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos + arc, UPPERCUT_RISE_DURATION * ts).set_trans(
		Tween.TRANS_EXPO
	)
	tween.tween_property(
		glove,
		"scale",
		Vector2(default_scale.x * UPPERCUT_STRIKE_SCALE_MUL.x, default_scale.y * UPPERCUT_STRIKE_SCALE_MUL.y),
		UPPERCUT_RISE_DURATION * ts
	).set_trans(Tween.TRANS_BACK)
	tween.set_parallel(false)
	tween.tween_callback(func(): punch_impact.emit(DAMAGE_UPPERCUT, action))
	tween.tween_callback(func(): _release_hand_busy_after_impact(action))
	tween.tween_interval(0.02 * ts)
	tween.set_parallel(true)
	tween.tween_property(glove, "position", default_pos, UPPERCUT_RETURN_DURATION * ts).set_trans(
		Tween.TRANS_QUAD
	)
	tween.tween_property(glove, "scale", default_scale, UPPERCUT_RETURN_DURATION * ts).set_trans(Tween.TRANS_QUAD)
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
