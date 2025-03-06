extends RichTextLabel
	
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	self.append_text(tr("Connecting...\n"))
	var microserver_running = await TCPDialog.run_python_microserver()
	if microserver_running:
		draw_new_message(tr("[color=yellow_green]Microserver Running.[/color]\n"))
	else:
		draw_new_message(tr("[color=tomato]Failed to launch Microserver![/color]\n"))
	TCPDialog.new_data_arrived.connect(parse_message)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func draw_new_message(message: String) -> void:
	self.append_text(message)

func parse_message(data: String) -> void:
	var data_dict = JSON.parse_string(data)
	if data_dict:
		if data_dict.has("direct_messages") and data_dict["direct_messages"].size()>0:
			var messages = data_dict["direct_messages"]
			for m in messages:
				draw_new_message(m + "\n")

		var system_message = data_dict.get("system_message", "")
		if system_message:
			match system_message:
				"CONNECTED_TO_SERVER":
					draw_new_message(tr("[color=yellow_green]Succsessfully connected to server.[/color]\n"))
				"SERVER_CONNECTION_RETRY":
					draw_new_message(tr("[color=gold]Trouble Connecting to Server. Retrying.[/color]\n"))
				"SERVER_CONNECTION_FAILURE":
					draw_new_message(tr("[color=tomato]Failure Connecting to Server.[/color]\n"))
				_:
					draw_new_message(tr("[color=tomato]UKNOWN SYSTEM MESSAGE! REPORT ISSUE TO DEVS.[/color]\n"))
