extends RefCounted
## GitHub Releases에서 python_embed.zip 다운로드 + ZIPReader 압축풀기.
## 로컬에 zip이 있으면 인터넷 없이도 설치 가능.

signal download_completed(success: bool)

const RELEASE_URL := "https://github.com/wlgptjd333/body-hero/releases/download/python-embed-v1.0/python_embed.zip"

var _parent: Node
var _target_dir: String
var _zip_path: String


func download(target_dir: String, parent: Node) -> void:
	_parent = parent
	_target_dir = target_dir
	_zip_path = target_dir.path_join("python_embed.zip")

	DirAccess.make_dir_recursive_absolute(target_dir)

	if FileAccess.file_exists(_zip_path):
		_extract_zip()
		return

	if not _download_from_github():
		download_completed.emit(false)


func _download_from_github() -> bool:
	var http := HTTPRequest.new()
	http.download_file = _zip_path
	http.request_completed.connect(_on_download_completed)
	_parent.add_child(http)
	var err := http.request(RELEASE_URL)
	if err != OK:
		push_error("Python ML 환경 다운로드 실패: ", err)
		return false
	return true


func _on_download_completed(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	var children := _parent.get_children()
	for c in children:
		if c is HTTPRequest:
			c.queue_free()

	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		push_error("다운로드 실패 (result=%d, http=%d)" % [result, response_code])
		download_completed.emit(false)
		return

	_extract_zip()


func _extract_zip() -> void:
	if not FileAccess.file_exists(_zip_path):
		push_error("ZIP 파일 없음: ", _zip_path)
		download_completed.emit(false)
		return

	var reader := ZIPReader.new()
	var err := reader.open(_zip_path)
	if err != OK:
		push_error("ZIP 열기 실패: ", err)
		download_completed.emit(false)
		return

	for file_path in reader.get_files():
		var full_path := _target_dir.path_join(file_path)
		if file_path.ends_with("/"):
			DirAccess.make_dir_recursive_absolute(full_path)
		else:
			DirAccess.make_dir_recursive_absolute(full_path.get_base_dir())
			var file := FileAccess.open(full_path, FileAccess.WRITE)
			if file:
				file.store_buffer(reader.read_file(file_path))
				file.close()

	reader.close()

	var flag := FileAccess.open(_target_dir.path_join("downloaded.flag"), FileAccess.WRITE)
	if flag:
		flag.store_line("ok")
		flag.close()

	download_completed.emit(true)
