extends Control
## 세로 막대 차트: 일별 칼로리(기본) 또는 일별 체중 등 동일 형식 시리즈

var _points: Array[Dictionary] = []
var _value_key: String = "calories"
var _suffix: String = "kcal"
var _bar_color: Color = Color(0.95, 0.72, 0.15, 0.95)
var _zero_based: bool = true


func set_points(points: Array[Dictionary], opt: Dictionary = {}) -> void:
	_points = points
	_value_key = str(opt.get("value_key", "calories"))
	_suffix = str(opt.get("suffix", "kcal"))
	if opt.has("color"):
		_bar_color = opt["color"] as Color
	else:
		_bar_color = Color(0.95, 0.72, 0.15, 0.95)
	_zero_based = bool(opt.get("zero_based", _value_key == "calories"))
	queue_redraw()


func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	if rect.size.x <= 8.0 or rect.size.y <= 8.0:
		return
	var margin_left := 24.0
	var margin_right := 10.0
	var margin_top := 10.0
	var margin_bottom := 32.0
	var plot := Rect2(
		Vector2(margin_left, margin_top),
		Vector2(rect.size.x - margin_left - margin_right, rect.size.y - margin_top - margin_bottom)
	)
	if plot.size.x <= 10.0 or plot.size.y <= 10.0:
		return
	draw_rect(plot, Color(0.12, 0.12, 0.14, 0.7), true)
	draw_line(Vector2(plot.position.x, plot.end.y), Vector2(plot.end.x, plot.end.y), Color(0.8, 0.8, 0.8, 0.85), 1.5)
	draw_line(Vector2(plot.position.x, plot.position.y), Vector2(plot.position.x, plot.end.y), Color(0.8, 0.8, 0.8, 0.85), 1.5)
	if _points.is_empty():
		return
	var n := _points.size()
	var label_stride: int = maxi(1, int(ceil(float(n) / 8.0)))
	var label_fs: int = 9 if n > 14 else 11

	var min_v: float = 0.0
	var max_v: float = 1.0
	if _zero_based:
		max_v = 1.0
		for p in _points:
			max_v = maxf(max_v, float(p.get(_value_key, 0.0)))
	else:
		var lo: float = INF
		var hi: float = -INF
		for p in _points:
			var w: float = float(p.get(_value_key, 0.0))
			if w > 0.0:
				lo = minf(lo, w)
				hi = maxf(hi, w)
		if lo == INF:
			min_v = 0.0
			max_v = 1.0
		else:
			if hi - lo < 0.5:
				lo = maxf(30.0, lo - 2.0)
				hi = minf(180.0, hi + 2.0)
			min_v = lo
			max_v = hi

	var span: float = maxf(max_v - min_v, 0.0001)
	var slot_w := plot.size.x / float(n)
	var bar_w := clampf(slot_w * 0.55, 2.0, 26.0)
	if n > 14:
		bar_w = clampf(slot_w * 0.45, 2.0, 14.0)

	for i in range(n):
		var p: Dictionary = _points[i]
		var val: float = float(p.get(_value_key, 0.0))
		var ratio: float = 0.0
		if _zero_based:
			ratio = clampf(val / max_v, 0.0, 1.0)
		else:
			if val > 0.0:
				ratio = clampf((val - min_v) / span, 0.0, 1.0)
		var h: float = ratio * plot.size.y
		var x := plot.position.x + slot_w * float(i) + (slot_w - bar_w) * 0.5
		var y := plot.end.y - h
		var col := _bar_color
		if not _zero_based and val <= 0.0:
			col = Color(_bar_color.r, _bar_color.g, _bar_color.b, 0.35)
			h = 2.0
			y = plot.end.y - h
		draw_rect(Rect2(Vector2(x, y), Vector2(bar_w, h)), col, true)

		if i % label_stride == 0 or i == n - 1:
			var date_str: String = str(p.get("date", ""))
			var short_date := date_str.right(5) if date_str.length() >= 5 else date_str
			draw_string(
				get_theme_default_font(),
				Vector2(x - 4.0, plot.end.y + 16.0),
				short_date,
				HORIZONTAL_ALIGNMENT_LEFT,
				-1,
				label_fs,
				Color(0.92, 0.92, 0.95, 1.0)
			)

	var cap: String
	if _zero_based:
		cap = "max %.1f %s" % [max_v, _suffix]
	else:
		cap = "%.1f ~ %.1f %s" % [min_v, max_v, _suffix]
	draw_string(
		get_theme_default_font(),
		Vector2(plot.position.x, 12.0),
		cap,
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		11,
		Color(0.85, 0.85, 0.88, 1.0)
	)
