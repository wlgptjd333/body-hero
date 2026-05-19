extends Node
## Stage Manager: 스테이지 설정, 적/배경/BGM 초기화를 담당.

const BULGE_SHADER := preload("res://shaders/perspective_bulge.gdshader")
const BG_EFFECT_LAYER := 10

@onready var _background: Sprite2D = $"../Background"
@onready var _bgm: AudioStreamPlayer = $"../BGM"
@onready var _enemy: Node2D = $"../Enemy"

var _bg_effect_layer: CanvasLayer = null


func setup_stage() -> void:
	_fit_background_to_viewport()
	_apply_bg_effect()
	var vp := get_viewport()
	if vp and not vp.size_changed.is_connected(_fit_background_to_viewport):
		vp.size_changed.connect(_fit_background_to_viewport)


func _apply_bg_effect() -> void:
	if not GameState.get_bg_effect_enabled():
		return
	var root := get_parent()
	if not root:
		return
	_bg_effect_layer = CanvasLayer.new()
	_bg_effect_layer.name = "BgEffectLayer"
	_bg_effect_layer.layer = BG_EFFECT_LAYER
	root.add_child(_bg_effect_layer)
	var rect := ColorRect.new()
	rect.name = "BgEffectRect"
	rect.layout_mode = 1
	rect.anchors_preset = 15
	rect.anchor_right = 1.0
	rect.anchor_bottom = 1.0
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var mat := ShaderMaterial.new()
	mat.shader = BULGE_SHADER
	mat.set_shader_parameter("distortion_strength", GameState.get_bg_effect_strength())
	rect.material = mat
	_bg_effect_layer.add_child(rect)


func setup_training_mode() -> void:
	if _enemy:
		_enemy.ai_enabled = false


func setup_audio(bgm_paths_override: Array[String] = [], hit_sound_paths_override: Array[String] = []) -> void:
	var bgm_paths: Array[String] = bgm_paths_override if bgm_paths_override else [
		"res://assets/audio/bgm/Retro_Ring_Rush.ogg",
		"res://assets/audio/bgm/mainbgm.ogg",
	]
	var hit_sound_paths: Array[String] = hit_sound_paths_override if hit_sound_paths_override else [
		"res://assets/audio/sfx/sfx_punch_hit.wav",
	]
	if _bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			_bgm.bus = "Music"
		if _bgm.stream == null:
			_try_load_stream(_bgm, bgm_paths)
		if _bgm.stream and _bgm.playing == false:
			_bgm.play()
	if _enemy:
		var hit_sound: AudioStreamPlayer = _enemy.get_node_or_null("HitSound")
		if hit_sound and AudioServer.get_bus_index("SFX") >= 0:
			hit_sound.bus = "SFX"
		if hit_sound and hit_sound.stream == null:
			_try_load_stream(hit_sound, hit_sound_paths)


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	AudioHelper.try_load_stream(player, paths)


func _fit_background_to_viewport() -> void:
	if not _background or not _background.texture:
		return
	var view_size := _get_view_size()
	var tex_size := _background.texture.get_size()
	if tex_size.x <= 0 or tex_size.y <= 0:
		return
	var scale_factor := maxf(view_size.x / tex_size.x, view_size.y / tex_size.y)
	_background.scale = Vector2(scale_factor, scale_factor)
	_background.position = view_size / 2


func get_view_size() -> Vector2:
	return _get_view_size()


func _get_view_size() -> Vector2:
	var vp := get_viewport()
	if vp:
		return vp.get_visible_rect().size
	return Vector2(1152, 648)


func cleanup() -> void:
	var vp := get_viewport()
	if vp and vp.size_changed.is_connected(_fit_background_to_viewport):
		vp.size_changed.disconnect(_fit_background_to_viewport)
