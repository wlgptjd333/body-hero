class_name SettingsPanelUI
extends Control
## 설정 패널: 해상도, 소리, 키보드 설정(리바인드), 적용, 뒤로가기

signal back_pressed

const INPUT_CONFIG_PATH := "user://input.cfg"
const RESOLUTIONS := [
	Vector2i(1152, 648),
	Vector2i(1280, 720),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
]

# 키보드 설정용 액션 이름과 버튼 노드 경로
const KEY_ACTIONS := [
	["punch_left", "Panel/Scroll/VBox/KeySection/KeyRowPunchLeft/KeyBtnPunchLeft"],
	["punch_right", "Panel/Scroll/VBox/KeySection/KeyRowPunchRight/KeyBtnPunchRight"],
	["upper_left", "Panel/Scroll/VBox/KeySection/KeyRowUpperLeft/KeyBtnUpperLeft"],
	["upper_right", "Panel/Scroll/VBox/KeySection/KeyRowUpperRight/KeyBtnUpperRight"],
	["hook_left", "Panel/Scroll/VBox/KeySection/KeyRowHookLeft/KeyBtnHookLeft"],
	["hook_right", "Panel/Scroll/VBox/KeySection/KeyRowHookRight/KeyBtnHookRight"],
	["guard", "Panel/Scroll/VBox/KeySection/KeyRowGuard/KeyBtnGuard"],
]

var _waiting_action: String = ""
var _key_buttons: Dictionary = {}  # action_name -> Button

@onready var _resolution_option: OptionButton = $Panel/Scroll/VBox/ResolutionSection/ResolutionRow/OptionButton
@onready var _slider_master: HSlider = $Panel/Scroll/VBox/SoundSection/MasterRow/HSlider
@onready var _label_master: Label = $Panel/Scroll/VBox/SoundSection/MasterRow/ValueLabel
@onready var _slider_sfx: HSlider = $Panel/Scroll/VBox/SoundSection/GameRow/HSlider
@onready var _label_sfx: Label = $Panel/Scroll/VBox/SoundSection/GameRow/ValueLabel
@onready var _slider_music: HSlider = $Panel/Scroll/VBox/SoundSection/MusicRow/HSlider
@onready var _label_music: Label = $Panel/Scroll/VBox/SoundSection/MusicRow/ValueLabel
@onready var _gender_option: OptionButton = $Panel/Scroll/VBox/HealthSection/GenderRow/GenderOption
@onready var _age_spin: SpinBox = $Panel/Scroll/VBox/HealthSection/AgeRow/AgeSpinBox
@onready var _height_spin: SpinBox = $Panel/Scroll/VBox/HealthSection/HeightRow/HeightSpinBox
@onready var _weight_spin: SpinBox = $Panel/Scroll/VBox/HealthSection/WeightRow/WeightSpinBox
@onready var _intensity_option: OptionButton = $Panel/Scroll/VBox/HealthSection/IntensityRow/IntensityOption
@onready var _btn_back: Button = $Panel/Scroll/VBox/BackButton
@onready var _btn_apply: Button = $Panel/Scroll/VBox/ApplyButton


func _ready() -> void:
	_setup_resolutions()
	_setup_volumes()
	_setup_health_profile()
	_setup_keyboard()
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


func _setup_health_profile() -> void:
	if _gender_option:
		var g := GameState.get_gender()
		if g == GameState.GENDER_FEMALE:
			_gender_option.selected = 2
		elif g == GameState.GENDER_OTHER:
			_gender_option.selected = 3
		else:
			_gender_option.selected = 1
	if _age_spin:
		_age_spin.value = float(GameState.get_age())
	if _height_spin:
		_height_spin.value = GameState.get_height_cm()
	if _weight_spin:
		_weight_spin.value = GameState.get_weight_kg()
	if _intensity_option:
		var factor := GameState.get_intensity_factor()
		if factor < 0.95:
			_intensity_option.selected = 0
		elif factor > 1.05:
			_intensity_option.selected = 2
		else:
			_intensity_option.selected = 1


func _apply_health_profile() -> void:
	if _gender_option:
		match _gender_option.selected:
			0:
				GameState.set_gender("")
			2:
				GameState.set_gender(GameState.GENDER_FEMALE)
			3:
				GameState.set_gender(GameState.GENDER_OTHER)
			_:
				GameState.set_gender(GameState.GENDER_MALE)
	if _age_spin:
		GameState.set_age(int(_age_spin.value))
	if _height_spin:
		GameState.set_height_cm(float(_height_spin.value))
	if _weight_spin:
		GameState.set_weight_kg(float(_weight_spin.value))
	if _intensity_option:
		var factor := 1.0
		match _intensity_option.selected:
			0:
				factor = 0.9
			2:
				factor = 1.1
			_:
				factor = 1.0
		GameState.set_intensity_factor(factor)


func _on_apply() -> void:
	_apply_resolution()
	_apply_volumes()
	_apply_health_profile()


func _on_back() -> void:
	back_pressed.emit()


# --- 키보드 설정 ---

func _setup_keyboard() -> void:
	for arr in KEY_ACTIONS:
		var action: String = arr[0]
		var path: String = arr[1]
		var btn: Button = get_node_or_null(path)
		if btn:
			_key_buttons[action] = btn
			btn.pressed.connect(_on_key_button_pressed.bind(action))
	_refresh_key_labels()


func _refresh_key_labels() -> void:
	for action in _key_buttons:
		var btn: Button = _key_buttons[action]
		if not btn or _waiting_action == action:
			continue
		var ev: InputEvent = _get_first_key_event(action)
		btn.text = _key_event_to_display(ev)


func _get_first_key_event(action: String) -> InputEvent:
	if not InputMap.has_action(action):
		return null
	var events: Array = InputMap.action_get_events(action)
	for ev in events:
		if ev is InputEventKey:
			return ev
	return null


func _key_event_to_display(ev: InputEvent) -> String:
	if ev == null:
		return "?"
	if ev is InputEventKey:
		var k: InputEventKey = ev as InputEventKey
		return k.as_text_physical_keycode()
	return "?"


func _on_key_button_pressed(action: String) -> void:
	if _waiting_action == action:
		return
	_waiting_action = action
	var btn: Button = _key_buttons.get(action)
	if btn:
		btn.text = "누르세요..."


func _input(event: InputEvent) -> void:
	if _waiting_action.is_empty():
		return
	if not event is InputEventKey:
		return
	var key_ev: InputEventKey = event as InputEventKey
	if not key_ev.pressed or key_ev.echo:
		return
	# ESC로 취소
	if key_ev.keycode == KEY_ESCAPE:
		_waiting_action = ""
		_refresh_key_labels()
		get_viewport().set_input_as_handled()
		return
	var phys: int = key_ev.physical_keycode
	_assign_key_to_action(_waiting_action, phys)
	_save_input_config()
	_waiting_action = ""
	_refresh_key_labels()
	get_viewport().set_input_as_handled()


func _assign_key_to_action(action: String, physical_keycode: int) -> void:
	# 다른 액션에서 같은 키 제거
	for other_action in _key_buttons:
		if other_action == action:
			continue
		var events: Array = InputMap.action_get_events(other_action)
		for i in range(events.size() - 1, -1, -1):
			if events[i] is InputEventKey and (events[i] as InputEventKey).physical_keycode == physical_keycode:
				InputMap.action_erase_event(other_action, events[i])
	var new_ev := InputEventKey.new()
	new_ev.physical_keycode = physical_keycode
	InputMap.action_erase_events(action)
	InputMap.action_add_event(action, new_ev)


func _save_input_config() -> void:
	var cfg := ConfigFile.new()
	for arr in KEY_ACTIONS:
		var action: String = arr[0]
		var ev: InputEvent = _get_first_key_event(action)
		if ev is InputEventKey:
			cfg.set_value("input", action, (ev as InputEventKey).physical_keycode)
	var err := cfg.save(INPUT_CONFIG_PATH)
	if err != OK:
		push_warning("키 설정 저장 실패: %s" % INPUT_CONFIG_PATH)


static func load_input_config_from_disk() -> void:
	if not FileAccess.file_exists(INPUT_CONFIG_PATH):
		return
	var cfg := ConfigFile.new()
	var err := cfg.load(INPUT_CONFIG_PATH)
	if err != OK:
		return
	var actions := [
		"punch_left", "punch_right", "upper_left", "upper_right",
		"hook_left", "hook_right", "guard"
	]
	for action in actions:
		if not cfg.has_section_key("input", action):
			continue
		if not InputMap.has_action(action):
			continue
		var phys: int = cfg.get_value("input", action, 0)
		if phys <= 0:
			continue
		InputMap.action_erase_events(action)
		var ev := InputEventKey.new()
		ev.physical_keycode = phys
		InputMap.action_add_event(action, ev)
