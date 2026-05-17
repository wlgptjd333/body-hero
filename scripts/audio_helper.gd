extends Node
## Audio stream loading utility (AutoLoad).
## Access via AudioHelper.try_load_stream(player, paths)

func try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p: String in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return
