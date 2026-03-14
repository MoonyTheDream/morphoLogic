extends Control

## Mini-map drawn with Godot's _draw() API.
## Receives position data from InputHandler.update_minimap (Dictionary):
##   "_area": { "name": String }
##   "<id>":  { "name": String, "type": "character"|"object", "x": float, "y": float, "description": String }
## x/y are in metres, relative to the player (who is always at centre).

const MAP_RADIUS   := 6.0  # metres visible from centre to edge
const FONT_SIZE_SM := 10
const FONT_SIZE_XS := 9
const DOT_RADIUS_CHAR := 5.0
const DOT_RADIUS_OBJ  := 3.5

# Colour palette — matches the existing teal/green/gold theme
const COL_BG         := Color(0.04, 0.07, 0.09, 0.90)
const COL_BORDER     := Color(0.657, 0.9, 0.8676, 0.85)
const COL_RING       := Color(0.657, 0.9, 0.8676, 0.15)
const COL_CROSS      := Color(0.657, 0.9, 0.8676, 0.20)
const COL_PLAYER     := Color(0.657, 0.9, 0.8676, 1.0)
const COL_CHARACTER  := Color(0.678, 0.847, 0.0,   0.95)
const COL_OBJECT     := Color(1.0,   0.843, 0.0,   0.85)
const COL_AREA_LABEL := Color(0.657, 0.9, 0.8676, 0.60)

var _entities: Dictionary = {}
var _area_name: String = ""

# Populated each _draw() call — used for click hit-testing between redraws.
var _drawn_objects: Array = []  # [{name, description, draw_pos: Vector2, dot_r: float}]

var _tooltip: PanelContainer


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP  # allow _gui_input to receive clicks
	InputHandler.update_minimap.connect(_on_update_minimap)
	_create_tooltip()


func _create_tooltip() -> void:
	_tooltip = PanelContainer.new()
	_tooltip.visible = false
	_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var rtl := RichTextLabel.new()
	rtl.name = "RTL"
	rtl.bbcode_enabled = true
	rtl.fit_content = true
	rtl.scroll_active = false
	rtl.custom_minimum_size = Vector2(140.0, 0.0)
	_tooltip.add_child(rtl)
	add_child(_tooltip)


func _on_update_minimap(objects: Dictionary) -> void:
	_entities.clear()
	_area_name = objects.get("_area", {}).get("name", "")
	for key in objects:
		if key != "_area":
			_entities[key] = objects[key]
	queue_redraw()


func _draw() -> void:
	_drawn_objects.clear()

	var sz     := size
	var centre := sz * 0.5
	var map_r  := minf(sz.x, sz.y) * 0.5
	var ppm    := map_r / MAP_RADIUS  # pixels per metre
	var font   := ThemeDB.fallback_font

	# ── Background ──────────────────────────────────────────────────────── #
	draw_rect(Rect2(Vector2.ZERO, sz), COL_BG)

	# ── Range ring (5 m) ──────────────────────────────────────────────────── #
	draw_arc(centre, 5.0 * ppm, 0.0, TAU, 48, COL_RING, 1.0)

	# ── Cardinal crosshair ────────────────────────────────────────────────── #
	draw_line(Vector2(centre.x, 4.0),        Vector2(centre.x, sz.y - 4.0),   COL_CROSS, 1.0)
	draw_line(Vector2(4.0, centre.y),        Vector2(sz.x - 4.0, centre.y),   COL_CROSS, 1.0)

	# ── Entities ─────────────────────────────────────────────────────────── #
	for key in _entities:
		var e: Dictionary = _entities[key]
		var is_char: bool = e.get("type", "object") == "character"

		# World → screen: +x = east (screen right), +y = north (screen up = -y)
		var pos := centre + Vector2(e.get("x", 0.0) * ppm, -e.get("y", 0.0) * ppm)

		# Clamp entities that are right at the edge inside the ring
		var delta := pos - centre
		var clamp_r := map_r - 6.0
		if delta.length() > clamp_r:
			pos = centre + delta.normalized() * clamp_r

		var col := COL_CHARACTER if is_char else COL_OBJECT
		var dot_r := DOT_RADIUS_CHAR if is_char else DOT_RADIUS_OBJ

		draw_circle(pos, dot_r, col)
		draw_string(
			font,
			pos + Vector2(dot_r + 3.0, 4.0),
			e.get("name", "?"),
			HORIZONTAL_ALIGNMENT_LEFT,
			92.0, FONT_SIZE_SM,
			Color(col, 0.85)
		)

		# Store for click hit-testing
		_drawn_objects.append({
			"name": e.get("name", ""),
			"description": e.get("description", ""),
			"draw_pos": pos,
			"dot_r": dot_r,
		})

	# ── Player dot (on top of everything) ────────────────────────────────── #
	draw_circle(centre, 5.5, COL_PLAYER)
	draw_arc(centre, 8.5, 0.0, TAU, 32, Color(COL_PLAYER, 0.40), 1.5)

	# ── Area label ───────────────────────────────────────────────────────── #
	if _area_name:
		draw_string(
			font,
			Vector2(8.0, FONT_SIZE_SM + 4.0),
			_area_name,
			HORIZONTAL_ALIGNMENT_LEFT,
			sz.x - 16.0, FONT_SIZE_SM,
			COL_AREA_LABEL
		)

	# ── Scale bar (5 m) ──────────────────────────────────────────────────── #
	var bar_y  := sz.y - 9.0
	var bar_hw := 2.5 * ppm  # half-width = 2.5 m
	var bar_c  := Color(COL_BORDER, 0.55)
	draw_line(Vector2(centre.x - bar_hw, bar_y), Vector2(centre.x + bar_hw, bar_y), bar_c, 1.5)
	draw_line(Vector2(centre.x - bar_hw, bar_y - 4.0), Vector2(centre.x - bar_hw, bar_y + 4.0), bar_c, 1.5)
	draw_line(Vector2(centre.x + bar_hw, bar_y - 4.0), Vector2(centre.x + bar_hw, bar_y + 4.0), bar_c, 1.5)
	draw_string(
		font,
		Vector2(centre.x - 7.0, bar_y - 3.0),
		"5m",
		HORIZONTAL_ALIGNMENT_LEFT,
		20.0, FONT_SIZE_XS,
		Color(COL_BORDER, 0.50)
	)


# ── Click handling ────────────────────────────────────────────────────────── #

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		_handle_click(event.position)


func _handle_click(click_pos: Vector2) -> void:
	for obj in _drawn_objects:
		var dp: Vector2 = obj["draw_pos"]
		var dot_r: float = obj["dot_r"]
		if dp.distance_to(click_pos) <= dot_r + 4.0:
			_show_tooltip(obj["name"], obj["description"], click_pos)
			return
	_hide_tooltip()


func _show_tooltip(obj_name: String, description: String, at_pos: Vector2) -> void:
	var rtl: RichTextLabel = _tooltip.get_node("RTL")
	var desc_text := description if description != "" else "(no description)"
	rtl.text = "[b]%s[/b]\n%s" % [obj_name, desc_text]

	_tooltip.visible = true
	_tooltip.reset_size()

	# Position near click, clamped inside the minimap bounds
	var tsize := _tooltip.size
	var tx := at_pos.x + 12.0
	var ty := at_pos.y + 12.0
	if tx + tsize.x > size.x:
		tx = at_pos.x - tsize.x - 12.0
	if ty + tsize.y > size.y:
		ty = at_pos.y - tsize.y - 12.0
	_tooltip.position = Vector2(tx, ty)


func _hide_tooltip() -> void:
	_tooltip.visible = false
