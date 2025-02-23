extends RichTextLabel
	
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	TCPDialog.new_data_arrived.connect(draw_new_message)
	self.append_text(tr("Connecting...\n"))


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func draw_new_message(message: String) -> void:
	self.append_text(message)
