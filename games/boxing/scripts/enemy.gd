extends Node2D
## 적 캐릭터 (main.tscn Enemy/AnimatedSprite2D — IDLE burger_idle_*, ATTACK burger_punch_l_01~04, KO burger_ko_*)
## 피격 시: 펀치 종류별 위치·규모 다른 CPUParticles2D 다층 연출 + 모듈레이트 플래시·SFX.
## 히트박스 없음: 피격은 "플레이어 공격 임팩트 시점에 적이 회피 중인가"로만 판정.
## 회피 중이면 빗나감, 아니면 무조건 히트.

signal hit_received(damage: float)
signal attack_missed  # 플레이어 공격이 회피로 빗나갔을 때 (연출/사운드용)
signal enemy_attack(damage: float)  # 적이 플레이어를 공격할 때 (Main에서 가드/HP 처리)
signal died

@export var max_hp := 100.0
@export var ai_enabled: bool = true
var current_hp: float

## 회피: 대기(랜덤) 후 evade_duration 동안 회피. 공격 텔레그래프 중엔 '시작'만 막고 대기 타이머는 쌓임.
@export var evade_duration := 0.38
@export var evade_idle_min := 0.35
@export var evade_idle_max := 1.1
## 공격: 랜덤 간격마다 시도. 회피 중에도 다음 공격까지 시간은 흐름(벽시계에 가깝게). 텔레그래프 중엔 시작만 막음.
@export var attack_delay_min := 1.4
@export var attack_delay_max := 2.45
@export var attack_telegraph := 0.7  # 공격 PNG 없을 때 위치 트윈 전체 길이(초). 임팩트 타이밍 비율에도 사용
## 공격 모션 각 프레임 실제 시간(초). 4프레면 합계 4×이 값(기본 1초).
@export var attack_frame_duration_sec := 0.25
## 플레이어 피격 판정: 몇 번째 프레임 **시점**(0부터). 2 = 세 번째(03 임팩트)
@export var enemy_attack_impact_frame_index := 2
@export var attack_damage := 24.0
## 타격 파티클 기본 위치 (미분류 시)
@export var hit_effect_offset: Vector2 = Vector2(0, -48)
## 어퍼컷: 상단(머리/번) 쪽 — 왼손은 좌상단, 오른손은 우상단
@export var hit_upper_l_offset: Vector2 = Vector2(-56, -96)
@export var hit_upper_r_offset: Vector2 = Vector2(56, -96)
## 잽·훅: 몸통 중앙 높이 — 왼쪽/오른쪽
@export var hit_jab_l_offset: Vector2 = Vector2(-44, -10)
@export var hit_jab_r_offset: Vector2 = Vector2(44, -10)
## 회피 시 스프라이트를 좌/우로 이동하는 픽셀 거리(랜덤 방향)
@export var evade_dodge_offset_pixels: float = 72.0

var _is_evading := false
var _evade_side_sign: float = 1.0
var _is_attacking := false
## 회피 창이 끝날 때까지 경과(초). 회피 중에만 증가.
var _evade_window_elapsed: float = 0.0
## 다음 회피까지 대기(초) 목표치 — randf_range(evade_idle_min, evade_idle_max)
var _next_evade_idle_delay: float = 2.0
var _evade_idle_accum: float = 0.0
## 다음 공격까지 대기(초) 목표치 — randf_range(attack_delay_min, attack_delay_max)
var _next_attack_delay: float = 4.0
var _attack_idle_accum: float = 0.0
var _attack_hit_emitted: bool = false

const IDLE_TEXTURE_BASE := "res://work_images/output/burger_idle_"
## 프레임당 재생 시간(초). (0.3초/프레임에서 한 번 더 2배 느리게)
const IDLE_FRAME_DURATION_SEC := 0.6
const IDLE_FRAME_PATH_MAX := 32
const FALLBACK_ENEMY_TEXTURE := "res://assets/textures/characters/placeholder_enemy.svg"

## 플레이어 펀치 몸통과 동일: work_images/output/burger_punch_l_01.png … _04.png
const ATTACK_TEXTURE_BASE := "res://work_images/output/burger_punch_l_"
const ATTACK_FRAME_PATH_MAX := 4

const HIT_TEXTURE_BASE := "res://work_images/output/burger_hit_"
const HIT_FRAME_PATH_MAX := 4
const HIT_FRAME_DURATION_SEC := 0.2

const KO_TEXTURE_BASE := "res://work_images/output/burger_ko_"
## KO만 idle보다 크게(캔버스·누끼 후 실제 그림 크기 차이 보정)
const KO_DISPLAY_SCALE := 2.0
## KO 모션은 프레임을 길게 잡아 천천히 재생 (SpriteFrames 프레임당 초; 값↑ = 느림)
const KO_FRAME_DURATION_SEC := 1.25
const KO_FRAME_PATH_MAX := 3
## KO 재생 끝난 뒤(마지막 프레임·시체 자세) 스프라이트를 화면 아래로 살짝 내림. Y+ = 아래
@export var ko_corpse_position_nudge: Vector2 = Vector2(0, 36)

@onready var hitbox: Area2D = $Hitbox
@onready var sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var hit_sound: AudioStreamPlayer = $HitSound

var _hit_particles: CPUParticles2D
var _hit_particles_splat: CPUParticles2D
var _hit_star_pop: CPUParticles2D
var _hit_accent_burst: CPUParticles2D

## HP 0 이후 KO 연출 중이면 true. Main에서 UDP 차단·펀치 무시용
var _is_dead := false
## 씬(AnimatedSprite2D scale) 기준 — KO 시 이 값에 KO_DISPLAY_SCALE 곱함
var _sprite_scale_base: Vector2 = Vector2.ONE
var _hit_anim_ticket: int = 0


func _ready() -> void:
	current_hp = max_hp
	_setup_idle_sprite_frames()
	if sprite:
		_sprite_scale_base = sprite.scale
	# 히트박스는 사용하지 않음. 피격은 main에서 punch_impact + is_evading()으로 처리
	if hitbox:
		hitbox.set_collision_layer_value(1, false)
		hitbox.set_collision_mask_value(2, false)
	_setup_hit_particles()
	_roll_next_attack_delay()
	_roll_next_evade_idle_delay()


func _setup_idle_sprite_frames() -> void:
	if sprite == null:
		return
	var sf := SpriteFrames.new()
	sf.add_animation("idle")
	sf.set_animation_loop("idle", true)
	# 로컬 작업/에셋 정리 중에 프레임 번호가 중간에 비거나 01이 빠져도 동작하도록:
	# "없으면 종료"가 아니라 "없으면 건너뛰기"로 로드한다.
	for idx: int in range(1, IDLE_FRAME_PATH_MAX + 1):
		var p: String = "%s%02d.png" % [IDLE_TEXTURE_BASE, idx]
		if not ResourceLoader.exists(p):
			continue
		var tex: Texture2D = ResourceLoader.load(
			p, "", ResourceLoader.CACHE_MODE_REPLACE
		) as Texture2D
		if tex == null:
			push_warning("Enemy: IDLE 텍스처 로드 실패: %s" % p)
			continue
		sf.add_frame("idle", tex, IDLE_FRAME_DURATION_SEC)
	if sf.get_frame_count("idle") < 1:
		# 최후의 안전장치: 프레임이 없으면 placeholder라도 보여준다(적이 '안 뜬' 상태 방지)
		var fallback_tex: Texture2D = null
		if ResourceLoader.exists(FALLBACK_ENEMY_TEXTURE):
			fallback_tex = load(FALLBACK_ENEMY_TEXTURE) as Texture2D
		if fallback_tex:
			sf.add_frame("idle", fallback_tex, 1.0)
		else:
			push_error("Enemy: IDLE 프레임이 없고 fallback 텍스처도 없습니다. %s" % FALLBACK_ENEMY_TEXTURE)
			return
	sf.add_animation("ko")
	sf.set_animation_loop("ko", false)
	for kidx: int in range(1, KO_FRAME_PATH_MAX + 1):
		var kp: String = "%s%02d.png" % [KO_TEXTURE_BASE, kidx]
		if not ResourceLoader.exists(kp):
			continue
		var ktex: Texture2D = ResourceLoader.load(
			kp, "", ResourceLoader.CACHE_MODE_REPLACE
		) as Texture2D
		if ktex == null:
			push_warning("Enemy: KO 텍스처 로드 실패: %s" % kp)
			continue
		sf.add_frame("ko", ktex, KO_FRAME_DURATION_SEC)
	# 공격: burger_punch_l_01 … _04 (없으면 기존 위치 트윈만 사용)
	var attack_textures: Array[Texture2D] = []
	for aidx: int in range(1, ATTACK_FRAME_PATH_MAX + 1):
		var ap: String = "%s%02d.png" % [ATTACK_TEXTURE_BASE, aidx]
		if not ResourceLoader.exists(ap):
			continue
		var atex: Texture2D = ResourceLoader.load(
			ap, "", ResourceLoader.CACHE_MODE_REPLACE
		) as Texture2D
		if atex == null:
			push_warning("Enemy: ATTACK 텍스처 로드 실패: %s" % ap)
			continue
		attack_textures.append(atex)
	if attack_textures.size() >= 1:
		sf.add_animation("attack")
		sf.set_animation_loop("attack", false)
		for atex in attack_textures:
			# 상대 duration 1.0 = 동일 길이 프레임. 실제 초는 set_animation_speed로 맞춤.
			sf.add_frame("attack", atex, 1.0)
		var sec_per_frame: float = maxf(attack_frame_duration_sec, 0.001)
		sf.set_animation_speed("attack", 1.0 / sec_per_frame)
	# 피격(단일/다중 프레임 지원): burger_hit_01 ... _NN
	var hit_textures: Array[Texture2D] = []
	for hidx: int in range(1, HIT_FRAME_PATH_MAX + 1):
		var hp: String = "%s%02d.png" % [HIT_TEXTURE_BASE, hidx]
		if not ResourceLoader.exists(hp):
			continue
		var htex: Texture2D = ResourceLoader.load(hp, "", ResourceLoader.CACHE_MODE_REPLACE) as Texture2D
		if htex == null:
			push_warning("Enemy: HIT 텍스처 로드 실패: %s" % hp)
			continue
		hit_textures.append(htex)
	if hit_textures.size() >= 1:
		sf.add_animation("hit")
		sf.set_animation_loop("hit", false)
		for htex in hit_textures:
			sf.add_frame("hit", htex, 1.0)
		sf.set_animation_speed("hit", 1.0 / maxf(HIT_FRAME_DURATION_SEC, 0.001))
	sprite.sprite_frames = sf
	sprite.play("idle")


func _setup_hit_particles() -> void:
	_hit_particles = CPUParticles2D.new()
	_hit_particles.name = "HitSparkParticles"
	_hit_particles.z_index = 8
	_hit_particles.z_as_relative = false
	_hit_particles.position = hit_effect_offset
	_hit_particles.emitting = false
	_hit_particles.one_shot = true
	_hit_particles.explosiveness = 0.92
	_hit_particles.amount = 56
	_hit_particles.lifetime = 0.34
	_hit_particles.lifetime_randomness = 0.4
	_hit_particles.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	_hit_particles.emission_sphere_radius = 24.0
	_hit_particles.direction = Vector2(0, -1)
	_hit_particles.spread = 180.0
	_hit_particles.gravity = Vector2(0, 300)
	_hit_particles.initial_velocity_min = 110.0
	_hit_particles.initial_velocity_max = 300.0
	_hit_particles.angular_velocity_min = -10.0
	_hit_particles.angular_velocity_max = 10.0
	_hit_particles.scale_amount_min = 3.5
	_hit_particles.scale_amount_max = 8.5
	_hit_particles.color = Color(1.0, 0.92, 0.4)
	_hit_particles.hue_variation_min = -0.06
	_hit_particles.hue_variation_max = 0.06
	# 스프라이트 중심에서 터지도록 부모를 AnimatedSprite2D로 (햄버거 그림 기준)
	if sprite is Node2D:
		(sprite as Node2D).add_child(_hit_particles)
	else:
		add_child(_hit_particles)

	_hit_particles_splat = CPUParticles2D.new()
	_hit_particles_splat.name = "HitSplatParticles"
	_hit_particles_splat.z_index = 7
	_hit_particles_splat.z_as_relative = false
	_hit_particles_splat.position = hit_effect_offset
	_hit_particles_splat.emitting = false
	_hit_particles_splat.one_shot = true
	_hit_particles_splat.explosiveness = 0.88
	_hit_particles_splat.amount = 26
	_hit_particles_splat.lifetime = 0.28
	_hit_particles_splat.lifetime_randomness = 0.25
	_hit_particles_splat.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	_hit_particles_splat.emission_sphere_radius = 15.0
	_hit_particles_splat.direction = Vector2(0, -1)
	_hit_particles_splat.spread = 180.0
	_hit_particles_splat.gravity = Vector2(0, 400)
	_hit_particles_splat.initial_velocity_min = 55.0
	_hit_particles_splat.initial_velocity_max = 175.0
	_hit_particles_splat.scale_amount_min = 5.0
	_hit_particles_splat.scale_amount_max = 11.0
	_hit_particles_splat.color = Color(0.95, 0.25, 0.2)
	if sprite is Node2D:
		(sprite as Node2D).add_child(_hit_particles_splat)
	else:
		add_child(_hit_particles_splat)

	_hit_star_pop = _make_hit_star_pop()
	_hit_accent_burst = _make_hit_accent_burst()
	if sprite is Node2D:
		(sprite as Node2D).add_child(_hit_star_pop)
		(sprite as Node2D).add_child(_hit_accent_burst)
	else:
		add_child(_hit_star_pop)
		add_child(_hit_accent_burst)


func _make_hit_star_pop() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.name = "HitStarPop"
	p.z_index = 9
	p.z_as_relative = false
	p.emitting = false
	p.one_shot = true
	p.explosiveness = 0.96
	p.amount = 72
	p.lifetime = 0.42
	p.lifetime_randomness = 0.35
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 18.0
	p.direction = Vector2(0, -1)
	p.spread = 180.0
	p.gravity = Vector2(0, 180)
	p.initial_velocity_min = 140.0
	p.initial_velocity_max = 420.0
	p.angular_velocity_min = -14.0
	p.angular_velocity_max = 14.0
	p.scale_amount_min = 5.0
	p.scale_amount_max = 14.0
	p.color = Color(1.0, 1.0, 0.95)
	p.hue_variation_min = -0.08
	p.hue_variation_max = 0.08
	return p


func _make_hit_accent_burst() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.name = "HitAccentBurst"
	p.z_index = 7
	p.z_as_relative = false
	p.emitting = false
	p.one_shot = true
	p.explosiveness = 0.82
	p.amount = 48
	p.lifetime = 0.38
	p.lifetime_randomness = 0.45
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 16.0
	p.direction = Vector2(0, -0.3)
	p.spread = 120.0
	p.gravity = Vector2(0, 420)
	p.initial_velocity_min = 90.0
	p.initial_velocity_max = 260.0
	p.scale_amount_min = 3.0
	p.scale_amount_max = 9.0
	p.color = Color(1.0, 0.55, 0.15)
	return p


func _hit_vfx_profile(punch_type: String) -> Dictionary:
	var t := punch_type
	if t.is_empty():
		t = "punch_l"
	var is_upper: bool = t.begins_with("upper")
	var is_left: bool = t.ends_with("_l")
	if is_upper:
		return {
			"offset": (hit_upper_l_offset if is_left else hit_upper_r_offset),
			"scale": 1.88,
			"upper": true,
		}
	if t.begins_with("punch"):
		return {
			"offset": (hit_jab_l_offset if is_left else hit_jab_r_offset),
			"scale": 1.38,
			"upper": false,
		}
	return {"offset": hit_effect_offset, "scale": 1.12, "upper": false}


func _burst_hit_particles(punch_type: String) -> void:
	var prof: Dictionary = _hit_vfx_profile(punch_type)
	var off: Vector2 = prof["offset"]
	var sm: float = prof["scale"]
	var up: bool = prof["upper"]
	var left_side: bool = punch_type.ends_with("_l")

	if _hit_particles:
		_hit_particles.position = off
		_hit_particles.emission_sphere_radius = 22.0 * sm
		_hit_particles.amount = mini(140, int(52 * sm))
		_hit_particles.initial_velocity_max = 260.0 + 120.0 * sm
		_hit_particles.scale_amount_min = 3.2 + 2.0 * sm
		_hit_particles.scale_amount_max = 8.0 + 5.0 * sm
		_hit_particles.color = Color(1.0, 0.95, 0.42) if up else Color(1.0, 0.88, 0.35)
		_hit_particles.restart()
		_hit_particles.emitting = true

	if _hit_particles_splat:
		var splat_off := off + Vector2(-12.0 if left_side else 12.0, 22.0)
		_hit_particles_splat.position = splat_off
		_hit_particles_splat.emission_sphere_radius = (13.0 + 10.0 * sm)
		_hit_particles_splat.amount = mini(110, int(28 * sm))
		_hit_particles_splat.initial_velocity_max = 140.0 + 90.0 * sm
		_hit_particles_splat.color = Color(0.98, 0.22, 0.18) if up else Color(0.92, 0.28, 0.45)
		_hit_particles_splat.restart()
		_hit_particles_splat.emitting = true

	if _hit_star_pop:
		_hit_star_pop.position = off + (Vector2(-14, -18) if left_side else Vector2(14, -18))
		_hit_star_pop.amount = int(92 if up else 56)
		_hit_star_pop.emission_sphere_radius = (26.0 if up else 17.0) * sm
		_hit_star_pop.scale_amount_max = (16.0 if up else 11.0) * sm
		_hit_star_pop.initial_velocity_max = 380.0 + (180.0 if up else 80.0)
		_hit_star_pop.direction = Vector2(-0.55, -0.82).normalized() if left_side else Vector2(0.55, -0.82).normalized()
		_hit_star_pop.restart()
		_hit_star_pop.emitting = true

	if _hit_accent_burst:
		var acc_off := off + (Vector2(-26, 8) if left_side else Vector2(26, 8))
		if up:
			acc_off += Vector2(-18 if left_side else 18, -24)
		_hit_accent_burst.position = acc_off
		_hit_accent_burst.amount = int(58 if up else 42)
		_hit_accent_burst.emission_sphere_radius = (22.0 if up else 15.0) * sm
		_hit_accent_burst.color = Color(1.0, 0.42, 0.08) if up else Color(1.0, 0.72, 0.2)
		var dir_x := -0.92 if left_side else 0.92
		_hit_accent_burst.direction = Vector2(dir_x, -0.35).normalized()
		_hit_accent_burst.spread = 95.0 if up else 140.0
		_hit_accent_burst.restart()
		_hit_accent_burst.emitting = true


func _process(delta: float) -> void:
	if _is_dead:
		return
	if not ai_enabled:
		return
	_update_attack_pattern(delta)
	_update_evade_pattern(delta)


func _roll_next_attack_delay() -> void:
	var lo: float = minf(attack_delay_min, attack_delay_max)
	var hi: float = maxf(attack_delay_min, attack_delay_max)
	_next_attack_delay = randf_range(lo, hi)


func _roll_next_evade_idle_delay() -> void:
	var lo: float = minf(evade_idle_min, evade_idle_max)
	var hi: float = maxf(evade_idle_min, evade_idle_max)
	_next_evade_idle_delay = randf_range(lo, hi)


func _update_evade_pattern(delta: float) -> void:
	if _is_evading:
		_evade_window_elapsed += delta
		if _evade_window_elapsed >= evade_duration:
			_evade_window_elapsed = 0.0
			_set_evading(false)
		return
	# 회피 대기: 공격 텔레그래프 중에도 시간은 흐름. 회피 '시작'만 공격 중엔 금지.
	_evade_idle_accum += delta
	if _is_attacking:
		return
	if _evade_idle_accum >= _next_evade_idle_delay:
		_evade_idle_accum = 0.0
		_roll_next_evade_idle_delay()
		_evade_window_elapsed = 0.0
		_set_evading(true)


func _set_evading(evading: bool) -> void:
	_is_evading = evading
	if sprite:
		var tween := create_tween()
		if evading:
			_evade_side_sign = -1.0 if randf() < 0.5 else 1.0
			var dodge_pos := Vector2(evade_dodge_offset_pixels * _evade_side_sign, -4.0)
			tween.tween_property(sprite, "position", dodge_pos, 0.1).set_trans(Tween.TRANS_QUAD)
		else:
			tween.tween_property(sprite, "position", Vector2.ZERO, 0.12).set_trans(Tween.TRANS_QUAD)


## Main에서 호출: 플레이어 펀치 임팩트 시점에 이 값으로 hit/miss 판정
func is_evading() -> bool:
	return _is_evading


func is_dead() -> bool:
	return _is_dead


func _update_attack_pattern(delta: float) -> void:
	if current_hp <= 0.0:
		return
	# 다음 공격까지 시간은 회피 중에도 흐름(회피로 공격 주기가 2배로 늘어나는 문제 제거)
	if not _is_attacking:
		_attack_idle_accum += delta
	# 실제 공격 시작은 회피·텔레그래프와 겹치지 않게
	if _is_evading or _is_attacking:
		return
	if _attack_idle_accum >= _next_attack_delay:
		_attack_idle_accum = 0.0
		_roll_next_attack_delay()
		_start_attack()


func _enemy_attack_impact_delay_sec(sf: SpriteFrames) -> float:
	## impact_frame_index 프레임이 **시작**되기 직전까지 경과 시간(초)
	var n: int = sf.get_frame_count("attack")
	if n < 1 or sprite == null:
		return 0.0
	var idx: int = clampi(enemy_attack_impact_frame_index, 0, n - 1)
	var fps: float = maxf(sf.get_animation_speed("attack"), 0.001)
	var spd: float = maxf(absf(sprite.get_playing_speed()), 0.001)
	var denom: float = fps * spd
	var sum_sec: float = 0.0
	for i: int in range(idx):
		sum_sec += sf.get_frame_duration("attack", i) / denom
	return sum_sec


func _schedule_enemy_attack_impact_timer(delay_sec: float) -> void:
	if delay_sec <= 0.0:
		_on_enemy_attack_impact_moment()
		return
	get_tree().create_timer(delay_sec).timeout.connect(_on_enemy_attack_impact_moment, CONNECT_ONE_SHOT)


func _on_enemy_attack_impact_moment() -> void:
	if _is_dead or not _is_attacking or _attack_hit_emitted:
		return
	_attack_hit_emitted = true
	enemy_attack.emit(attack_damage)


func _start_attack() -> void:
	_is_attacking = true
	_attack_hit_emitted = false
	if sprite == null:
		var impact_t_null: float = attack_telegraph * (
			float(enemy_attack_impact_frame_index) / maxf(float(ATTACK_FRAME_PATH_MAX), 1.0)
		)
		_schedule_enemy_attack_impact_timer(impact_t_null)
		var tw := create_tween()
		tw.tween_interval(attack_telegraph)
		tw.tween_callback(_finish_enemy_attack_sequence)
		return
	var sf: SpriteFrames = sprite.sprite_frames
	if sf != null and sf.has_animation("attack") and sf.get_frame_count("attack") >= 1:
		sprite.play("attack")
		_schedule_enemy_attack_impact_timer(_enemy_attack_impact_delay_sec(sf))
		sprite.animation_finished.connect(_on_attack_animation_finished, Object.CONNECT_ONE_SHOT)
		return
	# 공격 PNG가 없을 때: 위치 트윈 + 임팩트 시점에 피격(4프레임 기준 비율)
	var orig: Vector2 = sprite.position
	var impact_t: float = attack_telegraph * (
		float(enemy_attack_impact_frame_index) / maxf(float(ATTACK_FRAME_PATH_MAX), 1.0)
	)
	_schedule_enemy_attack_impact_timer(impact_t)
	var tween := create_tween()
	tween.tween_property(sprite, "position", orig + Vector2(0, 12), attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)
	tween.tween_property(sprite, "position", orig, attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)
	tween.tween_callback(_finish_enemy_attack_sequence)


func _on_attack_animation_finished() -> void:
	_finish_enemy_attack_sequence()


func _finish_enemy_attack_sequence() -> void:
	if sprite and sprite.sprite_frames != null and sprite.sprite_frames.has_animation("idle"):
		if not _is_dead:
			sprite.play("idle")
	if not _attack_hit_emitted and not _is_dead and _is_attacking:
		_attack_hit_emitted = true
		enemy_attack.emit(attack_damage)
	_is_attacking = false


func _play_hit_animation_once() -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	if _is_dead:
		return
	if not sprite.sprite_frames.has_animation("hit"):
		return
	var canceled_attack: bool = _is_attacking
	if canceled_attack:
		var attack_done_cb := Callable(self, "_on_attack_animation_finished")
		if sprite.animation_finished.is_connected(attack_done_cb):
			sprite.animation_finished.disconnect(attack_done_cb)
		# 진행 중이던 공격은 피격으로 즉시 취소(피격 모션 우선)
		_is_attacking = false
		_attack_hit_emitted = true
	_hit_anim_ticket += 1
	var ticket: int = _hit_anim_ticket
	sprite.play("hit")
	var restore_after: float = HIT_FRAME_DURATION_SEC * maxf(float(sprite.sprite_frames.get_frame_count("hit")), 1.0)
	get_tree().create_timer(restore_after).timeout.connect(func() -> void:
		if _is_dead:
			return
		if ticket != _hit_anim_ticket:
			return
		if sprite == null or sprite.sprite_frames == null:
			return
		if sprite.sprite_frames.has_animation("idle"):
			sprite.play("idle")
		# 공격 중 피격으로 끊겼다면 hit 종료 후 "새 공격"을 다시 시작.
		if canceled_attack and ai_enabled and not _is_evading and not _is_attacking:
			_start_attack()
		elif canceled_attack:
			# 지금 바로 시작 불가(예: 회피 중)면 다음 업데이트에서 최대한 빨리 재시도.
			_attack_idle_accum = _next_attack_delay
	, CONNECT_ONE_SHOT)


func _flash_hit(punch_type: String = "") -> void:
	if hit_sound:
		hit_sound.play()
	var pt := punch_type if not punch_type.is_empty() else "punch_l"
	_burst_hit_particles(pt)
	_play_hit_animation_once()
	if not sprite:
		return
	# 스케일 트윈은 제거: 연타·트윈 겹침 시 스케일이 누적되어 커지는 현상 방지. 색 플래시만 사용.
	var tween := create_tween()
	tween.tween_property(sprite, "modulate", Color(1.2, 0.35, 0.35), 0.05)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.11)


func take_damage(amount: float, punch_type: String = "punch_l") -> void:
	if _is_dead:
		return
	current_hp -= amount
	hit_received.emit(amount)
	_flash_hit(punch_type)
	if current_hp <= 0:
		current_hp = 0
		_is_dead = true
		_start_ko()


func _start_ko() -> void:
	if sprite:
		var attack_done_cb := Callable(self, "_on_attack_animation_finished")
		if sprite.animation_finished.is_connected(attack_done_cb):
			sprite.animation_finished.disconnect(attack_done_cb)
		_is_attacking = false
		_attack_hit_emitted = true
	if sprite == null or sprite.sprite_frames == null:
		died.emit()
		return
	if not sprite.sprite_frames.has_animation("ko") or sprite.sprite_frames.get_frame_count("ko") < 1:
		died.emit()
		return
	sprite.scale = _sprite_scale_base * KO_DISPLAY_SCALE
	sprite.play("ko")
	# Godot 4 SpriteFrames에는 get_animation_duration() 없음 → 재생 끝과 맞추려면 시그널 사용
	sprite.animation_finished.connect(_on_ko_animation_finished, Object.CONNECT_ONE_SHOT)


func _on_ko_animation_finished() -> void:
	if sprite:
		sprite.position += ko_corpse_position_nudge
	died.emit()


## 훈련장에서 KO 후 같은 적을 풀피로 즉시 재사용할 때 호출.
func reset_for_respawn() -> void:
	current_hp = max_hp
	_is_dead = false
	_is_attacking = false
	_is_evading = false
	_evade_window_elapsed = 0.0
	_evade_idle_accum = 0.0
	_attack_idle_accum = 0.0
	_roll_next_attack_delay()
	_roll_next_evade_idle_delay()
	if sprite:
		sprite.modulate = Color.WHITE
		sprite.scale = _sprite_scale_base
		sprite.position = Vector2.ZERO
		if sprite.sprite_frames and sprite.sprite_frames.has_animation("idle"):
			sprite.play("idle")
