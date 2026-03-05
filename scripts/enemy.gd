extends Node2D
## 햄버거 몬스터: 히트박스 + HP + 맞을 때 반응 (케첩 이펙트는 나중에 스프라이트로)

signal hit_received(damage: float)
signal died

@export var max_hp := 100.0
var current_hp: float

@onready var hitbox: Area2D = $Hitbox
@onready var sprite: CanvasItem = $Sprite2D
@onready var hit_sound: AudioStreamPlayer = $HitSound


func _ready() -> void:
	current_hp = max_hp
	if hitbox:
		hitbox.area_entered.connect(_on_hitbox_area_entered)
		hitbox.body_entered.connect(_on_hitbox_body_entered)


func _on_hitbox_area_entered(area: Area2D) -> void:
	_take_damage_from(area, 15.0)


func _on_hitbox_body_entered(_body: Node2D) -> void:
	# 필요 시 Body로 들어온 것도 처리
	pass


func _take_damage_from(area: Node2D, damage: float) -> void:
	# "Glove" 그룹이거나 이름에 Glove 포함된 Area만 데미지 인정 (중복 방지)
	if not area.is_in_group("glove"):
		return
	current_hp -= damage
	hit_received.emit(damage)
	_flash_hit()
	if current_hp <= 0:
		current_hp = 0
		died.emit()
		# TODO: KO 연출, 케첩 이펙트 등


func _flash_hit() -> void:
	if hit_sound:
		hit_sound.play()
	if not sprite:
		return
	var tween := create_tween()
	tween.tween_property(sprite, "modulate", Color.RED, 0.05)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.1)


func take_damage(amount: float) -> void:
	current_hp -= amount
	hit_received.emit(amount)
	_flash_hit()
	if current_hp <= 0:
		current_hp = 0
		died.emit()
