extends RefCounted
## Internal seam: manages the webcam ML Python process lifecycle.
## GameState owns an instance and delegates to it.


var bridge_pid: int = -1
var launched_camera: int = -999
var launched_backend: String = ""
var launched_profile: String = ""
var launched_roi: bool = false
var launched_zone: float = 0.3
var launched_skip_guard: bool = false
var launched_full_body_squat: bool = false


func is_running() -> bool:
	return bridge_pid > 0 and _is_process_running_safe(bridge_pid)


func get_pid() -> int:
	return bridge_pid


func ensure(
	auto_launch: bool,
	camera_index: int,
	camera_backend: String,
	ml_speed_profile: String,
	roi_mode: bool,
	center_zone_margin: float,
	skip_guard_single: bool,
	full_body_squat: bool,
	python_exe: String,
	script_path: String,
) -> void:
	if not auto_launch:
		return
	if bridge_pid > 0 and not _is_process_running_safe(bridge_pid):
		bridge_pid = -1
	if bridge_pid > 0 and _is_process_running_safe(bridge_pid):
		if (
			launched_camera == camera_index
			and launched_backend == camera_backend
			and launched_profile == ml_speed_profile
			and launched_roi == roi_mode
			and launched_zone == center_zone_margin
			and launched_skip_guard == skip_guard_single
			and launched_full_body_squat == full_body_squat
		):
			print(
				"웹캠 ML 브리지 유지 (PID=%d, index=%d, backend=%s, profile=%s, roi=%s, zone=%.2f, skip_guard=%s, full_body=%s)"
				% [bridge_pid, camera_index, camera_backend, ml_speed_profile, str(roi_mode), center_zone_margin, str(skip_guard_single), str(full_body_squat)]
			)
			return
		var kerr: Error = OS.kill(bridge_pid)
		if kerr != OK:
			push_warning("이전 웹캠 ML 브리지 종료 실패 PID=%d" % bridge_pid)
		bridge_pid = -1
	var args := PackedStringArray([
		script_path,
		"--camera-index",
		str(camera_index),
		"--camera-backend",
		camera_backend,
		"--profile",
		ml_speed_profile,
	])
	if roi_mode:
		args.append("--roi")
	args.append("--center-zone")
	args.append(str(center_zone_margin))
	if skip_guard_single:
		args.append("--skip-guard-single")
	if full_body_squat:
		args.append("--full-body-squat")
	print("웹캠 ML 실행 시도: python=", python_exe, " script=", script_path, " profile=", ml_speed_profile, " roi=", roi_mode, " zone=", center_zone_margin, " skip_guard=", skip_guard_single, " full_body=", full_body_squat)
	bridge_pid = OS.create_process(python_exe, args, false)
	if bridge_pid <= 0:
		push_warning("웹캠 ML 브리지 시작 실패(OS.create_process).")
		_reset_launched()
	else:
		launched_camera = camera_index
		launched_backend = camera_backend
		launched_profile = ml_speed_profile
		launched_roi = roi_mode
		launched_zone = center_zone_margin
		launched_skip_guard = skip_guard_single
		launched_full_body_squat = full_body_squat
		print("웹캠 ML 브리지 시작 PID=", bridge_pid, " index=", camera_index, " backend=", camera_backend, " profile=", ml_speed_profile, " roi=", roi_mode, " zone=", center_zone_margin, " skip_guard=", skip_guard_single, " full_body=", full_body_squat)


func shutdown() -> void:
	if bridge_pid > 0:
		var kerr: Error = OS.kill(bridge_pid)
		if kerr != OK:
			push_warning("웹캠 ML 브리지 종료 실패 PID=%d" % bridge_pid)
	_reset_launched()


func _reset_launched() -> void:
	bridge_pid = -1
	launched_camera = -999
	launched_backend = ""
	launched_profile = ""
	launched_roi = false
	launched_zone = 0.3
	launched_skip_guard = false
	launched_full_body_squat = false


func _is_process_running_safe(pid: int) -> bool:
	if pid <= 0:
		return false
	return OS.is_process_running(pid)



