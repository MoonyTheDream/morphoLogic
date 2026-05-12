"""
Memory — the world's memory, where things are remembered and recalled.

All database query and create operations live here, receiving the sessionmaker
via constructor injection instead of relying on a module-level global.
"""

import asyncio

from typing import Optional, Type, Tuple, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

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
    ObjectType,
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

    async def find_account(self, username_or_id: str | int) -> Account | None:
        """Finds and returns account by id or username.

        Args:
            username_or_id (str | int): Username or ID of the account to search.

        Returns:
            Account | None: Account object if found, else None.
        """
        match username_or_id:
            case int():
                stmt = select(Account).where(Account.id == username_or_id)
            case str():
                stmt = select(Account).where(Account.username == username_or_id)

        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            return (await session.execute(stmt)).scalar_one_or_none()

    async def find_character(
        self,
        character: str | int | Character,
        eagerly: bool = False,
    ) -> Character | None:
        """
        Finds character by name, ID or Character object,
        Optionally eagerly loads the soul and account relationships.

        Args:
            character (str | int | Character): Name, ID, or Character object to search for.
            eagerly (bool): Loads the soul and account if True. Default to False.
        Returns:
            Character: if found, None otherwise.
        """
        base = select(Character)
        if eagerly:
            base = base.options(
                selectinload(Character.soul).selectinload(CharacterSoul.account),
                selectinload(Character.holder),
                selectinload(Character.holds),
            )

        match character:
            case Character():
                stmt = base.where(Character.id == character.id)
            case str():
                stmt = base.where(Character.name == character)
            case int():
                stmt = base.where(Character.id == character)

        async with self._sessionmaker() as session:
            return (await session.execute(stmt)).scalars().first()

    async def find_object(
        self, name_or_id: str | int, eagerly: bool = False
    ) -> GameObject | None:
        """Finds GameObject that is not a Character.
        Looks only for objects with exact name as given — to expand in the future
        to use fuzzy search.

        Args:
            name_or_id (str | int): Name or ID of the searched object.
            eagerly (bool): If True, also loads holder and holds relationships. Defaults to False.

        Returns:
            Optional[GameObject]: Returns the first matching object if found.
            None otherwise.
        """
        base = select(GameObject).where(GameObject.object_type != ObjectType.CHARACTER)
        if eagerly:
            base = base.options(
                selectinload(GameObject.holder), selectinload(GameObject.holds)
            )

        if isinstance(name_or_id, int):
            stmt = base.where(GameObject.id == name_or_id)
        elif isinstance(name_or_id, str):
            stmt = base.where(GameObject.name == name_or_id)
        else:
            raise TypeError("name_or_id must be a string or an integer")

        async with self._sessionmaker() as session:
            return (await session.execute(stmt)).scalars().first()

    async def search_by_xy(self, x: float, y: float) -> GameObject | Character | None:
        """Search for an object by XY coordinates.

        Args:
            x (float): x coordinate
            y (float): y coordinate
        Returns:
            GameObject | Character | None: Returns the first object found
            at the coordinates, or None if no object is found.
        """
        point = from_shape(Point(x, y), srid=3857)
        stmt = select(GameObject).where(
            ST_DWithin(
                ST_Force2D(GameObject.location),
                ST_Force2D(point),
                0.1,
            )
        )
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            return result.scalars().first()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Seed.py Z Tego Korzysta ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
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

    # -------------------------------------------------------------------------------------------- #

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

    async def create_account(
        self, username: str, email: str, permission_level: int = 2
    ) -> Optional[Account]:
        """Creates an account in the database.

        Returns:
            Account: Account object if created, None otherwise.
        """

        async with self._sessionmaker() as session:
            account = Account(username=username, email=email, permission_level=permission_level)
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
        attributes: dict = {},
        holder: GameObject | None = None,
        holds: list[GameObject] = [],
    ) -> Optional[Character]:
        """Creates a character in the database.

        Returns:
            Character: Character object if created, None otherwise.
        """

        if location is None:
            location = DEFAULT_SPAWN_LOCATION

        kwargs = {}
        if holder is not None:
            kwargs["holder"] = holder
        if holds is not None:
            if not isinstance(holds, list):
                holds = [holds]
            kwargs["holds"] = holds

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
        holder: GameObject = None,
        holds: Union[list[GameObject], GameObject] = None,
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
        if holder is not None:
            kwargs["holder"] = holder
        if holds is not None:
            if not isinstance(holds, list):
                holds = [holds]
            kwargs["holds"] = holds

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
