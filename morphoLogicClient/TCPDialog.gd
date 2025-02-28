extends Node

# var microserver_process_id = null # storing process ID of microserver for cleanup
var TCPClient = StreamPeerTCP.new()
var is_tcp_connected = false
const SERVER_IP = "127.0.0.1"
const TEMP_FILE_PATH = "res://temp_port.txt"
var assigned_port = -1
var microserver_process = -1
# const SERVER_PORT = 6164
signal new_data_arrived(data)
var root

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	run_python_microserver()
	root = get_tree().root

func run_python_microserver():
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
	else:
		print("Failed to start Python microserver. :(")

func read_port_from_temp_file():
	var file = FileAccess.open(TEMP_FILE_PATH, FileAccess.READ)

	if file:
		assigned_port = file.get_as_text().strip_edges().to_int()
		file.close()

		# Delete file after reading
		DirAccess.remove_absolute(TEMP_FILE_PATH)
		print("Read port:", assigned_port, "and deleted temp file.")
	else:
		print("Port file not found!")

func initialize_connection(client_data: String) -> void:
	var txt_f = root.get_node("BasicView/MainTextControls/MainTextField")
	read_port_from_temp_file()
	if assigned_port == -1:
		txt_f.draw_new_message(tr("No valid port assigned. Cannot connect."))
	is_tcp_connected = connect_to_microserver()
	var message = ""
	if  is_tcp_connected:
		message = "Connected to microserver."
		print(message)

	else:
		message = "Failed to connect to microserver!"
		print(message)
		connect("tree_exiting", _exit_tree())
		return

	# txt_f.draw_new_message(message)
	send_tcp_message(client_data)
	var tcp_t = Thread.new()
	tcp_t.start(continously_receive_messages)

func _exit_tree():
	# Make sure Python processed is killed (to death) when exiting godot
	send_tcp_message("CLEANUP")
	print("[GODOT] Python microserver has been slain.")

func connect_to_microserver() -> bool:
	var connection_result = TCPClient.connect_to_host(SERVER_IP, assigned_port)
	if connection_result == OK:
		print("Connected to %s" % TCPClient.get_connected_host())
		return true
	else:
		print("An error occured: %s" % connection_result)
	return false

func continously_receive_messages() -> void:
	while true:
		TCPClient.poll()
		if is_tcp_connected and TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			var available_bytes = TCPClient.get_available_bytes()
			if available_bytes > 0:
				var received_data = TCPClient.get_utf8_string(available_bytes)
				call_deferred("emit_received_data", received_data)
				# new_data_arrived.emit(received_data)

func emit_received_data(data):
	new_data_arrived.emit(data)

func send_tcp_message(message: String) -> void:
	TCPClient.poll()
	# var debug = TCPClient.get_status()
	if is_tcp_connected and TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		var data = message.to_utf8_buffer()
		TCPClient.put_data(data)
		# print(data)
		#TCPClient.put_utf8_string(message)
	else:
		print("Not connected. Message \"%s\" has not been sent." % message)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	pass
