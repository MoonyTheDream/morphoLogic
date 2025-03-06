extends Node

# var microserver_process_id = null # storing process ID of microserver for cleanup
var TCPClient = StreamPeerTCP.new()
const SERVER_IP = "127.0.0.1"
const TEMP_FILE_PATH = "res://temp_port.txt"
var assigned_port = -1
var microserver_process = -1
# const SERVER_PORT = 6164
signal new_data_arrived(data)
var root
# var username = null

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	# run_python_microserver()
	root = get_tree().root

func run_python_microserver() -> bool:
	# Executing Python script
	var python_executable = ProjectSettings.globalize_path("res://")
	python_executable += "microserver/kafka_env/bin/python3"
	# if OS.get_name() == "Windows":
	# 	python_executable = "kafka_env\\Scripts\\python.exe"
	var script_path = ProjectSettings.globalize_path("res://")
	script_path += "microserver/microserver.py"
	
	# Run the script
	var microserver_process_id = OS.create_process(python_executable, [script_path])
	# print(microserver_process_id)
	if microserver_process_id != -1:
		microserver_process = microserver_process_id
		print("Python microserver started successfully. Process: %s" % microserver_process)
		var connected = await _initialize_tcp_connection()
		if connected:
			return true
	print("Failed to start Python microserver. :(")
	return false

func _initialize_tcp_connection() -> bool:
	var got_port = await read_port_from_temp_file()
	if !got_port:
		print("Failed to get a port to microserver.")
		return false
	if assigned_port == -1:
		print("No valid port assigned. Cannot connect.")
		return false
	var connection_result = TCPClient.connect_to_host(SERVER_IP, assigned_port)
	if connection_result == OK:
		print("Connected to %s" % TCPClient.get_connected_host())
		# connect("tree_exiting", _exit_tree())
		return true
	print("An error occured: %s" % connection_result)
	return false

func read_port_from_temp_file() -> bool:
	var file = null
	var tried = 0
	
	while true:
		file = FileAccess.open(TEMP_FILE_PATH, FileAccess.READ)
		if file:
			assigned_port = file.get_as_text().strip_edges().to_int()
			file.close()

			# Delete file after reading
			DirAccess.remove_absolute(TEMP_FILE_PATH)
			print("Read port:", assigned_port, "and deleted temp file.")
			return true
		else:
			tried += 1
			if tried < 10:
				await get_tree().create_timer(0.30).timeout
				continue
			print("Port file not found!")
			return false
	return false

func initialize_server_connection(client_data):
	send_tcp_message(client_data, true)
	var tcp_t = Thread.new()
	tcp_t.start(continously_receive_messages)

func _exit_tree():
	# Make sure Python processed is killed (to death) when exiting godot
	send_tcp_message("CLEANUP", true)
	print("[GODOT] Python microserver has been slain.")


func continously_receive_messages() -> void:
	while true:
		TCPClient.poll()
		if TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			var available_bytes = TCPClient.get_available_bytes()
			if available_bytes > 0:
				var received_data = TCPClient.get_utf8_string(available_bytes)
				call_deferred("emit_received_data", received_data)
				# new_data_arrived.emit(received_data)

func emit_received_data(data):
	new_data_arrived.emit(data)

func send_tcp_message(message: String, system_message: bool = false) -> void:
	var wrap_message = {
			"auth": {
				"username": ClientData.username,
				"client_version": ClientData.version,
				"timestamp": Time.get_datetime_string_from_system(true, true),
				"session_token": "NOT_IMPLEMENTED_YET"
			}
		}
	if system_message:
		wrap_message["system_message"] = message
	else:
		wrap_message["client_input"] = message
	wrap_message = JSON.stringify(wrap_message)

	TCPClient.poll()
	# var debug = TCPClient.get_status()
	if TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		var data = wrap_message.to_utf8_buffer()
		TCPClient.put_data(data)
		# print(data)
		#TCPClient.put_utf8_string(message)
	else:
		print("Not connected. Message \"%s\" has not been sent." % message)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	pass
