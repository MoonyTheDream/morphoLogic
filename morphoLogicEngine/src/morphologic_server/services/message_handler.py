"""MessageHandler — Kafka consumer loop + full protocol routing."""

import asyncio
import json

from confluent_kafka import Message

from morphologic_server import logger
from morphologic_server.network.kafka import (
    KafkaConnection,
    CLIENTS_GENERAL_TOPIC as _CLIENTS_GENERAL_TOPIC,
)


class KafkaMessage:
    """Parsed wrapper around a raw Kafka message."""

    def __init__(self, raw_msg: Message):
        self.topic = raw_msg.topic()
        self.msg = json.loads(raw_msg.value().decode("utf-8"))
        logger.debug('Consumed from %s: "%s"', self.topic, self.msg)
        self.system_msg = self.msg["payload"].get("system_message", "")
        self.user_input = self.msg["payload"].get("user_input", "")
        self.sending_user = self.msg["metadata"]["username"]


class MessageHandler:
    """Consumes Kafka messages and routes them to the correct handler."""

    def __init__(self, kafka: KafkaConnection, tg: asyncio.TaskGroup):
        self.kafka = kafka
        self.tg = tg
        self._stop = False
        # Maps Kafka username → authenticated Character
        self._sessions: dict = {}

    async def start(self):
        """Start the consumer loop as a task."""
        self.tg.create_task(self._consume_loop())

    def stop(self):
        self._stop = True

    async def _consume_loop(self):
        """Continuously consume Kafka messages and dispatch them."""
        while not self._stop:
            msgs = await asyncio.to_thread(
                lambda: self.kafka.consumer.consume(num_messages=1, timeout=0.2)
            )
            if msgs:
                msg = msgs[0] if isinstance(msgs, list) else msgs
                if msg.error():
                    logger.warning("Kafka error: %s", msg.error().str())
                    continue
                parsed = KafkaMessage(msg)
                self.tg.create_task(self._route(parsed))

    async def _route(self, msg: KafkaMessage):
        """Route a message to the correct handler based on system_message."""
        match msg.system_msg:
            case "ITS'A_ME_MARIO":
                await self._handshake_init(msg.msg)
            case "WALLS_HAVE_EARS_GOT_IT":
                self._handshake_ack(msg.sending_user, msg.msg)
            case "LOUD_AND_CLEAR":
                await self._send_surroundings(msg.sending_user)
            case "":
                if msg.user_input:
                    await self._handle_user_input(msg.sending_user, msg.user_input)
            case _:
                logger.warning('Unknown system_message: "%s"', msg.system_msg)

    # ── Handshake ────────────────────────────────────────────────────────────

    async def _handshake_init(self, raw_msg: dict):
        """ITS'A_ME_MARIO → authenticate, create private topic, reply SHH_LET'S_TALK_IN_PRIVATE."""
        from morphologic_server.archetypes.base import authenticate

        username = raw_msg["metadata"].get("username", "")
        if not username:
            return

        password = raw_msg["payload"].get("content", "")
        character = await authenticate(username, password)
        if character is None:
            logger.info('Auth failed for "%s"', username)
            self.kafka.send_data_to_user(
                _CLIENTS_GENERAL_TOPIC,
                username,
                direct_message="[color=tomato]Authentication failed. Check your username and password.[/color]\n",
            )
            return

        self._sessions[username] = character
        logger.info('"%s" authenticated as %s', username, character.name)

        created = self.kafka.create_new_topics([username])
        dedicated_topic = created[0] if created else username
        if created:
            logger.info('Created topic: "%s"', dedicated_topic)
        self.kafka.send_data_to_user(
            _CLIENTS_GENERAL_TOPIC,
            username,
            server_message="SHH_LET'S_TALK_IN_PRIVATE",
            content=dedicated_topic,
        )

    def _handshake_ack(self, username: str, raw_msg: dict):
        """WALLS_HAVE_EARS_GOT_IT → send CAN_YOU_HEAR_ME? to the user's private topic."""
        self.kafka.send_data_to_user(
            username,
            username=raw_msg["metadata"]["username"],
            server_message="CAN_YOU_HEAR_ME?",
        )

    # ── Surroundings ─────────────────────────────────────────────────────────

    async def _send_surroundings(self, username: str):
        """LOUD_AND_CLEAR → query DB for surroundings, send SURROUNDINGS_DATA."""
        try:
            await self._do_send_surroundings(username)
        except Exception as e:
            logger.error("Error sending surroundings to %s: %s", username, e)

    async def _do_send_surroundings(self, username: str):
        from morphologic_server.utils.search import get_objects_in_proximity

        user = self._sessions.get(username)
        if user is None:
            return

        await user.refresh()

        proximity = await get_objects_in_proximity(user)
        area = await user.get_area_im_in()

        game_objects = proximity.get("game_objects", [])
        characters = proximity.get("characters", [])
        area_name = area.name if area else "unknown"

        # Text description
        characters_str = "\n".join(
            [f"{c.name} ({c.id})" for c in characters if c.id != user.id]
        )
        objects_str = "\n".join(
            [f"{o.name} ({o.id})" for o in game_objects if o.container_id is None]
        )
        text = (
            f'Character {user.name} is in area "{area_name}" \n'
            f' Characters around:\n {characters_str} \n\n'
            f' Objects around:\n {objects_str}'
        )

        # Minimap data — relative positions in metres
        player_x = user.location.x
        player_y = user.location.y
        objects_dict: dict = {"_area": {"name": area_name}}

        for char in characters:
            if char.id == user.id:
                continue  # player is always at centre
            objects_dict[str(char.id)] = {
                "name": char.name,
                "type": "character",
                "x": round(char.location.x - player_x, 2),
                "y": round(char.location.y - player_y, 2),
                "description": char.description,
            }

        for obj in game_objects:
            if obj.container_id is not None:
                continue  # skip items stored inside containers
            objects_dict[str(obj.id)] = {
                "name": obj.name,
                "type": "object",
                "x": round(obj.location.x - player_x, 2),
                "y": round(obj.location.y - player_y, 2),
                "description": obj.description,
            }

        self.kafka.send_data_to_user(
            topic=username,
            username=username,
            server_message="SURROUNDINGS_DATA",
            content=text,
            objects=objects_dict,
        )

    # ── User input ───────────────────────────────────────────────────────────

    async def _handle_user_input(self, username: str, text: str):
        """Parse and execute a typed command, then refresh surroundings."""
        from morphologic_server.game_logic.commands import handle_command
        from morphologic_server.utils.search import get_objects_in_proximity

        user = self._sessions.get(username)
        if user is None:
            return

        try:
            proximity = await get_objects_in_proximity(user)
            feedback = await handle_command(text, user, proximity)
            if feedback:
                self.kafka.send_data_to_user(
                    username, username, direct_message=feedback + "\n"
                )
            await self._send_surroundings(username)
        except Exception as e:
            logger.error("Error handling input from %s: %s", username, e)
