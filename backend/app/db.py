from typing import Literal

import psycopg
import redis

from backend.app.config import Settings


DependencyStatus = Literal["ok", "not_configured", "unavailable"]


def check_database_status(settings: Settings) -> DependencyStatus:
    """Check whether PostgreSQL is configured and reachable."""

    # Treat missing configuration as an explicit bootstrap state, not a crash.
    if settings.database_url is None:
        return "not_configured"

    try:
        # Run the smallest possible query so the health endpoint proves connectivity only.
        with psycopg.connect(settings.database_url, connect_timeout=1) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception:
        # Health checks should report dependency state without breaking the whole API.
        return "unavailable"

    return "ok"


def check_redis_status(settings: Settings) -> DependencyStatus:
    """Check whether Redis is configured and reachable."""

    # Treat missing configuration as an explicit bootstrap state, not a crash.
    if settings.redis_url is None:
        return "not_configured"

    try:
        # Ping is enough for M1 because no Redis-backed workflow has been added yet.
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
    except Exception:
        # Health checks should report dependency state without breaking the whole API.
        return "unavailable"

    return "ok"
