"""CI pytest guards; loaded explicitly by scripts/ci.py, never by the app."""
import os
import socket

import pytest


def pytest_sessionstart(session):
    if os.environ.get("AI_PROVIDER") != "mock":
        raise pytest.UsageError("CI requires AI_PROVIDER=mock")


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def guard(operation):
        def connect(sock, address):
            # Windows asyncio implements socketpair using loopback TCP.
            # PostgreSQL also uses loopback; real adapters are independently
            # blocked by LEADFORGE_CI before opening a client.
            if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "localhost", "::1"}:
                raise AssertionError("External network access is forbidden in CI tests")
            return operation(sock, address)
        return connect

    monkeypatch.setattr(socket.socket, "connect", guard(original))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(original_ex))


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("LEADFORGE_REQUIRE_NO_SKIPS") == "1":
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter and reporter.stats.get("skipped"):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
