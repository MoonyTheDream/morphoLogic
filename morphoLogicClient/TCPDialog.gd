extends Node

# var microserver_process_id = null # storing process ID of microserver for cleanup
var TCPClient = StreamPeerTCP.new()
const SERVER_IP = "127.0.0.1"
# signal new_data_arrived(data)
var tcp_t


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass

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
