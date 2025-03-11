extends Node

const SETTINGS_FILE = "res://settings.json"

func load_settings(path: String = SETTINGS_FILE) -> Dictionary:
	"""
	Loads global settings from a JSON file.
	Returns an empty dictionary if the file is missing.
	"""
	if not FileAccess.file_exists(path):
		push_error("Settings file %s not found." % path)
		return {}  # Returning an empty dictionary instead of raising an error

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Failed to open settings file: %s" % path)
		return {}

	var content := file.get_as_text()
	return JSON.parse_string(content)

var server_general_topic = load_settings().get("generalTopic", "")

var version = "0.1.0"
var username = null
