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
		# var system_message = data['payload']['type'] == "system_message"
		# var system_message = data.get("system_message", "")
		# var payload = data['payload']
		var server_message = data['payload'].get("server_message", "")
		var direct_message = data['payload'].get("direct_message", "")
		# if system_message:
		match server_message:
			"CONNECTED_TO_SERVER":
				draw_message.emit(tr("[color=yellow_green]Succsessfully connected to server.[/color]\n"))
			"SERVER_CONNECTION_RETRY":
				draw_message.emit(tr("[color=gold]Trouble Connecting to Server. Retrying.[/color]\n"))
			"SERVER_CONNECTION_FAILURE":
				draw_message.emit(tr("[color=tomato]Failure Connecting to Server.[/color]\n"))
			# Handshake
			"client_topic_handoff":
				var message_content = data['payload']["content"]
				# var new_topic = message_content
				TCPDialog.send_tcp_message("", "microserver_subscribe_to", message_content)
				TCPDialog.send_tcp_message("", "produce_to_topic", ClientData.server_general_topic)
				TCPDialog.send_tcp_message("", "HANDSHAKE_GLOBAL_TOPIC")
				_wait_for_ack()
			"":
				pass
			_:
				draw_message.emit(tr("[color=tomato]UKNOWN SERVER MESSAGE! REPORT ISSUE TO DEVS.[/color]\n"))
		# _:
		# 	draw_message.emit(tr("[color=tomato]UKNOWN MESSAGE TYPE! REPORT ISSUE TO DEVS.[/color]\n"))
		if direct_message:
			draw_message.emit(direct_message)

func _wait_for_ack():
	TCPDialog.new_data_arrived.disconnect(parse_message)
	var server_answer = await TCPDialog.new_data_arrived
	if server_answer['payload'].get('server_message', '') == "ACK":
		TCPDialog.new_data_arrived.connect(parse_message)
		var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
		draw_message.emit(success_msg)
	else:
		draw_message.emit("KURDE ERROR, BO NIE BYŁO 'ACK', ALE NIE MAM NIC POZA TYM PRINTEM")
