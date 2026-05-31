"""MessageHandler — Kafka consumer loop + full protocol routing."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from morphologic_server.network.kafka import (
    KafkaConnection,
)
from morphologic_server.services.messages import ReceivedMessage

from confluent_kafka import Message

if TYPE_CHECKING:
    from morphologic_server.awakening import MorphoLogicHeart


# class ReceivedMessage:
#     """Parsed wrapper around a raw Kafka message."""

#     def __init__(self, raw_msg: Message):
#         self.topic = raw_msg.topic()
#         self.msg = json.loads(raw_msg.value().decode("utf-8"))
#         self.log.debug('Consumed from %s: "%s"', self.topic, self.msg)
#         self.type = self.msg["payload"]["type"]
#         self.user = self.msg["metadata"]["username"]


class MessageHandler:
    """Consumes Kafka messages and routes them to the correct handler."""

    def __init__(
        self, heart: MorphoLogicHeart, kafka: KafkaConnection, tg: asyncio.TaskGroup
    ):
        self.heart = heart
        self.log = self.heart.log.getChild("handler")
        self.kafka = kafka
        self.tg = tg
        self._stop = False
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
            for msg in msgs:
                if msg.error():
                    self.log.error("Kafka error: %s", msg.error().str())  # type: ignore # we know this is a Message, not an error
                    continue
                try:
                    received_msg = ReceivedMessage(msg)
                except Exception:
                    self.log.exception(
                        "Dropping unparseable message from %s", msg.topic()
                    )
                    continue
                self.log.debug(
                    'Consumed from %s: "%s"', received_msg.topic, received_msg.msg
                )
                self.tg.create_task(self._route(received_msg))

    async def _route(self, received: ReceivedMessage):
        """Route a message to the correct handler based on system_message."""

        try:
            if received.type == "system_message":
                match received.msg:
                    case "ITS'A_ME_MARIO":
                        self.log.debug(
                            'Received handshake initiation from "%s".', received.user
                        )
                        await self._handshake_init(received)
                    case "WALLS_HAVE_EARS_GOT_IT":
                        self.log.debug(
                            'Received handshake ack from "%s".', received.user
                        )
                        self._handshake_ack(received.user)
                    case "LOUD_AND_CLEAR":
                        self.log.debug(
                            'Received surroundings request from "%s".', received.user
                        )
                        await self._send_surroundings(received.user)
                    case _:
                        self.log.warning('Unknown system_message: "%s"', received.msg)

            if received.type == "user_input":
                await self._handle_user_input(received.user, received.msg)
        except Exception:
            self.log.exception(
                "Routing failed for %s (type: %s)", received.user, received.type
            )
            if received.user:
                self.kafka.send_data_to_user(
                    self.heart.settings.CLIENTS_GENERAL_TOPIC,
                    received.user,
                    direct_message="[color=tomato]Internal server error.[/color]\n",
                )
            # Duplicated for now, we weill add a plce that store which sessions listenes to whick topics.
            if received.user:
                self.kafka.send_data_to_user(
                    received.user,
                    received.user,
                    direct_message="[color=tomato]Internal server error.[/color]\n",
                )

    # ── Handshake ────────────────────────────────────────────────────────────

    async def _handshake_init(self, received: ReceivedMessage):
        """ITS'A_ME_MARIO → authenticate, create private topic, reply SHH_LET'S_TALK_IN_PRIVATE."""
        username = received.user
        if not username:
            self.log.warning("Received handshake initiation with empty username.")
            return

        password = received.content or ""
        character = await self.heart.memory.authenticate(username, password)
        if character is None:
            self.log.info('Auth failed for "%s"', username)
            self.kafka.send_data_to_user(
                self.heart.settings.CLIENTS_GENERAL_TOPIC,
                username,
                direct_message="[color=tomato]Authentication failed. Check your username and password.[/color]\n",
            )
            return

        self._sessions[username] = character
        self.log.info('"%s" authenticated as %s', username, character.name)

        created = await self.kafka.create_new_topics([username])
        dedicated_topic = created[0] if created else username
        if created:
            self.log.info('Created topic: "%s"', dedicated_topic)
        self.kafka.send_data_to_user(
            self.heart.settings.CLIENTS_GENERAL_TOPIC,
            username,
            server_message="SHH_LET'S_TALK_IN_PRIVATE",
            content=dedicated_topic,
        )

    def _handshake_ack(self, username: str):
        """WALLS_HAVE_EARS_GOT_IT → send CAN_YOU_HEAR_ME? to the user's private topic."""
        self.kafka.send_data_to_user(
            username,
            username,
            server_message="CAN_YOU_HEAR_ME?",
        )

    # ── Surroundings ─────────────────────────────────────────────────────────

    async def _send_surroundings(self, username: str):
        """LOUD_AND_CLEAR → query DB for surroundings, send SURROUNDINGS_DATA."""
        try:
            await self._do_send_surroundings(username)
        except Exception:
            self.log.exception("Error sending surroundings to %s", username)

    async def _do_send_surroundings(self, username: str):
        user = self._sessions.get(username)
        if user is None:
            return

        surroundings = await self.heart.memory.get_full_surroundings(user)
        game_objects = surroundings["game_objects"]
        characters = surroundings["characters"]
        area = surroundings["area"]
        terrain = surroundings["terrain"]
        area_name = area.name if area else "unknown"

        # Text description
        characters_str = "\n".join(
            [f"{c.name} ({c.id})" for c in characters if c.id != user.id]
        )
        objects_str = "\n".join(
            [f"{o.name} ({o.id})" for o in game_objects if o.holder_id is None]
        )
        text = (
            f'Character {user.name} is in area "{area_name}" \n'
            f" Characters around:\n {characters_str} \n\n"
            f" Objects around:\n {objects_str}"
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
            if obj.holder_id is not None:
                continue  # skip items stored inside holders
            objects_dict[str(obj.id)] = {
                "name": obj.name,
                "type": "object",
                "x": round(obj.location.x - player_x, 2),
                "y": round(obj.location.y - player_y, 2),
                "description": obj.description,
            }

        for t in terrain:
            objects_dict[f"t{t.id}"] = {
                "name": t.type.value,
                "type": "terrain",
                "x": round(t.location.x - player_x, 2),
                "y": round(t.location.y - player_y, 2),
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

        user = self._sessions.get(username)
        if user is None:
            return

        try:
            proximity = await self.heart.memory.get_objects_in_proximity(user)
            feedback = await handle_command(text, user, proximity)
            if feedback:
                self.kafka.send_data_to_user(
                    username, username, direct_message=feedback + "\n"
                )
            await self._send_surroundings(username)
        except Exception:
            self.log.exception("Error handling input from %s", username)
