"""
Memory — the world's memory, where things are remembered and recalled.

All database query and create operations live here, receiving the sessionmaker
via constructor injection instead of relying on a module-level global.
"""

from typing import Optional, Type, Tuple, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from geoalchemy2 import shape
from geoalchemy2.functions import (
    ST_DWithin,
    ST_Force2D,
    ST_3DDWithin,
    ST_3DDistance,
)
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon

from morphologic_server import logger
from morphologic_server.archetypes.base import (
    Archetypes,
    Account,
    Character,
    CharacterSoul,
    Terrain,
    Area,
    GameObject,
)
from morphologic_server.db.models import (
    AccountDB,
    CharacterSoulDB,
    TerrainType,
    TerrainDB,
    AreaDB,
    GameObjectDB,
    CharacterDB,
)


DEFAULT_SPAWN_LOCATION = from_shape(Point(0, 0, 0), srid=3857)

STANDARD_VISIBILITY_RADIUS = 10.0  # in metres


class Memory:
    """The world's Memory — all database operations in one place, injected with a sessionmaker."""

    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    # ******************************************************************************************** #
    #                                            SEARCHING                                         #
    # ******************************************************************************************** #

    async def find_account(self, account_name: str) -> Optional["Account"]:
        """
        Finds account by name.
        If "#<int>" is being searched, it will be searched by ID.

        Args:
            account_name (str): Name or #ID of the account to search for.

        Returns:
            Account: if found, None otherwise.
        """

        async with self._sessionmaker() as session:

            if account_name.startswith("#"):
                try:
                    account_id = int(account_name[1:])
                except ValueError:
                    logger.warning(
                        "Invalid account ID format: %s. Expected format: #[int].",
                        account_name,
                    )
                    return None
                stmt = select(AccountDB).where(AccountDB.id == account_id)

            else:
                stmt = select(AccountDB).where(AccountDB.name == account_name)
            result = await session.execute(stmt)
            account = result.scalars().first()

            if account:
                return Account(account)
            return None

    async def search(self, name_or_id: str, archetype: Type["Archetypes"]):
        """Search for an object by name or ID.
        If "#[int]" is being searched, it will be searched by ID.

        Args:
            name_or_id (str): Name or #ID of the object to search for.
            archetype (Archetypes): The archetype class to search in.

        Returns:
            Object: if found, None otherwise.
        """
        model = archetype.linked_db_obj

        async with self._sessionmaker() as session:
            if name_or_id.startswith("#"):
                try:
                    object_id = int(name_or_id[1:])
                except ValueError:
                    logger.warning(
                        "Invalid object ID format: %s. Expected format: #[int].",
                        name_or_id,
                    )
                    return None
                stmt = select(model).where(model.id == object_id)
            else:
                stmt = select(model).where(model.name == name_or_id)
            result = await session.execute(stmt)
            obj = result.scalars().first()

            return archetype(obj) if obj else None

    async def simple_query(self, value, attribute: str, model: Type["Archetypes"]):
        """Simple query to find rows from specified table by attribute.

        Args:
            value (any): the value to search for
            attribute (str): an attribute to search for
            model (Archetypes): the model to search in

        Returns:
            Archetypes: Returns object or objects if found, None otherwise.
        """
        async with self._sessionmaker() as session:
            stmt = select(model.linked_db_obj).where(
                getattr(model.linked_db_obj, attribute) == value
            )
            result = await session.execute(stmt)
            obj = result.scalars().all()

            if obj:
                return [model(o) for o in obj] if len(obj) > 1 else model(obj[0])
            return None

    async def search_by_xy(self, x: float, y: float, archetype: Type["Archetypes"]):
        """Search for an object by XY coordinates.

        Args:
            x (float): x coordinate
            y (float): y coordinate
            archetype (Archetypes child): The archetype class to search in.
        Returns:
            Object: if found, None otherwise.
        """
        point = from_shape(Point(x, y), srid=3857)
        model = archetype.linked_db_obj
        async with self._sessionmaker() as session:
            stmt = select(model).where(
                ST_DWithin(
                    ST_Force2D(model.location),
                    ST_Force2D(point),
                    0.1,
                )
            )
            result = await session.execute(stmt)
            obj = result.scalars().first()

            return archetype(obj) if obj else None

    async def get_objects_in_proximity(
        self, focal_point, radius: float = STANDARD_VISIBILITY_RADIUS
    ):
        """Get all game objects and characters within radius of a focal point.

        Args:
            focal_point: An archetype with a .location property (Point with x, y, z).
            radius (float): Search radius in metres.

        Returns:
            dict: {"game_objects": [...], "characters": [...]}
        """

        point_z = from_shape(
            Point(
                focal_point.location.x, focal_point.location.y, focal_point.location.z
            ),
            srid=3857,
        )

        async with self._sessionmaker() as session:
            stmt1 = (
                select(GameObjectDB)
                .where(ST_3DDWithin(GameObjectDB.location, point_z, radius))
                .order_by(ST_3DDistance(GameObjectDB.location, point_z))
            )

            stmt2 = (
                select(CharacterDB)
                .where(ST_3DDWithin(CharacterDB.location, point_z, radius))
                .order_by(ST_3DDistance(CharacterDB.location, point_z))
            )
            result1 = await session.execute(stmt1)
            result2 = await session.execute(stmt2)

            game_objects = result1.scalars().all()
            characters = result2.scalars().all()

        game_objects = [
            GameObject(obj) for obj in game_objects if obj.object_type != "character"
        ]
        characters = [Character(obj) for obj in characters]

        return {
            "game_objects": game_objects,
            "characters": characters,
        }

    # ******************************************************************************************** #
    #                                            CREATING                                          #
    # ******************************************************************************************** #

    async def create_account(self, name: str, email: str) -> Optional["Account"]:
        """Creates an account in the database.

        Returns:
            Account: Archetypes Account object if created, None otherwise.
        """

        async with self._sessionmaker() as session:
            account = AccountDB(name=name, email=email, permission_level=2)
            session.add(account)
            await session.commit()
            await session.refresh(account)
            return Account(account)

    async def create_character_and_soul(
        self,
        account_id,
        name: str,
        description: str = "",
        location=None,
        permission_level: int = 2,
    ) -> Optional[list]:
        """Creates a character and a character soul in the database.

        Returns:
            List[Character, CharacterSoul]: Archetypes Character and CharacterSoul objects if created,
                None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION

        async with self._sessionmaker() as session:
            character = CharacterDB(
                name=name,
                description=description,
                location=location,
            )
            character_soul = CharacterSoulDB(
                aura=0,
                account_id=account_id,
                permission_level=permission_level,
                bound_character=character,
            )
            session.add(character_soul)
            await session.commit()
            await session.refresh(character_soul)
            await session.refresh(character)

            return [Character(character), CharacterSoul(character_soul)]

    async def create_character(
        self,
        name: str,
        soul: "CharacterSoul",
        description: str = "",
        location=None,
        attributes: dict = None,
        container: "GameObject" = None,
        stored: list = None,
    ) -> Optional["Character"]:
        """Creates a character in the database.

        Returns:
            Character: Archetypes Character object if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION

        async with self._sessionmaker() as session:
            character = CharacterDB(
                name=name,
                soul=soul,
                description=description,
                location=location,
                attributes=attributes,
                container=container,
                stored=stored,
            )
            session.add(character)
            await session.commit()
            await session.refresh(character)
            return Character(character)

    async def create_or_edit_terrain(
        self, x: int, y: int, z: int = 0, terrain_type: TerrainType = TerrainType.SOIL
    ) -> "Terrain":
        """Add or edit terrain in DB.

        Args:
            x (int): x coordinate
            y (int): y coordinate
            z (int, optional): z coordinate. Defaults to 0.
            terrain_type (TerrainType, optional): type of terrain. Defaults to TerrainType.SOIL.

        Returns:
            Terrain: Created or updated terrain object.
        """

        async with self._sessionmaker() as session:
            point3d = Point(float(x), float(y), float(z))
            point_geom = shape.from_shape(point3d, srid=3857)

            # First check if the terrain already exists
            stmt = select(TerrainDB).where(
                ST_DWithin(
                    ST_Force2D(TerrainDB.location),
                    ST_Force2D(point_geom),
                    0.1,
                )
            )
            result = await session.execute(stmt)
            terrain = result.scalars().first()

            if terrain:
                # Terrain already exists, update it
                old_point = shape.to_shape(terrain.location)
                new_point = Point(old_point.x, old_point.y, float(z))

                terrain.location = shape.from_shape(new_point, srid=3857)
                terrain.type = terrain_type
            else:
                terrain = TerrainDB(location=point_geom, type=terrain_type)
                session.add(terrain)

            await session.commit()
            await session.refresh(terrain)
            return Terrain(terrain)

    async def create_area(
        self,
        polygon: list[Tuple[float, float]],
        name: str,
        description: str,
        priority: int = 0,
    ) -> Optional["Area"]:
        """Creates an area in the database.

        Returns:
            Area: Archetypes Area object if created, None otherwise.
        """

        async with self._sessionmaker() as session:
            polygon = Polygon(polygon)
            area = AreaDB(
                polygon=shape.from_shape(polygon, srid=3857),
                name=name,
                description=description,
                priority=priority,
            )
            session.add(area)
            await session.commit()
            await session.refresh(area)
            return Area(area)

    async def create_game_object(
        self,
        name: str,
        description: str = "",
        location=None,
        attributes: dict = None,
        container: "GameObject" = None,
        stored: Union[list["GameObject"], "GameObject"] = None,
    ) -> Optional["GameObject"]:
        """Creates a game object in the database.

        Returns:
            GameObject: Archetypes GameObject object if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION
        else:
            location = from_shape(location, srid=3857)

        kwargs = {}
        if container is not None:
            container = container.db_obj
            kwargs["container"] = container
        if stored is not None:
            if not isinstance(stored, list):
                stored = [stored]
            stored = [stored.db_obj for obj in stored]
            kwargs["stored"] = stored

        async with self._sessionmaker() as session:
            game_object = GameObjectDB(
                name=name,
                description=description,
                location=location,
                attributes=attributes,
                **kwargs,
            )
            session.add(game_object)
            await session.commit()
            await session.refresh(game_object)
            return GameObject(game_object)

    # ******************************************************************************************** #
    #                                         AUTHENTICATION                                       #
    # ******************************************************************************************** #

    async def authenticate(self, username: str, password: str) -> Optional["Character"]:
        """Return the bound Character if username + password are valid, else None.

        Lookup chain: Account.name → account.character_souls[0] → soul.bound_character.
        """
        account = await self.find_account(username)
        if account is None or not account.check_password(password):
            return None
        souls = account.character_souls
        if not souls:
            return None
        return souls[0].bound_character
