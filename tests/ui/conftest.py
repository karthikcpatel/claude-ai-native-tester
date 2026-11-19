"""Fixtures for the UI tests: start the local mock app on a free loopback port and reset its ledger per test.

Set BASE_URL to test an app that is already running (the fixture then starts nothing). Any MOCK_APP_FAULT in the
environment is passed to the app, which is how the mutation challenge makes tests fail on purpose.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "mock-app" / "server.py"

def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=3) as response:  # loopback only
        return response.read()


@pytest.fixture(scope="session")
def base_url():
    external = os.environ.get("BASE_URL")
    if external:
        yield external.rstrip("/")
        return
    port = _free_port()
    env = {**os.environ, "MOCK_APP_TEST_ROUTES": "1", "MOCK_APP_QUIET": "1"}
    process = subprocess.Popen([sys.executable, str(APP), "--port", str(port)], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            _get(url + "/healthz")
            break
        except OSError:
            if process.poll() is not None:
                raise RuntimeError("mock app exited: " + process.stderr.read().decode(errors="replace"))
            time.sleep(0.1)
    else:
        process.kill()
        raise RuntimeError("mock app did not start")
    yield url
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture(autouse=True)
def clean_ledger(base_url):
    request = urllib.request.Request(base_url + "/__test__/reset", method="POST", data=b"")
    urllib.request.urlopen(request, timeout=3).read()


@pytest.fixture
def charges(base_url):
    """Callable returning the mock charges recorded so far (the ground truth for 'was anyone charged?')."""
    return lambda: json.loads(_get(base_url + "/__test__/ledger"))["charges"]
