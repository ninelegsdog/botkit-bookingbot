"""Integration tests using testcontainers for PostgreSQL and Redis."""
from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_container(db_session):
    """Test PostgreSQL container is accessible."""
    from sqlalchemy import text
    result = await db_session.execute(text("SELECT 1 as val"))
    row = result.fetchone()
    assert row is not None
    assert row.val == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_container(redis_client):
    """Test Redis container is accessible."""
    await redis_client.set("test_key", "test_value")
    value = await redis_client.get("test_key")
    assert value == "test_value"
    await redis_client.delete("test_key")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_hash(redis_client):
    """Test Redis hash operations."""
    await redis_client.hset("user:1", mapping={"name": "test", "email": "test@example.com"})
    user = await redis_client.hgetall("user:1")
    assert user["name"] == "test"
    assert user["email"] == "test@example.com"
    await redis_client.delete("user:1")
