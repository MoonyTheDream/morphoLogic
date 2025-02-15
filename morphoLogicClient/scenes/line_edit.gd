extends LineEdit


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	self.text_submitted.connect(_send_to_tcp)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass
	
func _send_to_tcp(text: String) -> void:
	text.strip_edges()
	TCPDialog.send_tcp_message(text)
