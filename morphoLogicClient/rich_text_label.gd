extends RichTextLabel
	
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	TCPDialog.new_data_arrived.connect(_draw_new_message_from_server)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func _draw_new_message_from_server(text: String) -> void:
	self.append_text(text)
