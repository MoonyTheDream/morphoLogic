extends LineEdit

var inputList = []
@export var inputListNumber = 25
var cursor = 0

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	inputList.append("placeholder") # occupying the 0 position - will be needed later
	self.text_submitted.connect(_inputConfiguration)
	await get_tree().create_timer(0.30).timeout
	await self.request_username()
	self.text_submitted.connect(_send_to_tcp)

func _inputConfiguration(message: String):
	var buffor = message
	self.select_all()
	if inputList.size() < inputListNumber:
		inputList.append(buffor)
	else:
		inputList = inputList.pop_front()
		inputList.append(buffor)

func _up():
	# if self.inputList[0] == self.text:

	self.inputList[0] = self.text
	self.cursor = 25 % self.inputList.size()
	self.text = self.inputList[self.cursor]

func _down():
	self.inputList[0] = self.text
	self.cursor += 1
	self.text = self.inputList[self.cursor]

func _esc():
	if self.text != self.inputList[0]:
		self.text = self.inputList[0]
	else:
		self.text = ""
	self.cursor = 0

	


func request_username():
	var answer = ""
	var txt_f = get_node("%MainTextField")
	var entry_message = tr("Please provide your [color=teal]username[/color].\n")
	entry_message = "[pulse freq=1.0 color=#ffffff40 ease=-2.0]" + entry_message + "[/pulse]"
	
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
			txt_f.draw_new_message(tr("Welcome, [color=teal]{username}[/color]! Let me see if you are on the invite guest.\n").format({username = answer}))
			break


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("key_up"):
		_up()
	if Input.is_action_just_pressed("key_down"):
		_down()
	
func _send_to_tcp(text: String) -> void:
	text.strip_edges()
	TCPDialog.send_tcp_message(text)
