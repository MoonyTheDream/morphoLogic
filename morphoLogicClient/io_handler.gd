extends Node

# var TextOutput

signal draw_message(msg)
signal update_objects(objects)
var message_processed := true

func _ready() -> void:
	while not Kafka.consumer.is_running():
		await get_tree().process_frame

	# Kafka.send_message("", "YO_ANYBODY_HOME?")
	
	# var kafka_message: Dictionary

	# while (true):
		
	# 	kafka_message = await Kafka.new_data_arrived

	# 	if kafka_message['payload'].get("server_message", "") == "UP_AND_RUNNING":
	# 		draw_message.emit(tr("[color=green_yellow]Server is up and running. Singing probably too.[/color]\n"))
	# 		break
		
	Kafka.new_data_arrived.connect(parse_message)

# func is_server_alive() -> bool:

func parse_message(data: Dictionary) -> void:
	if data and data['metadata'].get("to_user", "") == ClientData.username:
		var server_message = data['payload'].get("server_message", "")
		# var system_message = data['payload'].get("system_message", "")
		var direct_message = data['payload'].get("direct_message", "")
		var objects = data['payload'].get("objects", "")
		var message_content = data['payload'].get("content", "")
		match server_message:
			# Handshake
			"SHH_LET'S_TALK_IN_PRIVATE":
				# var new_topic = message_content
				# TCPDialog.send_tcp_message("", "MICROSERVER_SUBSCRIBE_TO", message_content)
				await Kafka.change_consumer_topic(message_content)

				# TCPDialog.send_tcp_message("", "PRODUCE_TO_TOPIC", ClientData.server_general_topic)
				# Kafka.set_producer_topic(ClientData.server_general_topic)
				Kafka.send_message("", "WALLS_HAVE_EARS_GOT_IT")
				# _wait_for_ack()
			"CAN_YOU_HEAR_ME?":
				var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
				draw_message.emit(success_msg)
				Kafka.send_message("", "LOUD_AND_CLEAR")
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
	message_processed = true
		

# func _wait_for_ack() -> void:
# 	Kafka.new_data_arrived.disconnect(parse_message)
# 	var server_answer = await Kafka.new_data_arrived
# 	if server_answer['payload'].get('server_message', '') == "ACK":
# 		var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
# 		draw_message.emit(success_msg)
# 	else:
# 		draw_message.emit("KURDE ERROR, BO NIE BYŁO 'ACK', ALE NIE MAM NIC POZA TYM PRINTEM")
# 	message_processed = true
# 	Kafka.new_data_arrived.connect(parse_message)

