extends Control
## 사용자 정보 패널: 칼로리, 체중, BMI 등 헬스 매니지먼트 기능

signal back_pressed

@onready var _back_btn: Button = $Panel/VBox/BackButton
@onready var _daily_chart: Control = $Panel/VBox/Scroll/ScrollInner/DailyChart
@onready var _weight_spin: SpinBox = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSpin
@onready var _weight_save_btn: Button = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSaveButton
@onready var _weight_chart: Control = $Panel/VBox/Scroll/ScrollInner/WeightChart
@onready var _profile_label: Label = $Panel/VBox/Scroll/ScrollInner/ProfileLabel


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)
	if _weight_save_btn:
		_weight_save_btn.pressed.connect(_on_weight_save_pressed)
	_refresh_all()


func _refresh_all() -> void:
	_refresh_profile()
	_refresh_daily_chart()
	_refresh_weight_ui()


func _refresh_profile() -> void:
	if not _profile_label:
		return
	var bmi: float = GameState.get_bmi()
	var bmi_label: String = GameState.get_bmi_category_label() if bmi > 0.0 else "미측정"
	var today_kcal: float = GameState.get_today_calories()
	var lines: PackedStringArray = [
		"프로필",
		"  체중: %.1f kg" % GameState.get_weight_kg(),
		"  키: %.0f cm" % GameState.get_height_cm(),
		"  BMI: %.1f (%s)" % [bmi, bmi_label] if bmi > 0.0 else "  BMI: 입력 필요",
		"",
		"오늘 현황",
		"  소모 칼로리: %.1f kcal" % today_kcal,
	]
	_profile_label.text = "\n".join(lines)


func _refresh_daily_chart() -> void:
	if not _daily_chart:
		return
	var points: Array[Dictionary] = GameState.get_recent_daily_calories(30)
	if _daily_chart.has_method("set_points"):
		_daily_chart.set_points(points)


func _refresh_weight_ui() -> void:
	if _weight_spin:
		var logged: float = GameState.get_today_logged_weight_kg()
		if logged > 0.0:
			_weight_spin.value = logged
		else:
			_weight_spin.value = GameState.get_weight_kg()
	if _weight_chart and _weight_chart.has_method("set_points"):
		var wpoints: Array[Dictionary] = GameState.get_recent_daily_weight_log(30)
		_weight_chart.set_points(wpoints, {
			"value_key": "weight",
			"suffix": "kg",
			"color": Color(0.35, 0.75, 0.95, 0.95),
			"zero_based": false,
		})


func _on_weight_save_pressed() -> void:
	if not _weight_spin:
		return
	GameState.log_today_weight_kg(float(_weight_spin.value))
	_refresh_weight_ui()
	_refresh_profile()


func _on_back() -> void:
	back_pressed.emit()
