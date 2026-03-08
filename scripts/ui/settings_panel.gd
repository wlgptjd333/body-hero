extends Control
## 설정 패널: 해상도 설정, 소리 설정(전체/게임/음악), 적용 버튼, 뒤로가기

signal back_pressed

const RESOLUTIONS := [
	Vector2i(1152, 648),
	Vector2i(1280, 720),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
]

@onready var _resolution_option: OptionButton = $Panel/Scroll/VBox/ResolutionSection/ResolutionRow/OptionButton
@onready var _slider_master: HSlider = $Panel/Scroll/VBox/SoundSection/MasterRow/HSlider
@onready var _label_master: Label = $Panel/Scroll/VBox/SoundSection/MasterRow/ValueLabel
@onready var _slider_sfx: HSlider = $Panel/Scroll/VBox/SoundSection/GameRow/HSlider
@onready var _label_sfx: Label = $Panel/Scroll/VBox/SoundSection/GameRow/ValueLabel
@onready var _slider_music: HSlider = $Panel/Scroll/VBox/SoundSection/MusicRow/HSlider
@onready var _label_music: Label = $Panel/Scroll/VBox/SoundSection/MusicRow/ValueLabel
@onready var _btn_back: Button = $Panel/Scroll/VBox/BackButton
@onready var _btn_apply: Button = $Panel/Scroll/VBox/ApplyButton


func _ready() -> void:
	_setup_resolutions()
	_setup_volumes()
	if _btn_back:
		_btn_back.pressed.connect(_on_back)
	if _btn_apply:
		_btn_apply.pressed.connect(_on_apply)
	if _slider_master:
		_slider_master.value_changed.connect(func(v: float): _update_label(_label_master, v))
	if _slider_sfx:
		_slider_sfx.value_changed.connect(func(v: float): _update_label(_label_sfx, v))
	if _slider_music:
		_slider_music.value_changed.connect(func(v: float): _update_label(_label_music, v))


func _get_window_size() -> Vector2i:
	var w := get_viewport().get_window()
	if w:
		return w.size
	return Vector2i(1152, 648)


func _db_to_linear(db: float) -> float:
	if db <= -80.0:
		return 0.0
	return db_to_linear(db)


func _linear_to_db(linear: float) -> float:
	if linear <= 0.0:
		return -80.0
	return linear_to_db(linear)


func _setup_resolutions() -> void:
	if not _resolution_option:
		return
	_resolution_option.clear()
	var current := _get_window_size()
	var sel := 0
	for i in range(RESOLUTIONS.size()):
		var r: Vector2i = RESOLUTIONS[i]
		_resolution_option.add_item("%d x %d" % [r.x, r.y], i)
		if r.x == current.x and r.y == current.y:
			sel = i
	_resolution_option.selected = sel


func _setup_volumes() -> void:
	var idx_master := AudioServer.get_bus_index("Master")
	if idx_master >= 0 and _slider_master and _label_master:
		var db: float = AudioServer.get_bus_volume_db(idx_master)
		var linear := _db_to_linear(db)
		_slider_master.value = linear * 100.0
		_update_label(_label_master, _slider_master.value)
	var idx_sfx := AudioServer.get_bus_index("SFX")
	if idx_sfx >= 0 and _slider_sfx and _label_sfx:
		var db: float = AudioServer.get_bus_volume_db(idx_sfx)
		var linear := _db_to_linear(db)
		_slider_sfx.value = linear * 100.0
		_update_label(_label_sfx, _slider_sfx.value)
	elif _slider_sfx and _label_sfx:
		_slider_sfx.value = 100.0
		_update_label(_label_sfx, 100.0)
	var idx_music := AudioServer.get_bus_index("Music")
	if idx_music >= 0 and _slider_music and _label_music:
		var db: float = AudioServer.get_bus_volume_db(idx_music)
		var linear := _db_to_linear(db)
		_slider_music.value = linear * 100.0
		_update_label(_label_music, _slider_music.value)
	elif _slider_music and _label_music:
		_slider_music.value = 100.0
		_update_label(_label_music, 100.0)


func _update_label(lbl: Label, value: float) -> void:
	if lbl:
		lbl.text = "%d%%" % int(value)


func _apply_resolution() -> void:
	if not _resolution_option:
		return
	var idx := _resolution_option.selected
	if idx < 0 or idx >= RESOLUTIONS.size():
		return
	var r: Vector2i = RESOLUTIONS[idx]
	var w := get_viewport().get_window()
	if w:
		# 전체화면/최대화 시에는 창 크기가 바뀌지 않으므로, 먼저 창 모드로 전환한 뒤 크기 적용
		w.set_mode(Window.MODE_WINDOWED)
		w.set_size(r)


func _apply_volumes() -> void:
	var idx_master := AudioServer.get_bus_index("Master")
	if idx_master >= 0 and _slider_master:
		var linear := _slider_master.value / 100.0
		AudioServer.set_bus_volume_db(idx_master, _linear_to_db(linear))
	var idx_sfx := AudioServer.get_bus_index("SFX")
	if idx_sfx >= 0 and _slider_sfx:
		var linear := _slider_sfx.value / 100.0
		AudioServer.set_bus_volume_db(idx_sfx, _linear_to_db(linear))
	var idx_music := AudioServer.get_bus_index("Music")
	if idx_music >= 0 and _slider_music:
		var linear := _slider_music.value / 100.0
		AudioServer.set_bus_volume_db(idx_music, _linear_to_db(linear))


func _on_apply() -> void:
	_apply_resolution()
	_apply_volumes()


func _on_back() -> void:
	back_pressed.emit()
