extends Node2D
## 적 캐릭터 (main.tscn Enemy/AnimatedSprite2D — IDLE work_images/output/burger_idle_*.png)
## 피격 시: CPUParticles2D 스파크(골드) + 스플랫(레드), 스프라이트 살짝 커졌다 복귀, 기존 플래시·SFX.
## 히트박스 없음: 피격은 "플레이어 공격 임팩트 시점에 적이 회피 중인가"로만 판정.
## 회피 중이면 빗나감, 아니면 무조건 히트.

signal hit_received(damage: float)
signal attack_missed  # 플레이어 공격이 회피로 빗나갔을 때 (연출/사운드용)
signal enemy_attack(damage: float)  # 적이 플레이어를 공격할 때 (Main에서 가드/HP 처리)
signal died

@export var max_hp := 100.0
var current_hp: float

# 회피 패턴: 이 시간만큼 회피 상태 유지 후, IDLE로 돌아갔다가 다시 회피
@export var evade_duration := 0.5
@export var idle_before_evade := 2.0

# 공격 패턴: 이 간격(초)마다 플레이어에게 공격 시도
@export var attack_interval := 3.0
@export var attack_telegraph := 0.6  # 공격 전 예비 동작 시간
@export var attack_damage := 15.0
## 타격 파티클·스파크가 터지는 위치 (적 로컬 좌표, 스프라이트 중심 기준)
@export var hit_effect_offset: Vector2 = Vector2(0, -48)

var _is_evading := false
var _pattern_timer: float = 0.0
var _attack_timer: float = 0.0
var _is_attacking := false

const IDLE_TEXTURE_BASE := "res://work_images/output/burger_idle_"
## 프레임당 재생 시간(초). (0.3초/프레임에서 한 번 더 2배 느리게)
const IDLE_FRAME_DURATION_SEC := 0.6
const IDLE_FRAME_PATH_MAX := 32

@onready var hitbox: Area2D = $Hitbox
@onready var sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var hit_sound: AudioStreamPlayer = $HitSound

var _hit_particles: CPUParticles2D
var _hit_particles_splat: CPUParticles2D


func _ready() -> void:
	current_hp = max_hp
	_setup_idle_sprite_frames()
	# 히트박스는 사용하지 않음. 피격은 main에서 punch_impact + is_evading()으로 처리
	if hitbox:
		hitbox.set_collision_layer_value(1, false)
		hitbox.set_collision_mask_value(2, false)
	_setup_hit_particles()


func _setup_idle_sprite_frames() -> void:
	if sprite == null:
		return
	var sf := SpriteFrames.new()
	sf.add_animation("idle")
	sf.set_animation_loop("idle", true)
	var idx := 1
	while idx <= IDLE_FRAME_PATH_MAX:
		var p: String = "%s%02d.png" % [IDLE_TEXTURE_BASE, idx]
		if not ResourceLoader.exists(p):
			break
		var tex: Texture2D = load(p) as Texture2D
		if tex == null:
			push_warning("Enemy: IDLE 텍스처 로드 실패: %s" % p)
			break
		sf.add_frame("idle", tex, IDLE_FRAME_DURATION_SEC)
		idx += 1
	if sf.get_frame_count("idle") < 1:
		push_error("Enemy: IDLE 프레임이 없습니다. work_images/output/burger_idle_*.png 를 확인하세요.")
		return
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
	_hit_particles.amount = 36
	_hit_particles.lifetime = 0.26
	_hit_particles.lifetime_randomness = 0.4
	_hit_particles.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	_hit_particles.emission_sphere_radius = 14.0
	_hit_particles.direction = Vector2(0, -1)
	_hit_particles.spread = 180.0
	_hit_particles.gravity = Vector2(0, 320)
	_hit_particles.initial_velocity_min = 80.0
	_hit_particles.initial_velocity_max = 240.0
	_hit_particles.angular_velocity_min = -8.0
	_hit_particles.angular_velocity_max = 8.0
	_hit_particles.scale_amount_min = 2.0
	_hit_particles.scale_amount_max = 5.0
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
	_hit_particles_splat.amount = 14
	_hit_particles_splat.lifetime = 0.2
	_hit_particles_splat.lifetime_randomness = 0.25
	_hit_particles_splat.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	_hit_particles_splat.emission_sphere_radius = 8.0
	_hit_particles_splat.direction = Vector2(0, -1)
	_hit_particles_splat.spread = 180.0
	_hit_particles_splat.gravity = Vector2(0, 420)
	_hit_particles_splat.initial_velocity_min = 40.0
	_hit_particles_splat.initial_velocity_max = 120.0
	_hit_particles_splat.scale_amount_min = 3.0
	_hit_particles_splat.scale_amount_max = 7.0
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
	_update_evade_pattern(delta)
	_update_attack_pattern(delta)


func _update_evade_pattern(delta: float) -> void:
	_pattern_timer += delta
	if _is_evading:
		if _pattern_timer >= evade_duration:
			_pattern_timer = 0.0
			_set_evading(false)
	else:
		if _pattern_timer >= idle_before_evade:
			_pattern_timer = 0.0
			_set_evading(true)


func _set_evading(evading: bool) -> void:
	_is_evading = evading
	# 회피 연출: 살짝 기울어지거나 움직임 (선택)
	if sprite:
		var tween := create_tween()
		if evading:
			tween.tween_property(sprite, "position", Vector2(8, -4), 0.08).set_trans(Tween.TRANS_QUAD)
		else:
			tween.tween_property(sprite, "position", Vector2.ZERO, 0.1).set_trans(Tween.TRANS_QUAD)


## Main에서 호출: 플레이어 펀치 임팩트 시점에 이 값으로 hit/miss 판정
func is_evading() -> bool:
	return _is_evading


func _update_attack_pattern(delta: float) -> void:
	if current_hp <= 0:
		return
	if _is_attacking:
		return
	_attack_timer += delta
	if _attack_timer >= attack_interval:
		_attack_timer = 0.0
		_start_attack()


func _start_attack() -> void:
	_is_attacking = true
	# 예비 동작 연출 후 공격 착탄
	if sprite:
		var orig: Vector2 = sprite.position
		var tween := create_tween()
		tween.tween_property(sprite, "position", orig + Vector2(0, 12), attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)
		tween.tween_property(sprite, "position", orig, attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)
		tween.tween_callback(_land_attack)
	else:
		var tween := create_tween()
		tween.tween_interval(attack_telegraph)
		tween.tween_callback(_land_attack)


func _land_attack() -> void:
	_is_attacking = false
	enemy_attack.emit(attack_damage)


func _flash_hit() -> void:
	if hit_sound:
		hit_sound.play()
	_burst_hit_particles()
	if not sprite:
		return
	var spr := sprite as Node2D
	if spr:
		var orig_scale: Vector2 = spr.scale
		var tween := create_tween()
		tween.tween_property(sprite, "modulate", Color(1.2, 0.35, 0.35), 0.05)
		tween.parallel().tween_property(spr, "scale", orig_scale * 1.07, 0.06).set_trans(Tween.TRANS_BACK)
		tween.chain()
		tween.tween_property(sprite, "modulate", Color.WHITE, 0.11)
		tween.parallel().tween_property(spr, "scale", orig_scale, 0.14).set_trans(Tween.TRANS_QUAD)
	else:
		var tween_flat := create_tween()
		tween_flat.tween_property(sprite, "modulate", Color.RED, 0.05)
		tween_flat.tween_property(sprite, "modulate", Color.WHITE, 0.1)


func take_damage(amount: float) -> void:
	current_hp -= amount
	hit_received.emit(amount)
	_flash_hit()
	if current_hp <= 0:
		current_hp = 0
		died.emit()
