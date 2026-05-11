"""
Memory — the world's memory, where things are remembered and recalled.

All database query and create operations live here, receiving the sessionmaker
via constructor injection instead of relying on a module-level global.
"""

import asyncio

from typing import Optional, Type, Tuple, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from geoalchemy2 import shape
from geoalchemy2.functions import (
    ST_DWithin,
    ST_Force2D,
    ST_Intersects,
    ST_3DDWithin,
    ST_3DDistance,
)
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon

from morphologic_server import logger
from morphologic_server.db.models import (
    Base,
    Account,
    CharacterSoul,
    Character,
    Terrain,
    TerrainType,
    Area,
    GameObject,
)

DEFAULT_SPAWN_LOCATION = from_shape(Point(0, 0, 0), srid=3857)

STANDARD_VISIBILITY_RADIUS = 10.0  # in metres

# 888    888                           888
# 888    888                           888
# 888    888                           888
# 8888888888  .d88b.   8888b.  888d888 888888
# 888    888 d8P  Y8b     "88b 888P"   888
# 888    888 88888888 .d888888 888     888
# 888    888 Y8b.     888  888 888     Y88b.
# 888    888  "Y8888  "Y888888 888      "Y888


# 888b     d888 8888888888 888b     d888  .d88888b.  8888888b. Y88b   d88P
# 8888b   d8888 888        8888b   d8888 d88P" "Y88b 888   Y88b Y88b d88P
# 88888b.d88888 888        88888b.d88888 888     888 888    888  Y88o88P
# 888Y88888P888 8888888    888Y88888P888 888     888 888   d88P   Y888P
# 888 Y888P 888 888        888 Y888P 888 888     888 8888888P"     888
# 888  Y8P  888 888        888  Y8P  888 888     888 888 T88b      888
# 888   "   888 888        888   "   888 Y88b. .d88P 888  T88b     888
# 888       888 8888888888 888       888  "Y88888P"  888   T88b    888
class Memory:
    """
    The world's Memory — all database operations in one place, injected with a sessionmaker.
    The sessionmaker is injected via the constructor, allowing for better testability
    and separation of concerns. When a server starts up, a Memory instance is created and passed
    to the MorphoLogicHeart,
    """

    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    # ******************************************************************************************** #
    #                                            SEARCHING                                         #
    # ******************************************************************************************** #

    async def find_account(self, account_name: str) -> Optional[Account]:
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
                stmt = select(Account).where(Account.id == account_id)

            else:
                stmt = select(Account).where(Account.username == account_name)
            result = await session.execute(stmt)
            return result.scalars().first()

    # 8888888888 8888888 Y88b   d88P 8888888 88888888888
    # 888          888    Y88b d88P    888       888
    # 888          888     Y88o88P     888       888
    # 8888888      888      Y888P      888       888
    # 888          888      d888b      888       888
    # 888          888     d88888b     888       888
    # 888          888    d88P Y88b    888       888
    # 888        8888888 d88P   Y88b 8888888     888

    # DO ZMIANY — LEPIEJ ZROBIĆ OSOBNE METHODS:
    # find_character, find_game_object, find_area, find_terrain
    async def search(self, name_or_id: str, model: Type[Base]):
        """Search for an object by name or ID.
        If "#[int]" is being searched, it will be searched by ID.

        Args:
            name_or_id (str): Name or #ID of the object to search for.
            model (Base subclass): The model class to search in.

        Returns:
            Object: if found, None otherwise.
        """
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
            try:
                result = await session.execute(stmt)
            except ConnectionRefusedError:
                logger.error(
                    "Database connection refused while searching for %s with name_or_id: %s\nCheck if the database server is running and accessible.",
                    model.__name__,
                    name_or_id,
                )
                raise
            return result.scalars().first()

    async def simple_query(self, value, attribute: str, model: Type[Base]):
        """Simple query to find rows from specified table by attribute.

        Args:
            value (any): the value to search for
            attribute (str): an attribute to search for
            model (Base subclass): the model to search in

        Returns:
            list: Returns list of objects if found, empty list otherwise.
        """
        async with self._sessionmaker() as session:
            stmt = select(model).where(getattr(model, attribute) == value)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def search_by_xy(self, x: float, y: float, model: Type[Base]):
        """Search for an object by XY coordinates.

        Args:
            x (float): x coordinate
            y (float): y coordinate
            model (Base subclass): The model class to search in.
        Returns:
            Object: if found, None otherwise.
        """
        point = from_shape(Point(x, y), srid=3857)
        async with self._sessionmaker() as session:
            stmt = select(model).where(
                ST_DWithin(
                    ST_Force2D(model.location),
                    ST_Force2D(point),
                    0.1,
                )
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_objects_in_proximity(
        self, focal_point, radius: float = STANDARD_VISIBILITY_RADIUS
    ):
        """Get all game objects and characters within radius of a focal point.

        Args:
            focal_point: A model with a .location property (Point with x, y, z).
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
            stmt = (
                select(GameObject)
                .where(ST_3DDWithin(GameObject.location, point_z, radius))
                .order_by(ST_3DDistance(GameObject.location, point_z))
            )

            result = await session.execute(stmt)
            all_objects = result.scalars().all()

            characters = [obj for obj in all_objects if isinstance(obj, Character)]
            game_objects = [
                obj for obj in all_objects if not isinstance(obj, Character)
            ]

        return {
            "game_objects": game_objects,
            "characters": characters,
        }

    async def get_full_surroundings(
        self, character: Character, radius: float = STANDARD_VISIBILITY_RADIUS
    ) -> dict:
        """Get all surroundings data for a character in a single session.

        Refreshes the character, then queries nearby objects, characters,
        area, and terrain — all within one session checkout.

        Returns:
            dict: {"game_objects": [...], "characters": [...], "area": Area|None, "terrain": [...]}
        """

        async def _fetch_obejct():
            async with self._sessionmaker() as session:
                stmt = (
                    select(GameObject)
                    .where(
                        ST_3DDWithin(GameObject.location, character._location, radius)
                    )
                    .order_by(ST_3DDistance(GameObject.location, character._location))
                )
                return (await session.execute(stmt)).scalars().all()

        async def _fetch_area():
            async with self._sessionmaker() as session:
                stmt = (
                    select(Area)
                    .where(ST_Intersects(Area.polygon, ST_Force2D(character._location)))
                    .order_by(Area.priority.desc())
                    .limit(
                        2
                    )  # We only need to check the top 2 areas for priority conflicts
                )
                return (await session.execute(stmt)).scalars().all()

        async def _fetch_terrain():
            async with self._sessionmaker() as session:
                stmt = select(Terrain).where(
                    ST_DWithin(
                        ST_Force2D(Terrain.location),
                        ST_Force2D(character._location),
                        radius,
                    )
                )
                return (await session.execute(stmt)).scalars().all()

        all_objects, areas, terrain = await asyncio.gather(
            _fetch_obejct(), _fetch_area(), _fetch_terrain()
        )

        characters = [obj for obj in all_objects if isinstance(obj, Character)]
        game_objects = [obj for obj in all_objects if not isinstance(obj, Character)]

        if len(areas) > 1 and areas[0].priority == areas[1].priority:
            logger.warning(
                "More than one area of the same priority at location %s",
                character._location,
            )
        area = areas[0] if areas else None

        return {
            "game_objects": game_objects,
            "characters": characters,
            "area": area,
            "terrain": terrain,
        }

    # ******************************************************************************************** #
    #                                            CREATING                                          #
    # ******************************************************************************************** #

    async def create_account(self, username: str, email: str) -> Optional[Account]:
        """Creates an account in the database.

        Returns:
            Account: Account object if created, None otherwise.
        """

        async with self._sessionmaker() as session:
            account = Account(username=username, email=email, permission_level=2)
            session.add(account)
            await session.commit()
            await session.refresh(account)
            return account

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
            List[Character, CharacterSoul]: if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION

        async with self._sessionmaker() as session:
            character = Character(
                name=name,
                description=description,
                location=location,
            )
            character_soul = CharacterSoul(
                aura=0,
                account_id=account_id,
                permission_level=permission_level,
                bound_character=character,
            )
            session.add(character_soul)
            await session.commit()
            await session.refresh(character_soul)
            await session.refresh(character)

            return [character, character_soul]

    async def create_character(
        self,
        name: str,
        soul: CharacterSoul,
        description: str = "",
        location=None,
        attributes: dict = None,
        container: GameObject = None,
        stored: list = None,
    ) -> Optional[Character]:
        """Creates a character in the database.

        Returns:
            Character: Character object if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION

        kwargs = {}
        if container is not None:
            kwargs["container"] = container
        if stored is not None:
            if not isinstance(stored, list):
                stored = [stored]
            kwargs["stored"] = stored

        async with self._sessionmaker() as session:
            character = Character(
                name=name,
                soul=soul,
                description=description,
                location=location,
                attributes=attributes,
                **kwargs,
            )
            session.add(character)
            await session.commit()
            await session.refresh(character)
            return character

    async def create_or_edit_terrain(
        self, x: int, y: int, z: int = 0, terrain_type: TerrainType = TerrainType.SOIL
    ) -> Terrain:
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
            stmt = select(Terrain).where(
                ST_DWithin(
                    ST_Force2D(Terrain.location),
                    ST_Force2D(point_geom),
                    0.1,
                )
            )
            result = await session.execute(stmt)
            terrain = result.scalars().first()

            if terrain:
                # Terrain already exists, update it
                old_point = shape.to_shape(terrain._location)
                new_point = Point(old_point.x, old_point.y, float(z))

                terrain._location = shape.from_shape(new_point, srid=3857)
                terrain.type = terrain_type
            else:
                terrain = Terrain(location=point_geom, type=terrain_type)
                session.add(terrain)

            await session.commit()
            await session.refresh(terrain)
            return terrain

    async def create_area(
        self,
        polygon: list[Tuple[float, float]],
        name: str,
        description: str,
        priority: int = 0,
    ) -> Optional[Area]:
        """Creates an area in the database.

        Returns:
            Area: Area object if created, None otherwise.
        """

        async with self._sessionmaker() as session:
            polygon = Polygon(polygon)
            area = Area(
                polygon=shape.from_shape(polygon, srid=3857),
                name=name,
                description=description,
                priority=priority,
            )
            session.add(area)
            await session.commit()
            await session.refresh(area)
            return area

    async def create_game_object(
        self,
        name: str,
        description: str = "",
        location=None,
        attributes: dict = None,
        container: GameObject = None,
        stored: Union[list[GameObject], GameObject] = None,
    ) -> Optional[GameObject]:
        """Creates a game object in the database.

        Returns:
            GameObject: GameObject object if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION
        else:
            location = from_shape(location, srid=3857)

        kwargs = {}
        if container is not None:
            kwargs["container"] = container
        if stored is not None:
            if not isinstance(stored, list):
                stored = [stored]
            kwargs["stored"] = stored

        async with self._sessionmaker() as session:
            game_object = GameObject(
                name=name,
                description=description,
                location=location,
                attributes=attributes,
                **kwargs,
            )
            session.add(game_object)
            await session.commit()
            await session.refresh(game_object)
            return game_object

    # ******************************************************************************************** #
    #                                         AUTHENTICATION                                       #
    # ******************************************************************************************** #

    async def authenticate(self, username: str, password: str) -> Optional[Character]:
        """Return the bound Character if username + password are valid, else None.

        Lookup chain: Account.username → account.character_souls[0] → soul.bound_character.
        """
        account = await self.find_account(username)
        if account is None or not account.check_password(password):
            return None
        souls = account.character_souls
        if not souls:
            return None
        return souls[0].bound_character
