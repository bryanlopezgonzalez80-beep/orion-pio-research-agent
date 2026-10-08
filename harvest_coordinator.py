"""Coordinate harvest writers through the existing PostgreSQL database."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from datetime import datetime, timezone
import logging

from database.config import get_database_config
from database.connection import connect_database, first_value
from platform_store import get_setting, set_setting

# Session lock, shared by the API and cloud runners. No schema changes needed.
HARVEST_LOCK_ID = 571994393349
LEASE_KEY = "deep_harvest.execution_lease"
LOG = logging.getLogger(__name__)
_LOCK_CONNECTION = ContextVar("orion_harvest_lock_connection", default=None)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def harvest_lock(status_key: str, instance_id: str):
    config = get_database_config()
    if config.engine != "postgres":
        # Local SQLite development retains the API's existing thread locks.
        yield True
        return
    connection = connect_database(config)
    owned = False
    token = None
    try:
        owned = bool(first_value(connection.execute(
            "SELECT pg_try_advisory_lock(?)", (HARVEST_LOCK_ID,)
        ).fetchone()))
        connection.commit()
        if owned:
            set_setting(LEASE_KEY, {
                "status_key": status_key, "instance_id": instance_id,
                "started_at": _now(),
            })
            token = _LOCK_CONNECTION.set(connection)
        yield owned
    finally:
        if token is not None:
            _LOCK_CONNECTION.reset(token)
        if owned:
            try:
                lease = get_setting(LEASE_KEY) or {}
                if lease.get("instance_id") == instance_id:
                    set_setting(LEASE_KEY, {**lease, "finished_at": _now()})
                connection.execute("SELECT pg_advisory_unlock(?)", (HARVEST_LOCK_ID,))
                connection.commit()
            except Exception:
                LOG.warning("Harvest lock cleanup could not be confirmed.")
        connection.close()


def heartbeat_harvest():
    """Stop before more work if the database session protecting it was lost."""
    connection = _LOCK_CONNECTION.get()
    if connection is not None:
        connection.execute("SELECT 1").fetchone()
        connection.commit()


def active_harvest(status_key: str | None = None, instance_id: str | None = None) -> bool:
    """Probe the actual session lock, rather than trusting a stale heartbeat."""
    config = get_database_config()
    if config.engine != "postgres":
        return False
    connection = connect_database(config)
    owned = False
    try:
        owned = bool(first_value(connection.execute(
            "SELECT pg_try_advisory_lock(?)", (HARVEST_LOCK_ID,)
        ).fetchone()))
        if owned:
            connection.execute("SELECT pg_advisory_unlock(?)", (HARVEST_LOCK_ID,))
            connection.commit()
            return False
        if status_key is None and instance_id is None:
            return True
        lease = get_setting(LEASE_KEY) or {}
        return (
            (status_key is None or lease.get("status_key") == status_key)
            and (instance_id is None or lease.get("instance_id") == instance_id)
            and not lease.get("finished_at")
        )
    finally:
        connection.close()


def exclusive_job(status_key: str, instance, local_lock):
    """Avoid concurrent API/runner writers; preserve another runner's status."""
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            invoked = False
            try:
                with harvest_lock(status_key, instance()) as owned:
                    if not owned:
                        previous = get_setting(status_key) or {}
                        if previous.get("instance_id") in (None, instance()):
                            set_setting(status_key, {
                                **previous, "state": "interrupted_retryable",
                                "interrupted_at": _now(),
                                "message": "Otra corrida está trabajando; vuelve a intentar cuando termine.",
                            })
                        return {"state": "blocked_retryable"}
                    invoked = True
                    return function(*args, **kwargs)
            finally:
                lock = local_lock()
                if not invoked and lock is not None and lock.locked():
                    lock.release()
        return guarded
    return decorate
