"""The older tests were written for the castle start (a court, a treasury, a capital to walk around). The living
world now starts on the frontier by default; tests/test_frontier.py covers that."""
import pytest

from city import config


@pytest.fixture(autouse=True)
def _castle_start_for_older_tests(request, monkeypatch):
    if "frontier" not in request.module.__name__:
        monkeypatch.setitem(config.DEFAULTS, "start", "kingdom")
