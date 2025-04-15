"""SQLAlchemy with Async Support - connecting PostreSQL database with asyncpg"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from morphologic_server import settings

_DEBUG = settings.LOG_LEVEL_DEBUG

DATABASE_URL = "postgresql+asyncpg://morphoLogicServer:morphologic@localhost:5432/morphoLogicDB"


# Create the async engnine
engine = create_async_engine(DATABASE_URL, echo=_DEBUG)

# Create the async session
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
    )

# ------------------------------------------------------------------------------------------------ #