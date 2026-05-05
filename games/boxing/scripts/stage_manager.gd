extends Node
## Stage Manager: 스테이지 설정, 적/배경/BGM 초기화를 담당.
## 현재는 1개 스테이지만 관리하며, 향후 StageConfig 기반 다중 스테이지로 확장.

@onready var _background: Sprite2D = $"../Background"
@onready var _bgm: AudioStreamPlayer = $"../BGM"
@onready var _enemy: Node2D = $"../Enemy"

func setup_stage() -> void:
	_fit_background_to_viewport()
	var vp := get_viewport()
	if vp and not vp.size_changed.is_connected(_fit_background_to_viewport):
		vp.size_changed.connect(_fit_background_to_viewport)


func setup_training_mode() -> void:
	if _enemy:
		_enemy.ai_enabled = false


func setup_audio() -> void:
	if _bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			_bgm.bus = "Music"
		if _bgm.stream == null:
			_try_load_stream(_bgm, [
				"res://assets/audio/bgm/Retro_Ring_Rush.ogg",
				"res://assets/audio/bgm/mainbgm.ogg",
			])
		if _bgm.stream and _bgm.playing == false:
			_bgm.play()
	if _enemy:
		var hit_sound: AudioStreamPlayer = _enemy.get_node_or_null("HitSound")
		if hit_sound and AudioServer.get_bus_index("SFX") >= 0:
			hit_sound.bus = "SFX"
		if hit_sound and hit_sound.stream == null:
			_try_load_stream(hit_sound, [
				"res://assets/audio/sfx/sfx_punch_hit.wav",
			])


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p: String in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return


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
