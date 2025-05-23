extends RichTextLabel

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var print_debug_mode = ProjectSettings.get("morphoLogic/loogging/print_debug_messages_on_client")
	InputHandler.update_objects.connect(objects_message_update)

	var popup = $InfoPopup
	popup.borderless = true
	popup.popup_window = true
	popup.transient = true
	popup.close_requested.connect(popup.hide)
	popup.focus_exited.connect(popup.hide)

	self.meta_clicked.connect(_process_meta_clicked_object)
	



# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	#connect("TCPClient.new_data_arrived", _draw_new_message_from_server)
	pass
	
func objects_message_update(message: Dictionary) -> void:
	self.clear()
	self.append_text("[color=gainsboro]" + tr("Characters nearby:\n") + "[/color]")
	for character_id in message.get("characters", []).keys():
		var character = message["characters"][character_id]
		self.push_meta(character, META_UNDERLINE_ON_HOVER)
		self.append_text("[color=dark_sea_green]" + character.name + "[/color]\n")
		self.pop()
	self.append_text("\n")

	self.append_text("[color=gainsboro]" + tr("Objects nearby:\n") + "[/color]")
	for object_id in message.get("game_objects"):
		var object = message["game_objects"][object_id]
		if object.get("container_id", null) != null:
			continue
		self.push_meta(object, META_UNDERLINE_ON_HOVER)
		self.append_text("[color=rosy_brown]" + object.name + "\n")
		self.pop()

func _process_meta_clicked_object(meta):
	var popup = $InfoPopup
	var label = popup.get_node("InfoLabel")
	var description = meta.description if meta.description else ""
	label.text = meta.name + "\n" + description
	# popup.popup_centered()
	popup.popup()
	popup.position = get_viewport().get_mouse_position() + Vector2(30, 30)
	
