"""Alembic migration environment (async mode)"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from sandbox.config import settings
from sandbox.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.postgres_dsn,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.postgres_dsn)
    async with engine.connect() as conn:
        await conn.run_sync(_run_sync)
    await engine.dispose()


def _run_sync(conn):
    context.configure(
        connection=conn,
        target_metadata=target_metadata,
        compare_type=True,
        version_table="sandbox_alembic_version",  # 每個服務獨立的版本追蹤表
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
