# from sqlalchemy import create_engine
# from sqlalchemy.orm import Session
# from geoalchemy2 import shape
# from shapely.geometry import Point
# from morphologic_server.db.models import Account, CharacterSoul, GameObject, Character, ObjectType

# # Set up the database connection (example: SQLite in memory)
# engine = create_engine("postgresql://morphoLogicServer:morphoLogicTEST@109.241.128.160:5436/morphoLogicDB")
# # Session = sessionmaker(bind=engine)
# # session = Session()

# with Session(engine) as session:
#     # Example: Create Account
#     account_1 = Account(name="Moony", email="moony@example.com")
#     account_2 = Account(name="AnotherPlayer", email="another@example.com")
#     session.add_all([account_1, account_2])
#     session.commit()

#     # Example: Create CharacterSoul
#     soul_1 = CharacterSoul(account_id=account_1.id, permission_level=0)
#     soul_2 = CharacterSoul(account_id=account_2.id, permission_level=2, aura=-10)
#     session.add_all([soul_1, soul_2])
#     session.commit()

#     # Example: Create Characters
#     character_1 = Character(
#         name="MoonyTheDwarf",
#         description="Taki tam Moony",
#         soul_id=soul_1.id,  # Link CharacterSoul to Character
#         location=shape.from_shape(Point(0, 0, 0), srid=3857),  # Example 3D location
#         object_type=ObjectType.CHARACTER,
#         attributes={"strength": "dużo"}
#     )
#     character_2 = Character(
#         name="AnotherCharacter",
#         # description="Jakiś totalny dziad",
#         soul_id=soul_2.id,  # Link CharacterSoul to Character
#         location=shape.from_shape(Point(1, 2, 0), srid=3857),  # Example 3D location
#         object_type=ObjectType.CHARACTER,
#     )
#     session.add_all([character_1, character_2])
#     session.commit()

#     # Example: Create GameObjects (items or other objects)
#     coin_1 = GameObject(
#         name="Gold Coin",
#         description="A shiny gold coin",
#         location=shape.from_shape(Point(0, 0, 0), srid=3857),  # Example location
#         object_type=ObjectType.ITEM,
#         attributes={"value": 1},
#     )
#     coin_2 = GameObject(
#         name="Silver Coin",
#         description="A shiny silver coin",
#         location=shape.from_shape(Point(0, 0, 0), srid=3857),  # Example location
#         object_type=ObjectType.ITEM,
#         attributes={"value": 0.5},
#     )
#     coin_3 = GameObject(
#         name="Copper Coin",
#         description="A shiny copper coin",
#         location=shape.from_shape(Point(1, 1, 0), srid=3857),  # Example location
#         object_type=ObjectType.ITEM,
#         attributes={"value": 0.1},
#     )

#     session.add_all([coin_1, coin_2, coin_3])
#     session.commit()

#     # Example: MoonyTheDwarf will puppet the pouch containing the coins
#     pouch = GameObject(
#         name="Coin Pouch",
#         description="A small leather pouch with coins inside",
#         location=shape.from_shape(Point(0, 0, 0), srid=3857),
#         object_type=ObjectType.ITEM,
#         attributes={"capacity": 5},
#     )
#     session.add(pouch)
#     session.commit()

#     # MoonyTheDwarf puppets the pouch (set by puppeting_id)
#     soul_1.puppeting = character_1
#     soul_2.puppeting = character_2
#     session.commit()
#     pouch.stored.append(coin_1)
#     pouch.stored.append(coin_2)
#     # pouch.stored.append(coin_3)
    
#     # Now we have:
#     # - Moony's account with a character soul bound to MoonyTheDwarf character
#     # - MoonyTheDwarf character puppeting the pouch
#     # - The pouch contains 3 coins (Gold, Silver, Copper)
#     # - All objects are stored in the database with their relationships correctly set up

#     # Commit final changes
#     session.commit()

