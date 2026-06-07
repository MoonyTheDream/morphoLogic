extends Node

signal draw_message(msg)
signal update_objects(objects)
signal update_minimap(objects: Dictionary)
var message_processed := true

func _ready() -> void:
	while not Kafka.consumer.is_running():
		await get_tree().process_frame

	Kafka.new_data_arrived.connect(parse_message)


func parse_message(data: Dictionary) -> void:
	if data and data['metadata'].get("to_user", "") == ClientData.username:
		var server_message = data['payload'].get("server_message", "")
		# var system_message = data['payload'].get("system_message", "")
		var direct_message = data['payload'].get("direct_message", "")
		var objects = data['payload'].get("objects", null)
		var message_content = data['payload'].get("content", "")
		match server_message:
			# Handshake
			"SHH_LET'S_TALK_IN_PRIVATE":
				await Kafka.change_consumer_topic(message_content)
				Kafka.send_system_message("WALLS_HAVE_EARS_GOT_IT")
			"CAN_YOU_HEAR_ME?":
				var success_msg = tr("[color=green_yellow]Succsessfuly Established Server Connection.[/color]\n")
				draw_message.emit(success_msg)
				Kafka.send_system_message("LOUD_AND_CLEAR")
			"SURROUNDINGS_DATA":
				update_objects.emit(message_content)

			"":
				pass
			_:
				draw_message.emit(tr('[color=tomato]UKNOWN SERVER MESSAGE:[/color]"%s"! [color=tomato]REPORT ISSUE TO DEVS.[/color]\n' % server_message))
		# _:
		if direct_message:
			draw_message.emit(direct_message)

		if objects and typeof(objects) == TYPE_DICTIONARY:
			update_minimap.emit(objects)
	message_processed = true
		