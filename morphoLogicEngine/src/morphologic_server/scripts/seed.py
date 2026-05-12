"""Seed the database with test objects, NPCs and player characters.

Run with:  morphologic seed
or:        morphologic seed --fresh   (wipe everything first)
or:        python -m morphologic_server.scripts.seed

Default behaviour: existing rows are left intact. Names that already exist are
skipped, so the script is idempotent. With --fresh, all Characters,
CharacterSouls, GameObjects, Accounts, Areas and Terrain are deleted before
seeding — useful for putting the world back to a known initial state.

All coordinates are in SRID 3857 (Web Mercator, metres).
The default spawn is (0, 0, 0); offsets below are in metres relative to it.

Convention: user-visible text (object/character names, descriptions, areas) is
in Polish. `attributes` dicts use English keys, as they're meant to be
consumed by code before reaching players.
"""

import asyncio

from shapely.geometry import Point
from sqlalchemy import delete

from morphologic_server.db.models import (
    Account,
    Area,
    Base,
    Character,
    CharacterSoul,
    GameObject,
    Terrain,
    TerrainType,
)
from morphologic_server import logger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pt(x: float, y: float, z: float = 0.0) -> Point:
    return Point(x, y, z)


async def _ensure_object(
    memory,
    name: str,
    description: str,
    location: Point | None = None,
    holder: GameObject | None = None,
    *,
    attributes: dict | None = None,
):
    """Create a game object only if one with this name doesn't already exist.

    If `holder` is given and the object is created, its location is
    overridden to match the holder's — nested items live where their
    holder lives.
    """
    existing = await memory.search(name, GameObject)
    if existing:
        logger.info("Seed: object '%s' already exists — skipping.", name)
        return existing

    if holder is not None:
        location = _pt(*holder.location.coords[0])
    elif location is None:
        raise ValueError(f"Seed: object '{name}' needs a location or a holder.")

    obj = await memory.create_game_object(
        name=name,
        description=description,
        location=location,
        holder=holder,
        attributes=attributes,
    )
    where = f" w '{holder.name}'" if holder is not None else ""
    logger.info("Seed: created object '%s'%s.", name, where)
    return obj


async def _ensure_account(
    memory, username: str, email: str, permission_level: int = 2
) -> Account:
    """Find an account by username, or create it."""
    account = await memory.find_account(username)
    if account:
        logger.info("Seed: account '%s' already exists — skipping.", username)
        return account
    account = await memory.create_account(
        username=username, email=email, permission_level=permission_level
    )
    logger.info("Seed: created account '%s'.", username)
    return account


async def _ensure_player_character(
    memory,
    account: Account,
    name: str,
    description: str,
    position: tuple[float, float, float],
    *,
    attributes: dict | None = None,
    permission_level: int = 2,
    puppet_self: bool = True,
) -> tuple[Character, CharacterSoul | None]:
    """Find a character by name, or create one bound to `account`.

    If freshly created and `puppet_self` is True, the character's soul is
    set to puppet the character itself (simulates a logged-in player).

    Returns (character, soul). `soul` is None when the character already
    existed (we don't re-fetch it — re-run with --fresh if you want to
    re-apply soul/puppet state).
    """
    existing = await memory.search(name, Character)
    if existing:
        logger.info("Seed: character '%s' already exists — skipping.", name)
        return existing, None

    character, soul = await memory.create_character_and_soul(
        account_id=account.id,
        name=name,
        description=description,
        location=None,
        permission_level=permission_level,
    )
    character.location = position
    if attributes is not None:
        character.attributes = attributes
    if puppet_self:
        character.puppeted_by_id = soul.id
    await character.save()
    logger.info(
        "Seed: created character '%s' (perm=%d, puppet_self=%s).",
        name,
        permission_level,
        puppet_self,
    )
    return character, soul


async def _ensure_npc(
    memory,
    name: str,
    description: str,
    position: tuple[float, float, float],
    *,
    attributes: dict | None = None,
) -> Character:
    """Create a soulless Character (NPC) — no account, no soul, just a body."""
    existing = await memory.search(name, Character)
    if existing:
        logger.info("Seed: NPC '%s' already exists — skipping.", name)
        return existing
    npc = await memory.create_character(
        name=name,
        soul=None,
        description=description,
        location=position,
        attributes=attributes,
    )
    logger.info("Seed: created NPC '%s'.", name)
    return npc


async def _wipe(sessionmaker):
    """Delete all seed-relevant rows. FK-safe order."""
    logger.info("Seed: --fresh requested — wiping existing data…")
    async with sessionmaker() as session:
        await session.execute(delete(Character))
        await session.execute(delete(GameObject))
        await session.execute(delete(CharacterSoul))
        await session.execute(delete(Account))
        await session.execute(delete(Area))
        await session.execute(delete(Terrain))
        await session.commit()
    logger.info("Seed: wipe complete.")


# ---------------------------------------------------------------------------
# Main seed
# ---------------------------------------------------------------------------


async def seed(fresh: bool = False):
    from morphologic_server.db.engine import create_sessionmaker
    from morphologic_server.db.memory import Memory
    from morphologic_server.config import ServerSettings

    settings = ServerSettings()
    sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
    Base._sessionmaker = sessionmaker
    memory = Memory(sessionmaker)

    if fresh:
        await _wipe(sessionmaker)

    logger.info("Seeding database…")

    # ── Areas ────────────────────────────────────────────────────────────── #
    if not await memory.simple_query("Mały, wierzbowy lasek", "name", Area):
        await memory.create_area(
            polygon=[(-10, -10), (10, -10), (10, 10), (-10, 10), (-10, -10)],
            name="Mały, wierzbowy lasek",
            description="Cichy lasek nad rzeką, gdzie rosną stare wierzby.",
            priority=2,
        )
        logger.info("Seed: created area 'Mały, wierzbowy lasek'")

    if not await memory.simple_query("Polana", "name", Area):
        await memory.create_area(
            polygon=[(5, 5), (20, 5), (20, 20), (5, 20), (5, 5)],
            name="Polana",
            description="Niewielka polana z miękką trawą i dzikimi kwiatami.",
            priority=1,
        )
        logger.info("Seed: created area 'Polana'")

    # Overlapping high-priority area, sits inside the wierzbowy lasek.
    if not await memory.simple_query("Magiczny Zakątek", "name", Area):
        await memory.create_area(
            polygon=[(-2, -2), (2, -2), (2, 2), (-2, 2), (-2, -2)],
            name="Magiczny Zakątek",
            description="Drewniana ławka pod rozłożystą wierzbą. Światło wydaje się tu docierać w mniejszym stopniu.",
            priority=10,
        )
        logger.info("Seed: created area 'Magiczny Zakątek'")

    # Karczma — far from spawn so it doesn't tangle with the lasek/polana.
    if not await memory.simple_query("Karczma 'Pod Srebrzystym Liściem'", "name", Area):
        await memory.create_area(
            polygon=[(45, 45), (55, 45), (55, 55), (45, 55), (45, 45)],
            name="Karczma 'Pod Srebrzystym Liściem'",
            description="Przytulna karczma o ścianach z bali i niskim, dymnym sklepieniu.",
            priority=3,
        )
        logger.info("Seed: created area 'Karczma 'Pod Srebrzystym Liściem''")

    # ── Terrain around spawn ──────────────────────────────────────────────── #
    terrain_tiles = [
        (0, 0, 0, TerrainType.SOIL),
        (3, 3, 0, TerrainType.SOIL),
        (-3, 3, 0, TerrainType.SOIL),
        (3, -3, 0, TerrainType.SOIL),
        (-3, -3, 0, TerrainType.SOIL),
        (6, 0, 0, TerrainType.SAND),
        (-6, 0, 0, TerrainType.SAND),
        (0, 6, 0, TerrainType.ROCK),
        (0, -6, 0, TerrainType.ROCK),
        (8, 4, 0, TerrainType.WATER),
        (-5, 7, 0, TerrainType.WATER),
        (5, -7, 0, TerrainType.SAND),
        # A patch around the karczma
        (50, 50, 0, TerrainType.SOIL),
        (49, 50, 0, TerrainType.SOIL),
        (51, 50, 0, TerrainType.SOIL),
        (50, 51, 0, TerrainType.SOIL),
    ]
    for x, y, z, t_type in terrain_tiles:
        await memory.create_or_edit_terrain(x, y, z, t_type)
    logger.info("Seed: ensured %d terrain tiles.", len(terrain_tiles))

    # ── Top-level objects scattered around spawn ─────────────────────────── #
    await _ensure_object(
        memory, "Stary dąb", "Rozłożysty dąb z wyraźną dziuplą.", _pt(3, 4)
    )
    kamien = await _ensure_object(
        memory,
        "Kamień graniczny",
        "Omszały kamień z wyrytym znakiem. Chwilami niby drży, mieni się w oczach.",
        _pt(-4, 2),
        attributes={"weight": 200, "sacred": True},
    )
    await _ensure_object(
        memory,
        "Wiadro",
        "Drewniane wiadro bez ucha.",
        _pt(1, -5),
        attributes={"weight": 1.5},
    )
    await _ensure_object(memory, "Ognisko", "Dopalające się ognisko.", _pt(-2, -2))
    skrzynia = await _ensure_object(
        memory,
        "Skrzynia",
        "Ciężka drewniana skrzynia.",
        _pt(7, 1),
        attributes={"weight": 20, "closed": False},
    )

    # ── Nested objects around spawn ──────────────────────────────────────── #
    # Two-level nest: Skrzynia → Sakiewka → monety.
    sakiewka = await _ensure_object(
        memory,
        "Sakiewka",
        "Skórzana sakiewka z monetami.",
        holder=skrzynia,
        attributes={"weight": 0.1},
    )
    await _ensure_object(
        memory,
        "Miedziana moneta",
        "Miedziana moneta.",
        holder=sakiewka,
        attributes={"weight": 0.005, "value": 1},
    )
    await _ensure_object(
        memory,
        "Srebrna moneta",
        "Srebrna moneta.",
        holder=sakiewka,
        attributes={"weight": 0.005, "value": 10},
    )
    await _ensure_object(
        memory,
        "Złota moneta",
        "Złota moneta.",
        holder=sakiewka,
        attributes={"weight": 0.008, "value": 100},
    )

    # ── Accounts ─────────────────────────────────────────────────────────── #
    moony_account = await _ensure_account(memory, "Moony", "moony@example.com", permission_level=0)
    another_account = await _ensure_account(
        memory, "AnotherAccount", "another@example.com"
    )
    zjawek_account = await _ensure_account(memory, "Zjawek", "zjawek@example.com")

    # ── Player characters (puppeted by their own souls) ──────────────────── #
    moony_char, _ = await _ensure_player_character(
        memory,
        moony_account,
        "MoonyTheDream",
        "Nikt taki, a jednak ktoś więcej.",
        position=(0.0, 0.0, 0.0),
        attributes={"strenght": "mocniak"},
        permission_level=0,  # admin
        puppet_self=True,
    )

    await _ensure_player_character(
        memory,
        another_account,
        "Wędrowiec",
        "Wędrująca dusza bez stałego celu.",
        position=(2.0, 3.0, 0.0),
        permission_level=2,
        puppet_self=True,
    )

    # zjawek: bound character placed far away, soul puppets the boundary stone.
    zjawek_char, zjawek_soul = await _ensure_player_character(
        memory,
        zjawek_account,
        "Zjawek z lasu",
        "Cień, który czasem wciela się w martwe rzeczy.",
        position=(-50.0, -50.0, 0.0),
        permission_level=2,
        puppet_self=False,
    )
    if zjawek_soul is not None and kamien is not None:
        kamien.puppeted_by_id = zjawek_soul.id
        await kamien.save()
        logger.info("Seed: Zjawek's soul now puppets 'Kamień graniczny'.")

    # ── Moony's inventory (items contained inside the character) ─────────── #
    await _ensure_object(
        memory,
        "Pędzel Moony'ego",
        "Cieniutki pędzel z czarną rączką.",
        holder=moony_char,
        attributes={"weight": 0.05},
    )
    await _ensure_object(
        memory,
        "Pióro wieczne",
        "Eleganckie pióro wieczne ze stalówką ze srebra.",
        holder=moony_char,
        attributes={"weight": 0.03, "ink": "black"},
    )
    await _ensure_object(
        memory,
        "Pergamin",
        "Zwitek czystego pergaminu.",
        holder=moony_char,
        attributes={"weight": 0.02},
    )

    # ── Karczma: NPC + furniture with nested contents ────────────────────── #
    await _ensure_npc(
        memory,
        "Stefan Karczmarz",
        "Krępy mężczyzna w fartuchu, wycierający kufel ścierką.",
        position=(49.0, 51.0, 0.0),
        attributes={"weight": 95},
    )

    kontuar = await _ensure_object(
        memory,
        "Kontuar",
        "Solidny dębowy kontuar, pociemniały od lat.",
        _pt(49, 50),
        attributes={"weight": 80},
    )
    await _ensure_object(
        memory,
        "Butelka miodu pitnego",
        "Pękata butelka miodu pitnego.",
        holder=kontuar,
        attributes={"weight": 1.2, "capacity": 0.75},
    )
    await _ensure_object(
        memory,
        "Butelka wina",
        "Butelka czerwonego wina.",
        holder=kontuar,
        attributes={"weight": 1.2, "capacity": 0.75},
    )

    stol_glowny = await _ensure_object(
        memory,
        "Stół przy palenisku",
        "Duży drewniany stół przy palenisku.",
        _pt(51, 50),
        attributes={"weight": 30},
    )
    await _ensure_object(
        memory,
        "Kufel",
        "Gliniany kufel po piwie.",
        holder=stol_glowny,
        attributes={"weight": 0.5, "capacity": 0.5},
    )
    talerz = await _ensure_object(
        memory,
        "Talerz",
        "Drewniany talerz z śladami tłuszczu.",
        holder=stol_glowny,
        attributes={"weight": 0.4},
    )
    # Three-level nest: Stół → Talerz → Chleb.
    await _ensure_object(
        memory,
        "Chleb",
        "Pajda razowego chleba.",
        holder=talerz,
        attributes={"weight": 0.5},
    )

    stol_boczny = await _ensure_object(
        memory,
        "Stół w rogu",
        "Mniejszy stół w cieniu rogu.",
        _pt(52, 51),
        attributes={"weight": 25},
    )
    await _ensure_object(
        memory,
        "Kufel piwa",
        "Pełny kufel jasnego piwa.",
        holder=stol_boczny,
        attributes={"weight": 0.9, "capacity": 0.5},
    )

    logger.info("Seeding complete.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed the morphoLogic database.")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe all existing accounts, characters, objects, areas and terrain first.",
    )
    args = parser.parse_args()
    asyncio.run(seed(fresh=args.fresh))


if __name__ == "__main__":
    main()
