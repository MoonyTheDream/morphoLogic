extends RichTextLabel

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var print_debug_mode = ProjectSettings.get("morphoLogic/loogging/print_debug_messages_on_client")
	self.append_text(tr("Connecting...\n"))
	InputHandler.draw_message.connect(draw_new_message)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	pass
	
func draw_new_message(message: String) -> void:
	self.append_text(message)
