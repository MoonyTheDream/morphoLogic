"""SQLAlchemy with Async Support - connecting PostreSQL database with asyncpg"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from morphologic_server import settings, logger

try:
    engine = create_async_engine("postgresql+asyncpg://" + settings.DB_ADDRESS)
except Exception as e:
    logger.exception("Failed to connect to the database: %s", e)
    raise

DBAsyncSession = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


