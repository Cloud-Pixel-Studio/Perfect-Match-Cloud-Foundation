from __future__ import annotations

from functools import lru_cache
from typing import cast

from sqlalchemy import Engine, create_engine, text

from pmc_api.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def database_is_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            result = cast(int, connection.execute(text("SELECT 1")).scalar_one())
            return result == 1
    except Exception:
        return False
