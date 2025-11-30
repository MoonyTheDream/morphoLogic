extends Node

signal new_data_arrived(data)

@onready var producer = KafkaProducer.new()
@onready var consumer := KafkaConsumer.new()
# var _is_kafka_ready := false


func _ready() -> void:
	# Prepare both Kafka Producer and Consumer
	consumer.set_bootstrap_servers(ClientData.bootstrap_server)
	consumer.set_topic(ClientData.clients_general_topic)
	print("Starting Kafka Consumer on topic: '%s'" % ClientData.clients_general_topic)
	consumer.start()
	# await consumer.consumer_ready

	producer.set_bootstrap_servers(ClientData.bootstrap_server)
	producer.set_topic(ClientData.server_general_topic)

func _is_it_for_me_really(data: Dictionary) -> bool:
	# Check if the message is for this client
	return data['metadata'].get("to_user", "") == ClientData.username or data['payload'].get("server_message", "") == "UP_AND_RUNNING"

func _process(_delta: float) -> void:
	# if consumer.has_message():
	if Kafka.consumer.is_running() and InputHandler.message_processed == true:
		var message = consumer.get_message()
		if message:
			print("Received message: %s" % message)

			if message != "":
				var data = JSON.parse_string(message)
				if data and _is_it_for_me_really(data):
					# data['metadata']['to_user'] = ClientData.username # Ensure the message is directed
					InputHandler.message_processed = false
					new_data_arrived.emit(data)
				else:
					print("Failed to parse message: %s" % message)

			# var dict_data: Array[Dictionary] = JSON.parse_string(received_messages)
			# call_deferred("emit_received_data", dict_data)


func send_message(user_input: String = "", system_message: String = "", message_content: String = "") -> void:
	# if not _is_kafka_ready:
		# await consumer.consumer_ready
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
	

	# var kafka_message = wrapped_message.to_utf8_buffer()
	print("Sending message: %s" % wrapped_message)
	producer.send_message(wrapped_message)

func set_producer_topic(topic: String) -> void:
	producer.set_topic(topic)

func change_consumer_topic(topic: String) -> void:
	# _is_kafka_ready = false
	# consumer.stop()
	# consumer.set_topic(topic)
	# consumer.start()
	# await consumer.consumer_ready
	consumer.change_topic(topic)
	await consumer.consumer_ready # Wait for Kafka consumer to be ready

	# _is_kafka_ready = true

func initialize_server_connection() -> void:
	# This method can be used to send an initial handshake message
	self.send_message("", "ITS'A_ME_MARIO")
