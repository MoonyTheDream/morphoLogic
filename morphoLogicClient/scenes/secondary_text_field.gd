extends RichTextLabel

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var print_debug_mode = ProjectSettings.get("morphoLogic/loogging/print_debug_messages_on_client")
	InputHandler.update_objects.connect(objects_message_update)



# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func objects_message_update(message: String) -> void:
	self.clear()
	self.append_text(message)
