extends LineEdit

var inputList = [] # A list of sent messages
@export var inputListNumber = 25 # Max number of remembered sent messages
var cursor = 0 # Current position in inputListNumber

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	grab_focus()
	inputList.append("") # occupying the 0 position, so any other will take subsequent place
	self.text_submitted.connect(_inputHandler) # later it will be part of _send_to_tcp
	await get_tree().create_timer(0.30).timeout # Better UX and time for other services to start
	
	var username = await self.request_username()
	# Username is needed in each message to Kafka
	ClientData.username = username
	# A method that will send the first message to Kafka with handshake
	TCPDialog.initialize_server_connection()

	self.text_submitted.disconnect(_inputHandler)
	self.text_submitted.connect(_send_to_tcp)

func _inputHandler(message: String, strip = true) -> void:
	self.cursor = 0
	if strip:
		message.strip_edges()
	self.select_all()
	for s in inputList:							
		if message == s:
			return
	_append(message)
	
func _append(message: String) -> void:
	if inputList.size() < inputListNumber:
		inputList.append(message)
	else:
		inputList.pop_front()
		inputList.append(message)

func _send_to_tcp(content: String) -> void:
	_inputHandler(content)
	TCPDialog.send_tcp_message(content)
	
func _up():
	_if_at_zero(true)
	self.cursor = (self.cursor - 1) % self.inputList.size()
	if self.cursor == -1:
		self.cursor = self.inputList.size() - 1
	self.text = self.inputList[self.cursor]
	self.select_all()

func _down():
	_if_at_zero()
	self.cursor = (self.cursor + 1) % self.inputList.size()
	self.text = self.inputList[self.cursor]
	self.select_all()

func _if_at_zero(is_up=false):
	if self.cursor == 0:
		if inputList[inputList.size()-1] != text:
			self.inputList[0] = self.text
		elif is_up:
			cursor -=1

func _esc():
	if cursor != 0:
		text = inputList[0]
		cursor = 0
	else:
		self.text = ""
	grab_focus()
	select_all()

func _enter_key():
	if not has_focus():
		grab_focus()
		select_all()

func request_username() -> String:
	var answer = ""
	var txt_f = get_node("%MainTextField")
	var entry_message = tr("Please provide your [color=medium_turquoise]username[/color].\n")
	entry_message = "[pulse freq=0.5 color=#ffffff60 ease=2.0]" + entry_message + "[/pulse]"
	
	txt_f.draw_new_message(entry_message)

	while true:
		answer = await self.text_submitted
		if answer == "":
			txt_f.draw_new_message(entry_message)
			continue
		else:
			answer = answer.strip_edges()
			if " " in answer:
				txt_f.draw_new_message(tr("Please don't use any spaces in your username.\n"))
				continue
			if not is_valid_username(answer):
				txt_f.draw_new_message(tr('You can only use letters, digits and "_", "-".\n'))
				continue
			txt_f.draw_new_message(tr("Welcome, [color=medium_turquoise]{username}[/color]! Let me see if you are on the invite guest.\n").format({username = answer}))
			return answer
	return ""

func is_valid_username(username_text: String) -> bool:
	var regex = RegEx.new()
	regex.compile("^[a-zA-Z0-9_-]+$")  # Allows only letters, numbers, _ and -
	return regex.search(username_text) != null

# func _client_metadata_json(username: String) -> String:
# 	var data = {
# 		"username": username,
# 		"client_version": ClientData.version
# 	}
# 	return JSON.stringify(data)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	if Input.is_action_just_pressed("key_up"):
		_up()
	if Input.is_action_just_pressed("key_down"):
		_down()
	if Input.is_action_just_pressed("enter_key"):
		_enter_key()
	if Input.is_action_just_pressed("key_esc"):
		_esc()
	
