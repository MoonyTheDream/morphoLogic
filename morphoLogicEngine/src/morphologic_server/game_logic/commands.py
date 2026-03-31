"""Game command parser — interprets free-text input from players."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from morphologic_server.db.models import Character

_MOVE_RE = re.compile(r"^(?:go|run|walk|move)\s+to\s+(.+)$", re.IGNORECASE)


async def handle_command(text: str, user: "Character", proximity: dict) -> str | None:
    """Parse a text command and mutate game state.

    Returns a feedback string for the player, or None if the command was not recognised.
    """
    m = _MOVE_RE.match(text.strip())
    if m:
        return await _move_to(m.group(1).strip(), user, proximity)
    return None


async def _move_to(target_name: str, user: "Character", proximity: dict) -> str:
    all_entities = proximity.get("game_objects", []) + proximity.get("characters", [])
    target = next(
        (e for e in all_entities if e.name.lower() == target_name.lower()), None
    )
    if target is None:
        return f'[color=tomato]Can\'t find "{target_name}" nearby.[/color]'
    user.location = (target.location.x, target.location.y, target.location.z)
    await user.save()
    return f'You move to {target.name}.'
