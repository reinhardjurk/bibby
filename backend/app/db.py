from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


def engine_kwargs() -> dict:
    """Verbindungsparameter. Für Scaleway Serverless SQL (database_ssl=true):
    TLS erzwingen und asyncpg-Statement-Cache abschalten (die DB hängt hinter
    einem Connection-Pooler, der server-side prepared statements bricht)."""
    kwargs: dict = {"pool_pre_ping": True}
    if settings.database_ssl:
        kwargs["connect_args"] = {"ssl": True, "statement_cache_size": 0}
        kwargs["pool_reset_on_return"] = "rollback"
    return kwargs


engine = create_async_engine(settings.database_url, **engine_kwargs())
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-Dependency: liefert eine Session pro Request."""
    async with SessionLocal() as session:
        yield session
