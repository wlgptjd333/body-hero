class_name SettingsPanelUI
extends Control
## 설정 패널: 해상도, 웹캠(카메라 인덱스), 소리, 키보드 설정(리바인드), 적용, 뒤로가기

signal back_pressed

const INPUT_CONFIG_PATH := "user://input.cfg"
const RESOLUTIONS := [
	Vector2i(1152, 648),
	Vector2i(1280, 720),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
]

# 키보드: punch_left/right 에 기본 보조 키(Z/C)를 함께 둠. 저장은 punch_left + punch_left_aux.
const DEFAULT_PUNCH_LEFT_AUX: int = KEY_Z
const DEFAULT_PUNCH_RIGHT_AUX: int = KEY_C
## GameState.ML_SPEED_PROFILE_VALUES 와 같은 순서.
const ML_PROFILE_UI_LABELS: Array[String] = [
	"균형 (balanced)",
	"빠른 반응 (fast_react)",
	"연타 (fast_combo)",
	"최고 속도 (max_speed)",
]

const KEY_ACTIONS := [
	["punch_left", "Panel/Scroll/VBox/KeySection/KeyRowPunchLeft/KeyBtnPunchLeft"],
	["punch_right", "Panel/Scroll/VBox/KeySection/KeyRowPunchRight/KeyBtnPunchRight"],
	["upper_left", "Panel/Scroll/VBox/KeySection/KeyRowUpperLeft/KeyBtnUpperLeft"],
	["upper_right", "Panel/Scroll/VBox/KeySection/KeyRowUpperRight/KeyBtnUpperRight"],
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
@onready var _camera_option: OptionButton = $Panel/Scroll/VBox/WebcamSection/CameraRow/CameraOption
@onready var _backend_option: OptionButton = $Panel/Scroll/VBox/WebcamSection/BackendRow/BackendOption
@onready var _ml_profile_option: OptionButton = $Panel/Scroll/VBox/WebcamSection/MlProfileRow/MlProfileOption
@onready var _btn_refresh_cameras: Button = $Panel/Scroll/VBox/WebcamSection/RefreshRow/BtnRefreshCameras
@onready var _btn_start_webcam_ml: Button = $Panel/Scroll/VBox/WebcamSection/WebcamMlRow/BtnStartWebcamMl
@onready var _btn_stop_webcam_ml: Button = $Panel/Scroll/VBox/WebcamSection/WebcamMlRow/BtnStopWebcamMl
@onready var _btn_start_collect_pose: Button = $Panel/Scroll/VBox/WebcamSection/CollectPoseRow/BtnStartCollectPose
@onready var _lbl_collect_pose_hint: Label = $Panel/Scroll/VBox/WebcamSection/LblCollectPoseHint
@onready var _lbl_webcam_ml_bridge: Label = $Panel/Scroll/VBox/WebcamSection/LblWebcamMlBridge
@onready var _lbl_camera_hint: Label = $Panel/Scroll/VBox/WebcamSection/CameraHintLabel
@onready var _btn_back: Button = $Panel/Scroll/VBox/BackButton
@onready var _btn_apply: Button = $Panel/ApplyButton


func _ready() -> void:
	_setup_resolutions()
	_setup_webcam_camera()
	_setup_ml_profile_option()
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
	if _btn_refresh_cameras:
		_btn_refresh_cameras.pressed.connect(_on_refresh_cameras_pressed)
	if _btn_start_webcam_ml:
		_btn_start_webcam_ml.pressed.connect(_on_start_webcam_ml_pressed)
	if _btn_stop_webcam_ml:
		_btn_stop_webcam_ml.pressed.connect(_on_stop_webcam_ml_pressed)
	if _btn_start_collect_pose:
		_btn_start_collect_pose.pressed.connect(_on_start_collect_pose_pressed)


func _setup_webcam_camera() -> void:
	_fill_camera_option_default()
	_select_camera_id_in_option(GameState.get_camera_index())
	_setup_webcam_backend_option()


func _setup_ml_profile_option() -> void:
	if not _ml_profile_option:
		return
	_ml_profile_option.clear()
	var ids: Array[String] = GameState.ML_SPEED_PROFILE_VALUES
	for i: int in range(ids.size()):
		var lab: String = ids[i]
		if i < ML_PROFILE_UI_LABELS.size():
			lab = ML_PROFILE_UI_LABELS[i]
		_ml_profile_option.add_item(lab, i)
	var cur: String = GameState.get_ml_speed_profile()
	var sel: int = 0
	for j: int in range(ids.size()):
		if ids[j] == cur:
			sel = j
			break
	_ml_profile_option.select(clampi(sel, 0, _ml_profile_option.item_count - 1))


func _setup_webcam_backend_option() -> void:
	if not _backend_option:
		return
	_backend_option.clear()
	var labels: Array[String] = [
		"자동 (Windows에서 DirectShow 우선)",
		"DirectShow — USB에 자주 필요",
		"MSMF",
		"OpenCV 기본",
	]
	for i: int in range(labels.size()):
		_backend_option.add_item(labels[i], i)
	var cur: String = GameState.get_camera_backend()
	var sel: int = 0
	for j: int in range(GameState.CAMERA_BACKEND_VALUES.size()):
		if str(GameState.CAMERA_BACKEND_VALUES[j]) == cur:
			sel = j
			break
	_backend_option.select(clampi(sel, 0, _backend_option.item_count - 1))


func _fill_camera_option_default() -> void:
	if not _camera_option:
		return
	_camera_option.clear()
	for i in range(10):
		_camera_option.add_item("카메라 %d" % i, i)


func _select_camera_id_in_option(want_id: int) -> void:
	if not _camera_option:
		return
	for i in range(_camera_option.item_count):
		if _camera_option.get_item_id(i) == want_id:
			_camera_option.select(i)
			return
	_camera_option.select(0)


func _on_refresh_cameras_pressed() -> void:
	if _lbl_camera_hint:
		_lbl_camera_hint.text = "스캔 중…"
	var py: String = GameState.get_venv_python_executable()
	var list_script: String = GameState.get_list_cameras_script_path()
	if not FileAccess.file_exists(py) or not FileAccess.file_exists(list_script):
		if _lbl_camera_hint:
			_lbl_camera_hint.text = "venv_ml Python 또는 list_cameras.py 없음. tools 폴더를 확인하세요."
		return
	var out_path: String = ProjectSettings.globalize_path("user://camera_list_scan.txt")
	var exec_out: Array = []
	var back: String = GameState.get_camera_backend()
	var exit_code: int = OS.execute(
		py,
		PackedStringArray([list_script, out_path, "--backend", back]),
		exec_out,
		false,
		false,
	)
	if exit_code != 0:
		if _lbl_camera_hint:
			_lbl_camera_hint.text = "목록 스캔 실패(opencv 등). 번호(0~9)를 직접 골라 보세요."
		return
	if not FileAccess.file_exists(out_path):
		if _lbl_camera_hint:
			_lbl_camera_hint.text = "출력 파일 없음."
		return
	var f := FileAccess.open(out_path, FileAccess.READ)
	if f == null:
		if _lbl_camera_hint:
			_lbl_camera_hint.text = "결과 파일을 열 수 없습니다."
		return
	var content := f.get_as_text()
	f.close()
	var found: Array[int] = []
	for line: String in content.split("\n"):
		var s := line.strip_edges()
		if s.is_empty():
			continue
		if s.is_valid_int():
			found.append(int(s))
	if found.is_empty():
		_fill_camera_option_default()
		if _lbl_camera_hint:
			_lbl_camera_hint.text = "열린 카메라 없음. 장치 연결 후 다시 시도하거나 번호를 직접 선택하세요."
	else:
		_camera_option.clear()
		for idx in found:
			_camera_option.add_item("카메라 %d (열림)" % idx, idx)
		_select_camera_id_in_option(GameState.get_camera_index())
		if _lbl_camera_hint:
			var parts: String = ""
			for j: int in range(found.size()):
				if j > 0:
					parts += ", "
				parts += str(found[j])
			_lbl_camera_hint.text = "OpenCV 기준 열리는 인덱스: %s" % parts


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
		# Windows 등에서 모드 전환 직후 같은 프레임 set_size 가 무시되는 경우가 있어 지연 적용
		w.call_deferred("set_size", r)


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


func _get_camera_index_from_ui() -> int:
	var cam_id := 0
	if _camera_option and _camera_option.item_count > 0 and _camera_option.selected >= 0:
		cam_id = _camera_option.get_item_id(_camera_option.selected)
	return cam_id


func _get_camera_backend_from_ui() -> String:
	var backend_str := GameState.get_camera_backend()
	if _backend_option and _backend_option.item_count > 0 and _backend_option.selected >= 0:
		var bi := clampi(_backend_option.selected, 0, GameState.CAMERA_BACKEND_VALUES.size() - 1)
		backend_str = str(GameState.CAMERA_BACKEND_VALUES[bi])
	return backend_str


func _get_ml_speed_profile_from_ui() -> String:
	var ids: Array[String] = GameState.ML_SPEED_PROFILE_VALUES
	if not _ml_profile_option or _ml_profile_option.item_count <= 0:
		return GameState.get_ml_speed_profile()
	var si := clampi(_ml_profile_option.selected, 0, ids.size() - 1)
	return ids[si]


func _save_webcam_and_window_from_ui() -> void:
	var sz := _get_window_size()
	GameState.save_display_settings(
		sz.x,
		sz.y,
		_get_camera_index_from_ui(),
		_get_camera_backend_from_ui(),
		_get_ml_speed_profile_from_ui(),
	)


func _on_apply() -> void:
	_apply_resolution()
	_apply_volumes()
	_apply_health_profile()
	_save_webcam_and_window_from_ui()


func _on_start_webcam_ml_pressed() -> void:
	_save_webcam_and_window_from_ui()
	if not GameState.has_webcam_ml_runtime_files():
		if _lbl_webcam_ml_bridge:
			_lbl_webcam_ml_bridge.text = "tools/udp_send_webcam_ml.py 가 없습니다. (Python은 venv_ml 또는 PATH의 python, 또는 BODY_HERO_PYTHON_EXE)"
		return
	GameState.ensure_webcam_ml_bridge(true)
	await get_tree().process_frame
	if GameState.is_webcam_ml_bridge_running():
		var pid: int = GameState.get_webcam_ml_bridge_pid()
		if _lbl_webcam_ml_bridge:
			_lbl_webcam_ml_bridge.text = (
				"웹캠 ML 실행 중 (PID %d). Python 창이 뜨고 TensorFlow 준비에 시간이 걸릴 수 있습니다." % pid
			)
	else:
		if _lbl_webcam_ml_bridge:
			_lbl_webcam_ml_bridge.text = "시작에 실패했거나 프로세스가 바로 종료되었습니다. 콘솔 로그를 확인하세요."


func _on_stop_webcam_ml_pressed() -> void:
	GameState.shutdown_webcam_ml_bridge()
	if _lbl_webcam_ml_bridge:
		_lbl_webcam_ml_bridge.text = "웹캠 ML 프로세스를 종료했습니다."


func _on_start_collect_pose_pressed() -> void:
	_save_webcam_and_window_from_ui()
	var tools_dir: String = GameState.get_tools_absolute_dir()
	var script_path: String = tools_dir.path_join("collect_pose_data.py")
	if not FileAccess.file_exists(script_path):
		if _lbl_collect_pose_hint:
			_lbl_collect_pose_hint.text = "collect_pose_data.py 를 찾을 수 없습니다 (tools 폴더)."
		return
	var py: String = GameState.resolve_python_executable_for_ml()
	if py != "python.exe" and py != "python3" and not FileAccess.file_exists(py):
		if _lbl_collect_pose_hint:
			_lbl_collect_pose_hint.text = "Python 실행 파일이 없습니다. tools/venv_ml 또는 BODY_HERO_PYTHON_EXE 를 확인하세요."
		return
	var cam: String = str(GameState.get_camera_index())
	var backend: String = GameState.get_camera_backend()
	var args := PackedStringArray([
		script_path,
		"--camera-index",
		cam,
		"--camera-backend",
		backend,
	])
	if OS.get_name() != "Windows":
		var quoted: String = (
			"\"%s\"" % script_path
			if script_path.contains(" ") or py.contains(" ")
			else script_path
		)
		var cmd: String = "%s %s --camera-index %s --camera-backend %s" % [py, quoted, cam, backend]
		DisplayServer.clipboard_set(cmd)
		if _lbl_collect_pose_hint:
			_lbl_collect_pose_hint.text = (
				"Windows가 아니면 터미널에서 직접 실행하세요. 명령을 클립보드에 복사했습니다: " + cmd
			)
		return
	var pid: int = OS.create_process(py, args, true)
	if pid > 0:
		if _lbl_collect_pose_hint:
			_lbl_collect_pose_hint.text = (
				"포즈 녹화를 실행했습니다 (카메라 %s, %s). 콘솔에서 녹화 후 Q로 저장·종료하세요." % [cam, backend]
			)
	else:
		if _lbl_collect_pose_hint:
			_lbl_collect_pose_hint.text = "collect_pose_data.py 실행에 실패했습니다. 경로·권한·Python 설치를 확인하세요."


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
		if action == "punch_left" or action == "punch_right":
			btn.text = _punch_action_key_display(action)
		else:
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


func _punch_action_key_display(action: String) -> String:
	if not InputMap.has_action(action):
		return "?"
	var parts: Array[String] = []
	for ev in InputMap.action_get_events(action):
		if ev is InputEventKey:
			var kk: InputEventKey = ev as InputEventKey
			parts.append(kk.as_text_physical_keycode())
	if parts.is_empty():
		return "?"
	return " / ".join(parts)


func _ordered_phys_codes_for_action(action: String) -> Array[int]:
	var out: Array[int] = []
	if not InputMap.has_action(action):
		return out
	for ev in InputMap.action_get_events(action):
		if ev is InputEventKey:
			var p: int = (ev as InputEventKey).physical_keycode
			if p > 0 and not out.has(p):
				out.append(p)
	return out


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
	for other_action in _key_buttons:
		if other_action == action:
			continue
		var events: Array = InputMap.action_get_events(other_action)
		for i in range(events.size() - 1, -1, -1):
			if events[i] is InputEventKey and (events[i] as InputEventKey).physical_keycode == physical_keycode:
				InputMap.action_erase_event(other_action, events[i])
	if action == "punch_left" or action == "punch_right":
		var aux_default: int = (
			DEFAULT_PUNCH_LEFT_AUX if action == "punch_left" else DEFAULT_PUNCH_RIGHT_AUX
		)
		InputMap.action_erase_events(action)
		var primary_ev := InputEventKey.new()
		primary_ev.physical_keycode = physical_keycode
		InputMap.action_add_event(action, primary_ev)
		if physical_keycode != aux_default:
			var aux_ev := InputEventKey.new()
			aux_ev.physical_keycode = aux_default
			InputMap.action_add_event(action, aux_ev)
	else:
		var new_ev := InputEventKey.new()
		new_ev.physical_keycode = physical_keycode
		InputMap.action_erase_events(action)
		InputMap.action_add_event(action, new_ev)


func _save_input_config() -> void:
	var cfg := ConfigFile.new()
	if FileAccess.file_exists(INPUT_CONFIG_PATH):
		cfg.load(INPUT_CONFIG_PATH)
	for arr in KEY_ACTIONS:
		var action: String = arr[0]
		if action == "punch_left" or action == "punch_right":
			var codes: Array[int] = _ordered_phys_codes_for_action(action)
			if codes.is_empty():
				continue
			cfg.set_value("input", action, codes[0])
			var aux_key: String = "%s_aux" % action
			if codes.size() >= 2:
				cfg.set_value("input", aux_key, codes[1])
			elif cfg.has_section_key("input", aux_key):
				cfg.erase_section_key("input", aux_key)
		else:
			var ev: InputEvent = _get_first_key_event(action)
			if ev is InputEventKey:
				cfg.set_value("input", action, (ev as InputEventKey).physical_keycode)
	for dead: String in ["hook_left", "hook_right"]:
		if cfg.has_section_key("input", dead):
			cfg.erase_section_key("input", dead)
	var err := cfg.save(INPUT_CONFIG_PATH)
	if err != OK:
		push_warning("키 설정 저장 실패: %s" % INPUT_CONFIG_PATH)


static func load_input_config_from_disk() -> void:
	if not FileAccess.file_exists(INPUT_CONFIG_PATH):
		return
	var cfg := ConfigFile.new()
	if cfg.load(INPUT_CONFIG_PATH) != OK:
		return
	var legacy_hook_l: int = 0
	if cfg.has_section_key("input", "hook_left"):
		legacy_hook_l = int(cfg.get_value("input", "hook_left", 0))
	var legacy_hook_r: int = 0
	if cfg.has_section_key("input", "hook_right"):
		legacy_hook_r = int(cfg.get_value("input", "hook_right", 0))
	for action in ["upper_left", "upper_right", "guard"]:
		if not cfg.has_section_key("input", action) or not InputMap.has_action(action):
			continue
		var phys: int = int(cfg.get_value("input", action, 0))
		if phys <= 0:
			continue
		InputMap.action_erase_events(action)
		var ev := InputEventKey.new()
		ev.physical_keycode = phys
		InputMap.action_add_event(action, ev)
	if InputMap.has_action("punch_left"):
		var touch_l: bool = (
			cfg.has_section_key("input", "punch_left")
			or cfg.has_section_key("input", "punch_left_aux")
			or legacy_hook_l > 0
		)
		if touch_l:
			var prim_l: int = int(cfg.get_value("input", "punch_left", 0))
			var aux_l: int = int(cfg.get_value("input", "punch_left_aux", 0))
			if aux_l <= 0 and legacy_hook_l > 0:
				aux_l = legacy_hook_l
			_apply_punch_keys_from_disk("punch_left", prim_l, aux_l, KEY_Z)
	if InputMap.has_action("punch_right"):
		var touch_r: bool = (
			cfg.has_section_key("input", "punch_right")
			or cfg.has_section_key("input", "punch_right_aux")
			or legacy_hook_r > 0
		)
		if touch_r:
			var prim_r: int = int(cfg.get_value("input", "punch_right", 0))
			var aux_r: int = int(cfg.get_value("input", "punch_right_aux", 0))
			if aux_r <= 0 and legacy_hook_r > 0:
				aux_r = legacy_hook_r
			_apply_punch_keys_from_disk("punch_right", prim_r, aux_r, KEY_C)


static func _apply_punch_keys_from_disk(action: String, primary: int, aux: int, default_aux: int) -> void:
	if not InputMap.has_action(action):
		return
	InputMap.action_erase_events(action)
	var keys: Array[int] = []
	if primary > 0:
		keys.append(primary)
	if aux > 0 and aux != primary and not keys.has(aux):
		keys.append(aux)
	if keys.size() == 1 and default_aux > 0 and keys[0] != default_aux and not keys.has(default_aux):
		keys.append(default_aux)
	for code in keys:
		var k := InputEventKey.new()
		k.physical_keycode = code
		InputMap.action_add_event(action, k)
