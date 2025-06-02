extends Node

var TextOutput

signal draw_message(msg)
signal update_objects(objects)

func _ready() -> void:
	TCPDialog.new_data_arrived.connect(parse_message)

func parse_message(data: Dictionary) -> void:
	if data and data['metadata'].get("to_user", "") == ClientData.username:
		var server_message = data['payload'].get("server_message", "")
		var system_message = data['payload'].get("system_message", "")
		var direct_message = data['payload'].get("direct_message", "")
		var objects = data['payload'].get("objects", "")
		match system_message:
			"CONNECTED_TO_SERVER":
				draw_message.emit(tr("[color=yellow_green]Succsessfully connected to server.[/color]\n"))
			"SERVER_CONNECTION_RETRY":
				draw_message.emit(tr("[color=gold]Trouble Connecting to Server. Retrying.[/color]\n"))
			"SERVER_CONNECTION_FAILURE":
				draw_message.emit(tr("[color=tomato]Failure Connecting to Server.[/color]\n"))
			"":
				pass
			_:
				draw_message.emit(tr('[color=tomato]UKNOWN SYSTEM MESSAGE:[/color]"%s"! [color=tomato]REPORT ISSUE TO DEVS.[/color]\n' % system_message))
		var message_content = data['payload'].get("content", "")
		match server_message:
			# Handshake
			"CLIENT_TOPIC_HANDOFF":
				# var new_topic = message_content
				TCPDialog.send_tcp_message("", "MICROSERVER_SUBSCRIBE_TO", message_content)
				TCPDialog.send_tcp_message("", "PRODUCE_TO_TOPIC", ClientData.server_general_topic)
				TCPDialog.send_tcp_message("", "HANDSHAKE_GLOBAL_TOPIC")
				_wait_for_ack()
			"SURROUNDINGS_DATA":
				update_objects.emit(message_content)

			"":
				pass
			_:
				draw_message.emit(tr('[color=tomato]UKNOWN SERVER MESSAGE:[/color]"%s"! [color=tomato]REPORT ISSUE TO DEVS.[/color]\n' % server_message))
		# _:
		# 	draw_message.emit(tr("[color=tomato]UKNOWN MESSAGE TYPE! REPORT ISSUE TO DEVS.[/color]\n"))
		if direct_message:
			draw_message.emit(direct_message)

		if objects:
			pass
			# update_objects.emit(objects["game_objects"])
			# update_objects.emit(message_content)
		

func _wait_for_ack():
	TCPDialog.new_data_arrived.disconnect(parse_message)
	var server_answer = await TCPDialog.new_data_arrived
	if server_answer['payload'].get('server_message', '') == "ACK":
		TCPDialog.new_data_arrived.connect(parse_message)
		var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
		draw_message.emit(success_msg)
	else:
		draw_message.emit("KURDE ERROR, BO NIE BYŁO 'ACK', ALE NIE MAM NIC POZA TYM PRINTEM")
