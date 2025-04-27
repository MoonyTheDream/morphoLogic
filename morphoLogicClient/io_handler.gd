extends Node

var TextOutput
var root

signal draw_message(msg)

func _ready() -> void:
	root = get_tree().root
	TCPDialog.new_data_arrived.connect(parse_message)
	# await get_tree().process_frame
	# print(get_tree().root.find_child(("MainTextControls")))
	# TextOutput = get_node("../MainTextControls/MainTextField")

func parse_message(data: Dictionary) -> void:

	if data and data['metadata'].get("to_user", "") == ClientData.username:

		# Handling System Messages
		var system_message = data['payload']['type'] == "system_message"
		# var system_message = data.get("system_message", "")
		var message_type = data['payload']['type']
		var message_content = data['payload']['content']
		# if system_message:
		match message_type:
			"system_message":
				match message_content:
					"CONNECTED_TO_SERVER":
						draw_message.emit(tr("[color=yellow_green]Succsessfully connected to server.[/color]\n"))
					"SERVER_CONNECTION_RETRY":
						draw_message.emit(tr("[color=gold]Trouble Connecting to Server. Retrying.[/color]\n"))
					"SERVER_CONNECTION_FAILURE":
						draw_message.emit(tr("[color=tomato]Failure Connecting to Server.[/color]\n"))
					_:
						draw_message.emit(tr("[color=tomato]UKNOWN SYSTEM MESSAGE! REPORT ISSUE TO DEVS.[/color]\n"))
			# Handshake
			"client_topic_handoff":
				var new_topic = data['client_topic_handoff']
				TCPDialog.send_tcp_message("microserver_subscribe_to", message_content)
				TCPDialog.send_tcp_message("produce_to_topic", ClientData.server_general_topic)
				TCPDialog.send_tcp_message("system_message", "HANDSHAKE_GLOBAL_TOPIC")
				_wait_for_ack()
			_:
				draw_message.emit(tr("[color=tomato]UKNOWN MESSAGE TYPE! REPORT ISSUE TO DEVS.[/color]\n"))
			

func _wait_for_ack():
	TCPDialog.new_data_arrived.disconnect(parse_message)
	var server_answer = await TCPDialog.new_data_arrived
	if server_answer['payload']['type'] == "system_message" and server_answer['payload']['content'] == "ACK":
		TCPDialog.new_data_arrived.connect(parse_message)
		var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
		draw_message.emit(success_msg)
	else:
		draw_message.emit("KURDE ERROR, BO NIE BYŁO 'ACK', ALE NIE MAM NIC POZA TYM PRINTEM")
