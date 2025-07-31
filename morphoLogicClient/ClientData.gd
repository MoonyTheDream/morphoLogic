extends Node

const CONFIG_PATH = "res://client_config.cfg"

var server_general_topic := ""
var clients_general_topic := ""
var version := "0.1.0"
var username = null
var bootstrap_server := ""

func load_settings(path: String = CONFIG_PATH) -> ConfigFile:
	var config = ConfigFile.new()
	var err = config.load(path)
	
	if err != OK:
		push_error("Failed to load client config from %s: error code %s" % [path, err])
	return config

func _ready():
	var config := load_settings()
	server_general_topic = config.get_value("kafka", "serverGeneralTopic", "serverGeneralTopic")
	clients_general_topic = config.get_value("kafka", "clientsGeneralTopic", "clientsGeneralTopic")
	bootstrap_server = config.get_value("kafka", "bootstrapServer", "localhost:9092")