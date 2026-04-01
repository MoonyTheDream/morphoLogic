"""Seed the database with test objects spread around the spawn point.

Run with:  morphologic seed
or:        python -m morphologic_server.scripts.seed

Existing data is left intact — objects/areas are only created if they don't
already exist (checked by name).  Characters are skipped if the named account
does not exist yet.

All coordinates are in SRID 3857 (Web Mercator, metres).
The default spawn is (0, 0, 0); offsets below are in metres relative to it.
"""

import asyncio

from shapely.geometry import Point

from morphologic_server.db.models import (
    Base,
    Character,
    GameObject,
    TerrainType,
)
from morphologic_server import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pt(x: float, y: float, z: float = 0.0) -> Point:
    return Point(x, y, z)


async def _ensure_object(memory, name: str, description: str, location: Point, container=None):
    """Create a game object only if one with this name doesn't already exist."""
    existing = await memory.search(name, GameObject)
    if existing:
        logger.info("Seed: object '%s' already exists — skipping.", name)
        return existing
    obj = await memory.create_game_object(
        name=name,
        description=description,
        location=location,
    )
    logger.info("Seed: created object '%s'.", name)
    return obj


# ---------------------------------------------------------------------------
# Main seed
# ---------------------------------------------------------------------------

async def seed():
    from morphologic_server.db.engine import create_sessionmaker
    from morphologic_server.db.memory import Memory
    from morphologic_server.db.models import Area
    from morphologic_server.config import ServerSettings

    settings = ServerSettings()
    sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
    Base._sessionmaker = sessionmaker
    memory = Memory(sessionmaker)

    logger.info("Seeding database…")

    # ── Areas ────────────────────────────────────────────────────────────── #
    existing_areas = await memory.simple_query("Mały, wierzbowy lasek.", "name", Area)
    if not existing_areas:
        await memory.create_area(
            polygon=[(-10, -10), (10, -10), (10, 10), (-10, 10), (-10, -10)],
            name="Mały, wierzbowy lasek.",
            description="Cichy lasek nad rzeką, gdzie rosną stare wierzby.",
            priority=1,
        )
        logger.info("Seed: created area 'Mały, wierzbowy lasek.'")
    else:
        logger.info("Seed: area 'Mały, wierzbowy lasek.' already exists — skipping.")

    existing_polana = await memory.simple_query("Polana", "name", Area)
    if not existing_polana:
        await memory.create_area(
            polygon=[(5, 5), (20, 5), (20, 20), (5, 20), (5, 5)],
            name="Polana",
            description="Otwarta polana z miękką trawą i dzikim kwieciem.",
            priority=1,
        )
        logger.info("Seed: created area 'Polana'")
    else:
        logger.info("Seed: area 'Polana' already exists — skipping.")

    # ── Terrain around spawn ──────────────────────────────────────────────── #
    terrain_tiles = [
        # (x, y, z, type)  — spread around spawn within visibility radius
        ( 0,  0, 0, TerrainType.SOIL),
        ( 3,  3, 0, TerrainType.SOIL),
        (-3,  3, 0, TerrainType.SOIL),
        ( 3, -3, 0, TerrainType.SOIL),
        (-3, -3, 0, TerrainType.SOIL),
        ( 6,  0, 0, TerrainType.SAND),
        (-6,  0, 0, TerrainType.SAND),
        ( 0,  6, 0, TerrainType.ROCK),
        ( 0, -6, 0, TerrainType.ROCK),
        ( 8,  4, 0, TerrainType.WATER),
        (-5,  7, 0, TerrainType.WATER),
        ( 5, -7, 0, TerrainType.SAND),
    ]
    for x, y, z, t_type in terrain_tiles:
        await memory.create_or_edit_terrain(x, y, z, t_type)
    logger.info("Seed: ensured %d terrain tiles.", len(terrain_tiles))

    # ── Game objects spread around spawn ─────────────────────────────────── #
    # Top-level objects (no container)
    await _ensure_object(memory, "Stary dąb",       "Rozłożysty dąb z wyraźną dziuplą.",      _pt( 3,  4))
    await _ensure_object(memory, "Kamień graniczny", "Omszały kamień z wyrytym znakiem.",      _pt(-4,  2))
    await _ensure_object(memory, "Wiadro",          "Drewniane wiadro bez ucha.",              _pt( 1, -5))
    await _ensure_object(memory, "Ognisko",         "Dopalające się ognisko.",                 _pt(-2, -2))
    await _ensure_object(memory, "Skrzynia",        "Ciężka drewniana skrzynia.",              _pt( 7,  1))
    await _ensure_object(memory, "Pędzel Moony'ego","Cieniutki pędzel z czarną rączką.",       _pt(-1, -3))

    # Coins placed individually at different spots
    coin_pouch = await _ensure_object(
        memory, "Coin Pouch", "Skórzana sakiewka z monetami.", _pt(3, -1)
    )
    await _ensure_object(memory, "Copper Coin", "Miedziana moneta.",  _pt(1,  0))
    await _ensure_object(memory, "Silver Coin", "Srebrna moneta.",    _pt(-2, 1))
    await _ensure_object(memory, "Gold Coin",   "Złota moneta.",      _pt(4, -2))

    # ── Extra NPC character ───────────────────────────────────────────────── #
    # Only create if an account named "Another" exists; skip otherwise.
    another_account = await memory.find_account("Another")
    if another_account:
        existing_char = await memory.search("AnotherCharacter", Character)
        if not existing_char:
            await memory.create_character_and_soul(
                account_id=another_account.id,
                name="AnotherCharacter",
                description="A wandering soul.",
                location=None,  # will use DEFAULT_SPAWN_LOCATION; move below
            )
            # Move them to (2, 3) so they're visible but distinct
            char = await memory.search("AnotherCharacter", Character)
            if char:
                char.location = (2.0, 3.0, 0.0)
                await char.save()
                logger.info("Seed: created and positioned 'AnotherCharacter'.")
        else:
            logger.info("Seed: 'AnotherCharacter' already exists — skipping.")
    else:
        logger.info(
            "Seed: no account named 'Another' found — skipping AnotherCharacter. "
            "Create the account first with 'morphologic shell' then re-run seed."
        )

    logger.info("Seeding complete.")


def main():
    asyncio.run(seed())


if __name__ == "__main__":
    main()
