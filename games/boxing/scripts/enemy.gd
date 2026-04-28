extends Node2D
## 적 캐릭터 (main.tscn Enemy/AnimatedSprite2D — IDLE burger_idle_*, ATTACK burger_punch_l_01~04, KO burger_ko_*)
## 피격 시: CPUParticles2D 스파크(골드) + 스플랫(레드), 모듈레이트 플래시·SFX (스케일은 건드리지 않음).
## 히트박스 없음: 피격은 "플레이어 공격 임팩트 시점에 적이 회피 중인가"로만 판정.
## 회피 중이면 빗나감, 아니면 무조건 히트.

signal hit_received(damage: float)
signal attack_missed  # 플레이어 공격이 회피로 빗나갔을 때 (연출/사운드용)
signal enemy_attack(damage: float)  # 적이 플레이어를 공격할 때 (Main에서 가드/HP 처리)
signal died

@export var max_hp := 100.0
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
## 타격 파티클·스파크가 터지는 위치 (적 로컬 좌표, 스프라이트 중심 기준)
@export var hit_effect_offset: Vector2 = Vector2(0, -48)
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

## HP 0 이후 KO 연출 중이면 true. Main에서 UDP 차단·펀치 무시용
var _is_dead := false
## 씬(AnimatedSprite2D scale) 기준 — KO 시 이 값에 KO_DISPLAY_SCALE 곱함
var _sprite_scale_base: Vector2 = Vector2.ONE


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
	add_child(_hit_particles_splat)


func _burst_hit_particles() -> void:
	if _hit_particles:
		_hit_particles.restart()
		_hit_particles.emitting = true
	if _hit_particles_splat:
		_hit_particles_splat.restart()
		_hit_particles_splat.emitting = true


func _process(delta: float) -> void:
	if _is_dead:
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


func _flash_hit() -> void:
	if hit_sound:
		hit_sound.play()
	_burst_hit_particles()
	if not sprite:
		return
	# 스케일 트윈은 제거: 연타·트윈 겹침 시 스케일이 누적되어 커지는 현상 방지. 색 플래시만 사용.
	var tween := create_tween()
	tween.tween_property(sprite, "modulate", Color(1.2, 0.35, 0.35), 0.05)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.11)


func take_damage(amount: float) -> void:
	if _is_dead:
		return
	current_hp -= amount
	hit_received.emit(amount)
	_flash_hit()
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
