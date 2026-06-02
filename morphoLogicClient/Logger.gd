extends Node

enum Level {
	DEBUG,
	INFO,
	WARNING,
	ERROR
}
const LEVEL_NAMES = {
	Level.DEBUG: "DEBUG",
	Level.INFO: "INFO",
	Level.WARNING: "WARNING",
	Level.ERROR: "ERROR"
}

var min_level: int = Level.INFO
var _file: FileAccess

func _ready() -> void:
	if ClientData.debug_logging:
		min_level = Level.DEBUG
	DirAccess.make_dir_recursive_absolute("user://logs")
	_file = FileAccess.open("user://logs/client.log", FileAccess.WRITE)

func _write(level: int, subsystem: String, msg: String) -> void:
	if level < min_level:
		return
	var ts := Time.get_datetime_string_from_system(true, true)
	var line := "[%s][%s][%s]: %s" % [ts, LEVEL_NAMES[level], subsystem, msg]
	if level >= Level.ERROR:
		printerr(line)
	else:
		print(line)
	if _file:
		_file.store_line(line)
		_file.flush()


func debug(subsystem: String, msg: String) -> void: _write(Level.DEBUG, subsystem, msg)
func info(subsystem: String, msg: String) -> void:  _write(Level.INFO, subsystem, msg)
func warning(subsystem: String, msg: String) -> void:  _write(Level.WARNING, subsystem, msg)
func error(subsystem: String, msg: String) -> void: _write(Level.ERROR, subsystem, msg)
