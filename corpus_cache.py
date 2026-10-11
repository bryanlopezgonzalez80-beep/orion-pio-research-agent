"""Short-lived, single-flight cache for shared corpus totals, never user records."""
from copy import deepcopy
from functools import wraps
from threading import Lock
from time import monotonic
from database.config import get_database_config


def corpus_cache(ttl=120):
    def decorate(fn):
        lock = Lock()
        cached = None
        expires = 0.0
        database = None

        @wraps(fn)
        def read():
            nonlocal cached, expires, database
            config = get_database_config()
            if config.engine != "postgres":
                return fn()
            key = config.database_url
            if cached is not None and database == key and monotonic() < expires:
                return deepcopy(cached)
            with lock:
                if cached is None or database != key or monotonic() >= expires:
                    value = fn()  # Never cache failures or label stale data as current.
                    cached, database, expires = deepcopy(value), key, monotonic() + ttl
                return deepcopy(cached)
        return read
    return decorate
