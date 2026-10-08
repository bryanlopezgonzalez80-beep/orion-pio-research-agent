from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from threading import Lock

import pytest

import harvest_coordinator as coordinator

pytestmark = pytest.mark.integration


@pytest.fixture
def pg_lock(monkeypatch):
    settings = {}
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (True,)
    monkeypatch.setattr(coordinator, "get_database_config", lambda: SimpleNamespace(engine="postgres"))
    monkeypatch.setattr(coordinator, "connect_database", lambda config: connection)
    monkeypatch.setattr(coordinator, "get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(coordinator, "set_setting", lambda key, value: settings.__setitem__(key, dict(value)))
    return connection, settings


def test_lock_is_held_while_work_runs_and_released_on_exception(pg_lock):
    connection, settings = pg_lock
    with pytest.raises(RuntimeError):
        with coordinator.harvest_lock("job", "worker") as owned:
            assert owned
            assert "finished_at" not in settings[coordinator.LEASE_KEY]
            coordinator.heartbeat_harvest()
            raise RuntimeError("interrupted")
    assert settings[coordinator.LEASE_KEY]["finished_at"]
    assert any("pg_advisory_unlock" in call.args[0] for call in connection.execute.call_args_list)
    connection.close.assert_called_once()
    assert coordinator._LOCK_CONNECTION.get() is None


def test_lost_session_stops_work(pg_lock):
    connection, _ = pg_lock
    with coordinator.harvest_lock("job", "worker"):
        connection.execute.side_effect = RuntimeError("session lost")
        with pytest.raises(RuntimeError):
            coordinator.heartbeat_harvest()
    connection.close.assert_called_once()


def test_busy_lock_does_not_publish_lease_or_unlock(pg_lock):
    connection, settings = pg_lock
    connection.execute.return_value.fetchone.return_value = (False,)
    with coordinator.harvest_lock("job", "worker") as owned:
        assert not owned
    assert settings == {}
    assert connection.execute.call_count == 1
    connection.close.assert_called_once()


def test_failed_acquisition_closes_database_session(pg_lock):
    connection, _ = pg_lock
    connection.execute.side_effect = RuntimeError("down")
    with pytest.raises(RuntimeError):
        with coordinator.harvest_lock("job", "worker"):
            pytest.fail("work started")
    connection.close.assert_called_once()


def test_probe_does_not_trust_an_abandoned_lease(pg_lock):
    connection, settings = pg_lock
    settings[coordinator.LEASE_KEY] = {"status_key": "job", "instance_id": "worker"}
    assert not coordinator.active_harvest("job", "worker")
    connection.close.assert_called_once()


@pytest.mark.parametrize("key,instance,finished,expected", [
    (None, None, False, True), ("job", "worker", False, True),
    ("another", "worker", False, False), ("job", "another", False, False),
    ("job", "worker", True, False),
])
def test_probe_matches_running_worker(pg_lock, key, instance, finished, expected):
    connection, settings = pg_lock
    connection.execute.return_value.fetchone.return_value = (False,)
    settings[coordinator.LEASE_KEY] = {"status_key": "job", "instance_id": "worker", "finished_at": "done" if finished else None}
    assert coordinator.active_harvest(key, instance) is expected
    connection.close.assert_called_once()


def test_sqlite_compatibility_has_no_database_probe(monkeypatch):
    monkeypatch.setattr(coordinator, "get_database_config", lambda: SimpleNamespace(engine="sqlite"))
    monkeypatch.setattr(coordinator, "connect_database", lambda *args: pytest.fail("Postgres probe in local mode"))
    with coordinator.harvest_lock("job", "local") as owned:
        assert owned
        coordinator.heartbeat_harvest()
    assert not coordinator.active_harvest()


@pytest.mark.parametrize("owner", ["worker", "other"])
def test_busy_worker_preserves_other_progress_and_releases_local_guard(monkeypatch, pg_lock, owner):
    _, settings = pg_lock
    settings["job"] = {"instance_id": owner, "state": "running", "received": 71}
    @contextmanager
    def busy(*args):
        yield False
    monkeypatch.setattr(coordinator, "harvest_lock", busy)
    lock = Lock()
    lock.acquire()
    @coordinator.exclusive_job("job", lambda: "worker", lambda: lock)
    def run():
        pytest.fail("concurrent work")
    assert run() == {"state": "blocked_retryable"}
    assert not lock.locked()
    assert settings["job"]["received"] == 71
    assert settings["job"]["state"] == ("interrupted_retryable" if owner == "worker" else "running")


def test_wrapper_does_not_release_the_next_local_job(monkeypatch):
    @contextmanager
    def owned(*args):
        yield True
    monkeypatch.setattr(coordinator, "harvest_lock", owned)
    lock = Lock()
    lock.acquire()
    @coordinator.exclusive_job("job", lambda: "worker", lambda: lock)
    def run():
        lock.release()
        lock.acquire()  # Another request acquired the local guard.
        return "done"
    assert run() == "done"
    assert lock.locked()
    lock.release()
