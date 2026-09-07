from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from typing import cast
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from pmc_api.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        try:
            yield session
        finally:
            session.rollback()


def set_request_context(
    session: Session,
    *,
    user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    session_hash: bytes | None = None,
    issuer: str | None = None,
    subject: str | None = None,
    login_state_hash: bytes | None = None,
) -> None:
    values = {
        "user_id": str(user_id) if user_id else "",
        "tenant_id": str(tenant_id) if tenant_id else "",
        "session_hash": session_hash.hex() if session_hash else "",
        "issuer": issuer or "",
        "subject": subject or "",
        "login_state_hash": login_state_hash.hex() if login_state_hash else "",
    }
    for key, value in values.items():
        session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": f"app.{key}", "value": value},
        )


def database_is_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            result = cast(int, connection.execute(text("SELECT 1")).scalar_one())
            return result == 1
    except Exception:
        return False
