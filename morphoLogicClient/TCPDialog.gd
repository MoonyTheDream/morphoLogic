extends Node
var TCPClient = StreamPeerTCP.new()
var is_tcp_connected = false
const SERVER_IP = "127.0.0.1"
const SERVER_PORT = 6164
signal new_data_arrived(data)

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	is_tcp_connected = connect_to_microserver()
	if  is_tcp_connected:
		print("Connected to microserver.")
	else:
		print("Failed to connect to microserver!")

func connect_to_microserver() -> bool:
	var connection_result = TCPClient.connect_to_host(SERVER_IP, SERVER_PORT)
	if connection_result == OK:
		return true
	else:
		print("An error occured: %s" % connection_result)
	return false

func send_tcp_message(message: String):
	TCPClient.poll()
	if is_tcp_connected and TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		var data = message.to_utf8_buffer()
		TCPClient.put_data(data)
		_ask_for_confirmation()
		print(data)
		#TCPClient.put_utf8_string(message)
	else:
		print("Not connected. Message \"%s\" has not been sent." % message)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	TCPClient.poll()
	if is_tcp_connected and TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		var available_bytes = TCPClient.get_available_bytes()
		if available_bytes > 0:
			var received_data = TCPClient.get_utf8_string(available_bytes)
			if received_data != "RECEIVED":
				new_data_arrived.emit(received_data)
		else:
			send_tcp_message("CONSUME")
			
			
			
func _ask_for_confirmation() -> bool:
	while true:
		if is_tcp_connected and TCPClient.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			var available_bytes = TCPClient.get_available_bytes()
			if available_bytes > 0:
				var received_data = TCPClient.get_utf8_string(available_bytes)
				if received_data == "RECEIVED":
					return true
			else: continue
	return false
