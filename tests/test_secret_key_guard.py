"""create_app() rejects an unsafe SECRET_KEY before doing any DB work.

The guardrail sits immediately after the env-var presence check, so these cases
set ALL FOUR required vars and weaken only SECRET_KEY. If they left the others
unset, the presence guard would raise first and the test would pass for the
wrong reason (a false positive that proves nothing). Asserting on the "too weak"
message distinguishes the guardrail's ValueError from the presence guard's.

No database is involved: the check runs before the app/DB is created, so
SQLITE3_DB points at a path that is never opened. The positive case (a strong
key lets create_app proceed) is already covered by every DB-backed fixture,
which now uses tests.TEST_SECRET_KEY.
"""
import pytest

from tests import TEST_SECRET_KEY


def _set_required_env(monkeypatch, secret_key):
    monkeypatch.setenv("SECRET_KEY", secret_key)
    monkeypatch.setenv("SQLITE3_DB", "never-opened-by-this-test.db")
    monkeypatch.setenv("SEED_EMAIL", "guard@example.com")
    monkeypatch.setenv("SEED_PWD", "unused")


@pytest.mark.parametrize("weak_key", [
    "t",            # far too short
    "x" * 31,       # one char below the 32 floor
    "development",  # known-weak placeholder
    "secret",       # known-weak placeholder
    "secret_key",   # known-weak placeholder
])
def test_create_app_rejects_weak_secret_key(monkeypatch, weak_key):
    _set_required_env(monkeypatch, weak_key)
    from course_reg import create_app
    with pytest.raises(ValueError, match="too weak"):
        create_app()


def test_create_app_accepts_strong_secret_key_for_the_guard(monkeypatch):
    """A 32+ char, non-placeholder key clears the guardrail. We don't run the
    full create_app() here (that needs a seeded DB); we only assert the key
    itself satisfies the rule the guard enforces, so the constant the fixtures
    rely on can't silently drift below the threshold."""
    assert len(TEST_SECRET_KEY) >= 32
    assert TEST_SECRET_KEY.strip().lower() not in {
        "development", "secret", "secret_key", "changeme", "password"
    }
