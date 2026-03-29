"""SQLAlchemy with Async Support - connecting PostreSQL database with asyncpg"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


def create_sessionmaker(db_address: str) -> async_sessionmaker:
    """Create an async sessionmaker from a database address string."""
    engine = create_async_engine("postgresql+asyncpg://" + db_address)
    return async_sessionmaker(engine, expire_on_commit=False)
