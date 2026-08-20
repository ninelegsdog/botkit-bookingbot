from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .migrations import Migration, MigrationRegistry


class Database:
    def __init__(self, url: str, *, poolclass: type | None = None) -> None:
        kwargs: dict = {"url": url}
        if poolclass is not None:
            kwargs["poolclass"] = poolclass
        self._engine = create_async_engine(**kwargs)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            async with session.begin():
                yield session

    async def init_database(self, registry: MigrationRegistry) -> None:
        applied = await self._applied_versions()
        for migration in registry.migrations:
            if migration.version not in applied:
                await self._apply(migration)

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def _applied_versions(self) -> set[int]:
        async with self._engine.connect() as conn:
            try:
                result = await conn.execute(text("SELECT version FROM _migrations ORDER BY version"))
                return {row[0] for row in result.all()}
            except Exception:
                await conn.execute(
                    text("CREATE TABLE IF NOT EXISTS _migrations (version INTEGER PRIMARY KEY, name TEXT)")
                )
                return set()

    async def _apply(self, migration: Migration) -> None:
        async with self._engine.begin() as conn:
            for stmt in migration.statements:
                await conn.execute(text(stmt))
            await conn.execute(
                text("INSERT INTO _migrations (version, name) VALUES (:v, :n)"),
                {"v": migration.version, "n": migration.name},
            )
