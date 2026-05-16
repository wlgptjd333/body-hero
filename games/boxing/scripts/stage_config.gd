class_name StageConfig extends Resource

@export var stage_id: String = "stage_1"
@export var monster_name: String = "BULGOGI BURGER"
@export var scene_path: String = ""

@export var enemy_max_hp: float = 100.0
@export var enemy_attack_damage: float = 30.0
@export var enemy_attack_delay_min: float = 1.4
@export var enemy_attack_delay_max: float = 2.45
@export var enemy_evade_idle_min: float = 0.35
@export var enemy_evade_idle_max: float = 1.1
@export var enemy_evade_duration: float = 0.38
@export var enemy_recovery_mult: float = 1.0

@export var bgm_paths: Array[String] = [
	"res://assets/audio/bgm/Retro_Ring_Rush.ogg",
	"res://assets/audio/bgm/mainbgm.ogg",
]

@export var hit_sound_paths: Array[String] = [
	"res://assets/audio/sfx/sfx_punch_hit.wav",
]
