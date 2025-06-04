extends Node

# var microserver_process_id = null # storing process ID of microserver for cleanup
var TCPClient = StreamPeerTCP.new()
const SERVER_IP = "127.0.0.1"
const TEMP_FILE_PATH = "res://temp_port.txt"
signal new_data_arrived(data)
var tcp_t


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass

func run_python_microserver() -> bool:
	# Executing Python script
	var python_executable = ProjectSettings.globalize_path("res://")
	python_executable += "microserver/kafka_venv/bin/python3.13"
	# if OS.get_name() == "Windows":
	# 	python_executable = "kafka_env\\Scripts\\python.exe"
	var script_path = ProjectSettings.globalize_path("res://microserver/microserver.py")
	
	# Run the script
	var microserver_process = OS.execute_with_pipe(python_executable, [script_path])
	if not microserver_process:
		print("Failed to create microserver process.")
		return false
	var m_stdio = microserver_process['stdio']
	print("Python microserver started successfully. Process: %s" % microserver_process['pid'])
	var connected = await _initialize_tcp_connection(m_stdio)
	if connected:
		return true
	print("Failed to start Python microserver. :(")
	return false

func _initialize_tcp_connection(m_stdio) -> bool:
	var port = await wait_for_port_from_pipe(m_stdio)
	if !port:
		print("Failed to get a port to microserver.")
		return false
	if port == -1:
		print("No valid port assigned. Cannot connect.")
		return false
	m_stdio.close()
	var connection_result = TCPClient.connect_to_host(SERVER_IP, port)
	if connection_result == OK:
		print("Connected to %s" % TCPClient.get_connected_host())
		# connect("tree_exiting", _exit_tree())
		return true
	print("An error occured: %s" % connection_result)
	return false

func wait_for_port_from_pipe(m_stdio, timeout_sec: float = 10.0) -> int:
	var start_time = Time.get_ticks_msec()
	var port = -1
	
	while (Time.get_ticks_msec() - start_time) < timeout_sec * 1000:
		if m_stdio.get_length() > 0:
			var output = m_stdio.get_as_text()
			output = output.split("\n")
			for line in output:
				if "PORT_FOR_GODOT" in line:
					print("OUTPUT: " + line)
					var parts = line.split(" ")
					if parts.size() > 1:
						port = parts[1].to_int()
						print("STDIO got port: '%d'" % port)
						return port
				else:
					print(output)
		await get_tree().process_frame # Non-blocking wait
	
	print("Timeout reached, no port received.")
	return -1

func initialize_server_connection():
	send_tcp_message("", "REQUEST_SERVER_CONNECTION")
	tcp_t = Thread.new()
	tcp_t.start(continously_receive_messages)

func _exit_tree():
	# Make sure Python processed is killed (to death) when exiting godot
	send_tcp_message("", "CLEANUP")
	print("Python microserver has been kindly asked to kill itself.")

	# Stop the thread properly
	if tcp_t and tcp_t.is_started():
		tcp_t.wait_to_finish()
		print("TCP thread stopped correctly.")

func continously_receive_messages() -> void:
	while true:
		TCPClient.poll()
		if TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			var available_bytes = TCPClient.get_available_bytes()
			if available_bytes > 0:
				var received_data = TCPClient.get_utf8_string(available_bytes)
				var received_messages = received_data.split("|k-sep|") # mircoserver.py adds this separator to each message
				var dict_data_list = []
				for message in received_messages:
					if message != "":
						dict_data_list.append(JSON.parse_string(message))
				for message in dict_data_list:
					call_deferred("emit_received_data", message)

				# var dict_data: Array[Dictionary] = JSON.parse_string(received_messages)
				# call_deferred("emit_received_data", dict_data)
		else:
			break
		OS.delay_msec(10)

func emit_received_data(data):
	new_data_arrived.emit(data)

func send_tcp_message(user_input: String = "", system_message: String = "", message_content: String = "") -> void:
	var data_to_send: Dictionary
	data_to_send['metadata'] = {
			"source": "client",
			"username": ClientData.username,
			"client_version": ClientData.version,
			"timestamp": Time.get_datetime_string_from_system(true, true),
			"session_token": "NOT_IMPLEMENTED_YET"
		}
	data_to_send['payload'] = {
		"user_input": user_input,
		"system_message": system_message,
		"content": message_content,
	}
	var wrapped_message = JSON.stringify(data_to_send) + "\n"
	

	TCPClient.poll()
	if TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		var data = wrapped_message.to_utf8_buffer()
		TCPClient.put_data(data)
	else:
		print("Not connected. Message \"%s\" has not been sent." % wrapped_message)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	pass
