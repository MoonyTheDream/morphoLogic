extends RichTextLabel
	
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	TCPDialog.new_data_arrived.connect(parse_message)
	self.append_text(tr("Connecting...\n"))


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func draw_new_message(message: String) -> void:
	self.append_text(message)

func parse_message(data: String) -> void:
	var data_dict = JSON.parse_string(data)
	if data_dict.has("message"):
		var to_send = data_dict["message"]
		if data_dict["type"] == "error":
			to_send = "[color=tomato]" + to_send + "[/color]"
		if data_dict["type"] == "warning":
			to_send = "[color=gold]" + to_send + "[/color]"
		draw_new_message(to_send + "\n")
