extends RichTextLabel

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var print_debug_mode = ProjectSettings.get("morphoLogic/loogging/print_debug_messages_on_client")
	self.append_text(tr("Connecting...\n"))
	var microserver_running = await TCPDialog.run_python_microserver()
	if not microserver_running:
		draw_new_message(tr("[color=tomato]Failed to launch Microserver![/color]\n"))
	elif print_debug_mode:
		draw_new_message(tr("[color=yellow_green]Microserver Running.[/color]\n"))
	InputHandler.draw_message.connect(draw_new_message)
	# TCPDialog.new_data_arrived.connect(parse_message)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func draw_new_message(message: String) -> void:
	self.append_text(message)
