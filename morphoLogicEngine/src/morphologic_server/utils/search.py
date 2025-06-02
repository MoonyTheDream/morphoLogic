from typing import Type

from sqlalchemy import select

from geoalchemy2.shape import from_shape
from geoalchemy2.functions import ST_DWithin, ST_Force2D, ST_Distance, ST_3DDWithin, ST_3DDistance

from shapely.geometry import Point

from morphologic_server import logger
from morphologic_server.db.engine import DBAsyncSession
from morphologic_server.db.models import (
    GameObjectDB,
    CharacterDB,
)
from morphologic_server.archetypes.base import (
    Archetypes,
    GameObject,
    Character
)

STANDARD_VISIBILITY_RADIUS = 10.0  # IN METERES


async def get_objects_in_proximity(
    focal_point: Type["Archetypes"], radius: float = STANDARD_VISIBILITY_RADIUS
):
    point_z = from_shape(Point(focal_point.location.x, focal_point.location.y, focal_point.location.z), srid=3857)

    async with DBAsyncSession() as session:
        stmt1 = (
            select(GameObjectDB)
            .where(
                ST_3DDWithin(
                    GameObjectDB.location,
                    point_z,
                    radius,
                )
            )
            .order_by(
                ST_3DDistance(
                    GameObjectDB.location,
                    point_z,
                )
            )
        )
        
        stmt2 = (
            select(CharacterDB)
            .where(
                ST_3DDWithin(
                    CharacterDB.location,
                    point_z,
                    radius,
                )
            )
            .order_by(
                ST_3DDistance(
                    CharacterDB.location,
                    point_z,
                )
            )
        )
        result1 = await session.execute(stmt1)
        result2 = await session.execute(stmt2)
        
        game_objects = result1.scalars().all()
        characters = result2.scalars().all()
        
    game_objects = [GameObject(obj) for obj in game_objects if obj.object_type != "character"]
    characters = [Character(obj) for obj in characters]
    
    
    result = {
        "game_objects": game_objects,
        "characters": characters,
    }
    return result
        
        
        

        
# def recuring_put_objects_to_container(game_objects: dict):
#     object_ids = [int(obj_id) for obj_id in game_objects.keys()]
#     for o_id, obj in game_objects.items():
#         # logger.debug(obj)
#         container_id = obj.get("container_id")
#         if container_id in object_ids:
#             if dict_game_objects[container_id].get("contains", None) is None:
#                 dict_game_objects[container_id]["contains"] = []
#             contains = dict_game_objects[container_id]["contains"]
#             contains.append(obj)
#             # We remove the object from the dict_game_objects
#             obj.update({"contains": contains})
#             dict_game_objects.pop(o_id)


# async def get_objects_in_proximity(
#     focal_point: Type["Archetypes"], radius: float = STANDARD_VISIBILITY_RADIUS
# ):
#     # point = from_shape(Point(focal_point.location.x, focal_point.location.y), srid=3857)
#     point_z = from_shape(Point(focal_point.location.x, focal_point.location.y, focal_point.location.z), srid=3857)

#     async with DBAsyncSession() as session:
#         stmt1 = (
#             select(GameObjectDB)
#             .where(
#                 ST_3DDWithin(
#                     GameObjectDB.location,
#                     point_z,
#                     radius,
#                 )
#             )
#             .order_by(
#                 ST_3DDistance(
#                     GameObjectDB.location,
#                     point_z,
#                 )
#             )
#         )
        
#         stmt2 = (
#             select(CharacterDB)
#             .where(
#                 ST_3DDWithin(
#                     CharacterDB.location,
#                     point_z,
#                     radius,
#                 )
#             )
#             .order_by(
#                 ST_3DDistance(
#                     CharacterDB.location,
#                     point_z,
#                 )
#             )
#         )
#         result1 = await session.execute(stmt1)
#         result2 = await session.execute(stmt2)
        
#         game_objects = result1.scalars().all()
#         characters = result2.scalars().all()
        
#     game_objects = [GameObject(obj) for obj in game_objects]
#     characters = [Character(obj) for obj in characters]
#     # dict_game_objects = [d.as_dict for d in game_objects if d.as_dict.get("object_type") != "character"]
#     dict_game_objects = {obj.id : obj.as_dict for obj in game_objects if obj.as_dict.get("object_type") != "character"}
#     # dict_characters = [d.as_dict for d in characters]
#     dict_characters = {obj.id : obj.as_dict for obj in characters}
#     # logger.debug("Objects in proximity: %s", stringified_game_objects)
#     # logger.debug("Characters in proximity: %s", stringified_characters)
    
#     # # We add 'contains' key to all objects
#     # for obj in dict_game_objects.values():
#     #     obj.update({"contains": []})
#     # for obj in dict_characters.values():
#     #     obj.update({"contains": []})
    
#     # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ This Must Be A Recuring Function ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
#     # We will put the objects to it's containers
#     # In future it will validate if the user can see the object (e.g. the object is in
#     # someone's inventory so the user can't see it)
#     # object_ids = [int(obj_id) for obj_id in dict_game_objects.keys()]
#     # for o_id, obj in dict_game_objects.items():
#     #     # logger.debug(obj)
#     #     container_id = obj.get("container_id")
#     #     if container_id in object_ids:
#     #         if dict_game_objects[container_id].get("contains", None) is None:
#     #             dict_game_objects[container_id]["contains"] = []
#     #         contains = dict_game_objects[container_id]["contains"]
#     #         contains.append(obj)
#     #         # We remove the object from the dict_game_objects
#     #         obj.update({"contains": contains})
#     #         dict_game_objects.pop(o_id)
    
#     # for char in dict_characters:
#     #     for obj in dict_game_objects:
#     #         if obj.get("container_id") == char.get("id"):
#     #             char["objects"].append(obj)
#     #             dict_game_objects.remove(obj)
    
#     result = {
#         "game_objects": dict_game_objects,
#         "characters": dict_characters,
#     }
#     return result
#         # return archetype(obj) if obj else None