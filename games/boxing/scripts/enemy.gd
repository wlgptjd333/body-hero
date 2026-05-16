extends Node2D
## 적 캐릭터 (main.tscn Enemy/AnimatedSprite2D — IDLE burger_idle_*, ATTACK burger_punch_l_01~04, KO burger_ko_*)

enum EnemyState { IDLE, ATTACK, EVADE, HIT, DEAD }
enum AttackPhase { STARTUP, ACTIVE, RECOVERY }

const DEBUG_FSM := true

## 피격 시: 펀치 종류별 위치·규모 다른 CPUParticles2D 다층 연출 + 모듈레이트 플래시·SFX.
## 히트박스 없음: 피격은 "플레이어 공격 임팩트 시점에 적이 회피 중인가"로만 판정.
## 회피 중이면 빗나감, 아니면 무조건 히트.

signal hit_received(damage: float)
signal enemy_attack(damage: float)  # 적이 플레이어를 공격할 때 (Main에서 가드/HP 처리)
signal died
signal phase_changed(new_phase: int)

@export var max_hp := 100.0
@export var ai_enabled: bool = true
var current_hp: float

## 보스 모드 설정
@export var is_boss: bool = false
@export var boss_phases: int = 1
var _current_phase: int = 1
var _phase_hp_thresholds: Array[float] = []

## 회피: 대기(랜덤) 후 evade_duration 동안 회피.
@export var evade_duration := 0.38
@export var evade_idle_min := 1.0
@export var evade_idle_max := 2.5
## 공격: 랜덤 간격.
@export var attack_delay_min := 0.5
@export var attack_delay_max := 1.2
@export var attack_telegraph := 0.7  # 공격 PNG 없을 때 위치 트윈 전체 길이(초). 임팩트 타이밍 비율에도 사용
## 공격 모션 각 프레임 실제 시간(초). 4프레면 합계 4×이 값(기본 1초).
@export var attack_frame_duration_sec := 0.25
## 플레이어 피격 판정: 몇 번째 프레임 **시점**(0부터). 2 = 세 번째(03 임팩트)
@export var enemy_attack_impact_frame_index := 2
@export var attack_damage := 30.0
## 타격 파티클 기본 위치 (미분류 시)
@export var hit_effect_offset: Vector2 = Vector2(0, -48)
## 어퍼컷: 상단(머리/번) 쪽 — 왼손은 좌상단, 오른손은 우상단
@export var hit_upper_l_offset: Vector2 = Vector2(-56, -96)
@export var hit_upper_r_offset: Vector2 = Vector2(56, -96)
## 펀치: 몸통 중앙 높이 — 왼쪽/오른쪽
@export var hit_punch_l_offset: Vector2 = Vector2(-44, -10)
@export var hit_punch_r_offset: Vector2 = Vector2(44, -10)
## 회피 시 스프라이트를 좌/우로 이동하는 픽셀 거리(랜덤 방향)
@export var evade_dodge_offset_pixels: float = 72.0

var _current_state: int = EnemyState.IDLE
var _state_enter_time: int = 0

var _is_evading := false
var _evade_side_sign: float = 1.0
var _is_attacking := false


@export var idle_texture_base := "res://assets/textures/characters/enemies/burger/burger_idle_"
## 프레임당 재생 시간(초). (0.3초/프레임에서 한 번 더 2배 느리게)
const IDLE_FRAME_DURATION_SEC := 0.6
const IDLE_FRAME_PATH_MAX := 32
const FALLBACK_ENEMY_TEXTURE := "res://assets/textures/characters/placeholder_enemy.svg"

## 플레이어 펀치 몸통과 동일: burger_punch_l_01.png … _04.png (assets)
@export var attack_texture_base := "res://assets/textures/characters/enemies/burger/burger_punch_l_"
const ATTACK_FRAME_PATH_MAX := 4

@export var hit_texture_base := "res://assets/textures/characters/enemies/burger/burger_hit_"
const HIT_FRAME_PATH_MAX := 4
const HIT_FRAME_DURATION_SEC := 0.2

@export var ko_texture_base := "res://assets/textures/characters/enemies/burger/burger_ko_"
## KO만 idle보다 크게(캔버스·누끼 후 실제 그림 크기 차이 보정)
const KO_DISPLAY_SCALE := 1.0
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
var _hit_spark_line: Line2D
var _particle_texture: Texture2D
var _particle_texture_soft: Texture2D
var _last_hit_damage: float = 0.0
var _last_hit_punch_type: String = "punch_l"

## HP 0 이후 KO 연출 중이면 true. Main에서 UDP 차단·펀치 무시용
var _is_dead := false

var _attack_idle_timer: float = 0.0
var _evade_idle_timer: float = 0.0
var _attack_phase_timer: float = 0.0
var _attack_phase: int = AttackPhase.STARTUP
var _evade_timer: float = 0.0
var _evade_tween: Tween = null
var _impact_emitted: bool = false
var _hit_timer: float = 0.0
var hit_stagger_duration: float = 0.2
## 씬(AnimatedSprite2D scale) 기준 — KO 시 이 값에 KO_DISPLAY_SCALE 곱함
var _sprite_scale_base: Vector2 = Vector2.ONE


func _ready() -> void:
	_apply_difficulty_stats()
	current_hp = max_hp
	_setup_idle_sprite_frames()
	if sprite:
		_sprite_scale_base = sprite.scale
	# 히트박스는 사용하지 않음. 피격은 main에서 punch_impact + is_evading()으로 처리
	if hitbox:
		hitbox.set_collision_layer_value(1, false)
		hitbox.set_collision_mask_value(2, false)
	_setup_hit_particles()
	_setup_particle_textures()
	_attack_idle_timer = randf_range(minf(attack_delay_min, attack_delay_max), maxf(attack_delay_min, attack_delay_max))
	_evade_idle_timer = randf_range(minf(evade_idle_min, evade_idle_max), maxf(evade_idle_min, evade_idle_max))
	_enter_state(_current_state)

func _apply_difficulty_stats() -> void:
	match GameState.get_difficulty():
		GameState.DIFFICULTY_EASY:
			max_hp = maxf(50.0, max_hp * 0.75)
			attack_damage = maxf(5.0, attack_damage * 0.75 * 0.85)
			attack_delay_min = attack_delay_min * 1.25
			attack_delay_max = attack_delay_max * 1.25
		GameState.DIFFICULTY_HARD:
			max_hp = maxf(50.0, max_hp * 1.6)
			attack_damage = maxf(5.0, attack_damage * 1.8)
			attack_delay_min = attack_delay_min * 0.95
			attack_delay_max = attack_delay_max * 0.95
		_:
			pass


## stage.gd의 _apply_stage_config() 이후 호출: stage_config 기본값을 덮어쓴 뒤
## 난이도 배율을 다시 적용하고 current_hp를 max_hp에 맞게 초기화.
## 이렇게 하지 않으면 enemy._ready()에서 난이도 배율이 적용된 current_hp와
## stage_config 원본 max_hp가 어긋나 HP 바가 난이도마다 다르게 보이는 버그가 발생함.
func reapply_difficulty_and_reset_hp() -> void:
	_apply_difficulty_stats()
	current_hp = max_hp


func _setup_idle_sprite_frames() -> void:
	if sprite == null:
		return
	var sf := SpriteFrames.new()
	sf.add_animation("idle")
	sf.set_animation_loop("idle", true)
	# 로컬 작업/에셋 정리 중에 프레임 번호가 중간에 비거나 01이 빠져도 동작하도록:
	# "없으면 종료"가 아니라 "없으면 건너뛰기"로 로드한다.
	for idx: int in range(1, IDLE_FRAME_PATH_MAX + 1):
		var p: String = "%s%02d.png" % [idle_texture_base, idx]
		if not ResourceLoader.exists(p):
			continue
		var tex: Texture2D = ResourceLoader.load(
			p, "", ResourceLoader.CACHE_MODE_REPLACE as ResourceLoader.CacheMode
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
		var kp: String = "%s%02d.png" % [ko_texture_base, kidx]
		if not ResourceLoader.exists(kp):
			continue
		var ktex: Texture2D = ResourceLoader.load(
			kp, "", ResourceLoader.CACHE_MODE_REPLACE as ResourceLoader.CacheMode
		) as Texture2D
		if ktex == null:
			push_warning("Enemy: KO 텍스처 로드 실패: %s" % kp)
			continue
		sf.add_frame("ko", ktex, KO_FRAME_DURATION_SEC)
	# 공격: burger_punch_l_01 … _04 (없으면 기존 위치 트윈만 사용)
	var attack_textures: Array[Texture2D] = []
	for aidx: int in range(1, ATTACK_FRAME_PATH_MAX + 1):
		var ap: String = "%s%02d.png" % [attack_texture_base, aidx]
		if not ResourceLoader.exists(ap):
			continue
		var atex: Texture2D = ResourceLoader.load(
			ap, "", ResourceLoader.CACHE_MODE_REPLACE as ResourceLoader.CacheMode
		) as Texture2D
		if atex == null:
			push_warning("Enemy: ATTACK 텍스처 로드 실패: %s" % ap)
			continue
		attack_textures.append(atex)
	if attack_textures.size() >= 1:
		sf.add_animation("attack")
		sf.set_animation_loop("attack", false)
		for atex: Texture2D in attack_textures:
			# 상대 duration 1.0 = 동일 길이 프레임. 실제 초는 set_animation_speed로 맞춤.
			sf.add_frame("attack", atex, 1.0)
		var sec_per_frame: float = maxf(attack_frame_duration_sec, 0.001)
		sf.set_animation_speed("attack", 1.0 / sec_per_frame)
	# 피격(단일/다중 프레임 지원): burger_hit_01 ... _NN
	var hit_textures: Array[Texture2D] = []
	for hidx: int in range(1, HIT_FRAME_PATH_MAX + 1):
		var hp: String = "%s%02d.png" % [hit_texture_base, hidx]
		if not ResourceLoader.exists(hp):
			continue
		var htex: Texture2D = ResourceLoader.load(
			hp, "", ResourceLoader.CACHE_MODE_REPLACE as ResourceLoader.CacheMode
		) as Texture2D
		if htex == null:
			push_warning("Enemy: HIT 텍스처 로드 실패: %s" % hp)
			continue
		hit_textures.append(htex)
	if hit_textures.size() >= 1:
		sf.add_animation("hit")
		sf.set_animation_loop("hit", false)
		for htex: Texture2D in hit_textures:
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
	_hit_particles.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE as CPUParticles2D.EmissionShape
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
	_hit_particles.texture = _particle_texture
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
	_hit_particles_splat.emission_shape = (
		CPUParticles2D.EMISSION_SHAPE_SPHERE as CPUParticles2D.EmissionShape
	)
	_hit_particles_splat.emission_sphere_radius = 15.0
	_hit_particles_splat.direction = Vector2(0, -1)
	_hit_particles_splat.spread = 180.0
	_hit_particles_splat.gravity = Vector2(0, 400)
	_hit_particles_splat.initial_velocity_min = 55.0
	_hit_particles_splat.initial_velocity_max = 175.0
	_hit_particles_splat.scale_amount_min = 5.0
	_hit_particles_splat.scale_amount_max = 11.0
	_hit_particles_splat.color = Color(0.95, 0.25, 0.2)
	_hit_particles_splat.texture = _particle_texture_soft
	if sprite is Node2D:
		(sprite as Node2D).add_child(_hit_particles_splat)
	else:
		add_child(_hit_particles_splat)

	_hit_star_pop = _make_hit_star_pop()
	_hit_star_pop.texture = _particle_texture
	_hit_accent_burst = _make_hit_accent_burst()
	_hit_accent_burst.texture = _particle_texture_soft
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
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE as CPUParticles2D.EmissionShape
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
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE as CPUParticles2D.EmissionShape
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


func _setup_particle_textures() -> void:
	var img := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	var center: float = 16.0
	for x: int in range(32):
		for y: int in range(32):
			var dist: float = Vector2(float(x) - center, float(y) - center).length() / center
			var alpha: float = clampf(1.0 - dist * dist, 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, alpha))
	_particle_texture = ImageTexture.create_from_image(img)

	var img2 := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for x: int in range(32):
		for y: int in range(32):
			var dist: float = Vector2(float(x) - center, float(y) - center).length() / center
			var alpha: float = clampf(1.0 - dist, 0.0, 1.0)
			alpha = alpha * alpha
			img2.set_pixel(x, y, Color(1, 1, 1, alpha))
	_particle_texture_soft = ImageTexture.create_from_image(img2)


func _spawn_hit_spark_line(impact_pos: Vector2, punch_type: String) -> void:
	var is_upper: bool = punch_type.begins_with("upper")
	var is_left: bool = punch_type.ends_with("_l")
	var theme: Dictionary = _get_current_effect_theme()
	var line_color: Color = theme.get("spark_color", Color(1, 0.95, 0.4))

	if _hit_spark_line == null:
		_hit_spark_line = Line2D.new()
		_hit_spark_line.name = "HitSparkLine"
		_hit_spark_line.z_index = 10
		_hit_spark_line.z_as_relative = false
		_hit_spark_line.width = 4.0
		_hit_spark_line.joint_mode = Line2D.LINE_JOINT_ROUND
		_hit_spark_line.end_cap_mode = Line2D.LINE_CAP_ROUND
		add_child(_hit_spark_line)

	var dir_x: float = -1.0 if is_left else 1.0
	var length: float = 120.0 if is_upper else 80.0
	var segments: int = 5
	var points: PackedVector2Array = PackedVector2Array()
	points.resize(segments + 1)
	points[0] = impact_pos + Vector2(dir_x * 20.0, -10.0)
	for i: int in range(1, segments + 1):
		var t: float = float(i) / float(segments)
		var px: float = points[0].x + dir_x * length * t
		var py: float = points[0].y + (randf() - 0.5) * 30.0 * (1.0 - t)
		if is_upper:
			py -= t * 40.0
		points[i] = Vector2(px, py)

	_hit_spark_line.points = points
	_hit_spark_line.default_color = line_color
	_hit_spark_line.width = 6.0 if is_upper else 4.0
	_hit_spark_line.visible = true

	var tween := create_tween()
	tween.tween_property(_hit_spark_line, "modulate:a", 0.0, 0.12)
	tween.tween_callback(func() -> void: _hit_spark_line.visible = false)


func _get_current_effect_theme() -> Dictionary:
	var theme_id: String = GameState.get_equipped_hit_effect()
	var colors: Dictionary = GameState.get_hit_effect_theme_colors(theme_id)
	return colors


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
			"offset": (hit_punch_l_offset if is_left else hit_punch_r_offset),
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
	var theme: Dictionary = _get_current_effect_theme()

	if _hit_particles:
		_hit_particles.position = off
		_hit_particles.emission_sphere_radius = 22.0 * sm
		_hit_particles.amount = mini(140, int(52 * sm))
		_hit_particles.initial_velocity_max = 260.0 + 120.0 * sm
		_hit_particles.scale_amount_min = 3.2 + 2.0 * sm
		_hit_particles.scale_amount_max = 8.0 + 5.0 * sm
		_hit_particles.color = theme.get("particle_color", Color(1.0, 0.95, 0.42) if up else Color(1.0, 0.88, 0.35))
		_hit_particles.restart()
		_hit_particles.emitting = true

	if _hit_particles_splat:
		var splat_off := off + Vector2(-12.0 if left_side else 12.0, 22.0)
		_hit_particles_splat.position = splat_off
		_hit_particles_splat.emission_sphere_radius = (13.0 + 10.0 * sm)
		_hit_particles_splat.amount = mini(110, int(28 * sm))
		_hit_particles_splat.initial_velocity_max = 140.0 + 90.0 * sm
		_hit_particles_splat.color = theme.get("splat_color", Color(0.98, 0.22, 0.18) if up else Color(0.92, 0.28, 0.45))
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
		_hit_accent_burst.color = theme.get("spark_color", Color(1.0, 0.42, 0.08) if up else Color(1.0, 0.72, 0.2))
		var dir_x := -0.92 if left_side else 0.92
		_hit_accent_burst.direction = Vector2(dir_x, -0.35).normalized()
		_hit_accent_burst.spread = 95.0 if up else 140.0
		_hit_accent_burst.restart()
		_hit_accent_burst.emitting = true

	var impact_pos_global: Vector2 = (sprite as Node2D).to_global(off) if sprite else Vector2.ZERO
	_spawn_hit_spark_line(impact_pos_global, punch_type)

	var shake_intensity: float = 30.0 if up else 10.0
	var hitstop_dur_ms: int = 12 if up else 6
	var flash_color: Color = theme.get("flash_color", Color(1, 1, 1))
	var flash_alpha: float = 0.3 if up else 0.15

	HitImpactSystem.trigger_shake(shake_intensity, 0.15)
	HitImpactSystem.trigger_hitstop(hitstop_dur_ms)


func _process(delta: float) -> void:
	if _current_state == EnemyState.DEAD:
		return
	_update_fsm(delta)


func transition_to(next: int, reason := "") -> void:
	if next == _current_state:
		if DEBUG_FSM:
			push_warning("transition_to(%s) but already in %s" % [EnemyState.keys()[next], EnemyState.keys()[_current_state]])
		return
	if DEBUG_FSM and _state_enter_time > 0:
		var duration := Time.get_ticks_msec() - _state_enter_time
		print("[FSM] %s lasted %dms" % [EnemyState.keys()[_current_state], duration])
	if DEBUG_FSM:
		print("[FSM] %s -> %s (%s)" % [EnemyState.keys()[_current_state], EnemyState.keys()[next], reason])
	_exit_state(_current_state)
	_current_state = next
	_state_enter_time = Time.get_ticks_msec()
	_enter_state(_current_state)


func _enter_state(state: int) -> void:
	match state:
		EnemyState.IDLE:
			pass
		EnemyState.ATTACK:
			_impact_emitted = false
			_start_attack_visual()
			if sprite and sprite.sprite_frames and sprite.sprite_frames.has_animation("attack") and sprite.sprite_frames.get_frame_count("attack") >= 1:
				if not sprite.frame_changed.is_connected(_on_attack_frame_changed):
					sprite.frame_changed.connect(_on_attack_frame_changed)
				if not sprite.animation_finished.is_connected(_on_attack_anim_finished):
					sprite.animation_finished.connect(_on_attack_anim_finished)
			else:
				_attack_phase = AttackPhase.STARTUP
				_attack_phase_timer = attack_telegraph
		EnemyState.EVADE:
			_evade_timer = evade_duration
			_start_evade_tween()
		EnemyState.HIT:
			_hit_timer = hit_stagger_duration
			_play_hit_anim()
			_hit_vfx(_last_hit_punch_type)
			emit_signal("hit_received", _last_hit_damage)
		EnemyState.DEAD:
			_is_dead = true
			_start_ko()


func _exit_state(state: int) -> void:
	match state:
		EnemyState.IDLE:
			pass
		EnemyState.ATTACK:
			_stop_attack_visual()
			if sprite:
				if sprite.frame_changed.is_connected(_on_attack_frame_changed):
					sprite.frame_changed.disconnect(_on_attack_frame_changed)
				if sprite.animation_finished.is_connected(_on_attack_anim_finished):
					sprite.animation_finished.disconnect(_on_attack_anim_finished)
		EnemyState.EVADE:
			if _evade_tween and _evade_tween.is_valid():
				_evade_tween.kill()
				_evade_tween = null
			if sprite:
				sprite.position = Vector2.ZERO
		EnemyState.HIT:
			if sprite:
				sprite.modulate = Color.WHITE
				if sprite.sprite_frames and sprite.sprite_frames.has_animation("idle"):
					sprite.play("idle")
		EnemyState.DEAD:
			pass


func _update_fsm(delta: float) -> void:
	match _current_state:
		EnemyState.IDLE:
			_update_idle(delta)
		EnemyState.ATTACK:
			_update_attack(delta)
		EnemyState.EVADE:
			_update_evade(delta)
		EnemyState.HIT:
			_update_hit(delta)
		EnemyState.DEAD:
			pass


func _update_idle(delta: float) -> void:
	if not ai_enabled:
		return

	_attack_idle_timer -= delta
	_evade_idle_timer -= delta

	if _attack_idle_timer <= 0.0:
		_attack_idle_timer = randf_range(minf(attack_delay_min, attack_delay_max), maxf(attack_delay_min, attack_delay_max))
		transition_to(EnemyState.ATTACK, "attack timer expired")
		return
	if _evade_idle_timer <= 0.0:
		_evade_idle_timer = randf_range(minf(evade_idle_min, evade_idle_max), maxf(evade_idle_min, evade_idle_max))
		transition_to(EnemyState.EVADE, "evade timer expired")
		return


func _on_attack_frame_changed() -> void:
	if sprite and sprite.frame == enemy_attack_impact_frame_index:
		_emit_impact()


func _on_attack_anim_finished() -> void:
	transition_to(EnemyState.IDLE, "attack complete")


func _update_attack(delta: float) -> void:
	if sprite and sprite.sprite_frames and sprite.sprite_frames.has_animation("attack") and sprite.sprite_frames.get_frame_count("attack") >= 1:
		return
	_attack_phase_timer -= delta
	match _attack_phase:
		AttackPhase.STARTUP:
			if _attack_phase_timer <= 0.0:
				_attack_phase = AttackPhase.ACTIVE
				_attack_phase_timer = 0.08
				_emit_impact()
		AttackPhase.ACTIVE:
			if _attack_phase_timer <= 0.0:
				_attack_phase = AttackPhase.RECOVERY
				_attack_phase_timer = 0.25
		AttackPhase.RECOVERY:
			if _attack_phase_timer <= 0.0:
				transition_to(EnemyState.IDLE, "attack complete")


func _update_evade(delta: float) -> void:
	_evade_timer -= delta
	if _evade_timer <= 0.0:
		_return_from_evade()


func _return_from_evade() -> void:
	_evade_timer = 999.0
	if _evade_tween and _evade_tween.is_valid():
		_evade_tween.kill()
		_evade_tween = null
	if not sprite:
		transition_to(EnemyState.IDLE, "evade complete")
		return
	_evade_tween = create_tween()
	_evade_tween.tween_property(sprite, "position", Vector2.ZERO, 0.12).set_trans(Tween.TRANS_QUAD)
	_evade_tween.finished.connect(_on_evade_return_finished.bind(), CONNECT_ONE_SHOT)


func _on_evade_return_finished() -> void:
	if _current_state == EnemyState.EVADE:
		transition_to(EnemyState.IDLE, "evade complete")


func _update_hit(delta: float) -> void:
	_hit_timer -= delta
	if _hit_timer <= 0.0:
		transition_to(EnemyState.IDLE, "stagger end")



## Main에서 호출: 플레이어 펀치 임팩트 시점에 이 값으로 hit/miss 판정
func is_evading() -> bool:
	return _current_state == EnemyState.EVADE


func is_dead() -> bool:
	return _current_state == EnemyState.DEAD


func _start_attack_visual() -> void:
	if sprite == null:
		return
	var sf: SpriteFrames = sprite.sprite_frames
	if sf != null and sf.has_animation("attack") and sf.get_frame_count("attack") >= 1:
		sprite.play("attack")
	else:
		var orig := sprite.position
		var tw := create_tween()
		tw.tween_property(sprite, "position", orig + Vector2(0, 12), attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)
		tw.tween_property(sprite, "position", orig, attack_telegraph * 0.5).set_trans(Tween.TRANS_QUAD)


func _stop_attack_visual() -> void:
	if sprite and sprite.sprite_frames:
		(sprite as AnimatedSprite2D).stop()
		if sprite.sprite_frames.has_animation("idle"):
			sprite.play("idle")


func _emit_impact() -> void:
	if _impact_emitted:
		return
	_impact_emitted = true
	enemy_attack.emit(attack_damage)


func _start_evade_tween() -> void:
	if not sprite:
		return
	_evade_side_sign = -1.0 if randf() < 0.5 else 1.0
	var dodge_pos := Vector2(evade_dodge_offset_pixels * _evade_side_sign, -4.0)
	_evade_tween = create_tween()
	_evade_tween.tween_property(sprite, "position", dodge_pos, 0.1).set_trans(Tween.TRANS_QUAD)


func _play_hit_anim() -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	if not sprite.sprite_frames.has_animation("hit"):
		return
	sprite.play("hit")


func _hit_vfx(punch_type: String) -> void:
	if hit_sound:
		hit_sound.play()
	_burst_hit_particles(punch_type)
	if not sprite:
		return
	var tween := create_tween()
	tween.tween_property(sprite, "modulate", Color(1.2, 0.35, 0.35), 0.05)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.11)


func take_damage(amount: float, punch_type: String = "punch_l") -> void:
	if _current_state == EnemyState.DEAD:
		return
	current_hp -= amount
	_last_hit_damage = amount
	_last_hit_punch_type = punch_type

	if current_hp <= 0:
		current_hp = 0
		if is_boss and _current_phase < boss_phases:
			_current_phase += 1
			phase_changed.emit(_current_phase)
			current_hp = max_hp
			transition_to(EnemyState.IDLE, "boss phase up")
			return
		transition_to(EnemyState.DEAD, "hp <= 0")
		return

	if _current_state == EnemyState.HIT:
		_hit_timer = hit_stagger_duration
		_play_hit_anim()
		_hit_vfx(_last_hit_punch_type)
		emit_signal("hit_received", _last_hit_damage)
		return

	transition_to(EnemyState.HIT, "take_damage")


func _start_ko() -> void:
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
	if sprite:
		if sprite.animation_finished.is_connected(_on_ko_animation_finished):
			sprite.animation_finished.disconnect(_on_ko_animation_finished)
		sprite.modulate = Color.WHITE
		sprite.scale = _sprite_scale_base
		sprite.position = Vector2.ZERO
		if sprite.sprite_frames and sprite.sprite_frames.has_animation("idle"):
			sprite.play("idle")
	_current_state = EnemyState.IDLE
	_state_enter_time = Time.get_ticks_msec()
	_enter_state(_current_state)
