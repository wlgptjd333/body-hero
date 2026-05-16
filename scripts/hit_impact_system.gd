extends Node
## Hit Impact System — 화면 흔들림, 히트스탑, 화면 플래시, 데미지 숫자
## stage.gd에서 HitImpactSystem.set_camera(camera_2d) 호출 필요

var _camera: Camera2D
var _shake_tween: Tween
var _flash_layer: CanvasLayer
var _flash_rect: ColorRect
var _hitstop_start_ms: int = 0
var _hitstop_duration_ms: int = 0


func _ready() -> void:
	_setup_flash_layer()


func _process(_delta: float) -> void:
	if _hitstop_duration_ms > 0:
		var elapsed: int = Time.get_ticks_msec() - _hitstop_start_ms
		if elapsed >= _hitstop_duration_ms:
			Engine.time_scale = 1.0
			_hitstop_duration_ms = 0


func set_camera(cam: Camera2D) -> void:
	_camera = cam


## 화면 흔들림
func trigger_shake(intensity: float, duration: float, horizontal: bool = true, vertical: bool = true) -> void:
	if _shake_tween and _shake_tween.is_valid():
		_shake_tween.kill()
	if _camera == null:
		return
	_shake_tween = create_tween()
	var steps: int = maxi(4, int(duration * 30.0))
	var step_dur: float = duration / float(steps)
	for i: int in range(steps):
		var progress: float = float(i) / float(steps)
		var current_intensity: float = intensity * (1.0 - progress)
		var shake_x: float = (randf() - 0.5) * 2.0 * current_intensity if horizontal else 0.0
		var shake_y: float = (randf() - 0.5) * 2.0 * current_intensity if vertical else 0.0
		_shake_tween.tween_property(_camera, "offset", Vector2(shake_x, shake_y), step_dur)
	_shake_tween.tween_property(_camera, "offset", Vector2.ZERO, 0.05)


## 히트스탑 (임팩트 순간 멈춤)
func trigger_hitstop(duration_ms: int, slow_scale: float = 0.05) -> void:
	_hitstop_start_ms = Time.get_ticks_msec()
	_hitstop_duration_ms = duration_ms
	Engine.time_scale = slow_scale


## 화면 플래시
func trigger_flash(color: Color, duration: float, max_alpha: float = 0.35) -> void:
	if _flash_rect == null:
		return
	_flash_rect.color = Color(color.r, color.g, color.b, max_alpha)
	_flash_rect.visible = true
	var tween := create_tween()
	tween.tween_property(_flash_rect, "color:a", 0.0, duration)
	tween.tween_callback(func() -> void: _flash_rect.visible = false)


## 데미지 숫자 팝업
func _setup_flash_layer() -> void:
	_flash_layer = CanvasLayer.new()
	_flash_layer.layer = 100
	_flash_layer.process_mode = Node.PROCESS_MODE_ALWAYS
	_flash_rect = ColorRect.new()
	_flash_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flash_rect.visible = false
	_flash_layer.add_child(_flash_rect)
	add_child(_flash_layer)
