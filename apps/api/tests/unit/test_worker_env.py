from __future__ import annotations

from truegrit_api.config import get_settings
from truegrit_api.platform.worker_env import bridge_worker_env


class WorkerEnv:
    ADMIN_LOGIN_EMAIL = "first-owner@example.test"
    ADMIN_LOGIN_PASSWORD = "first-password"


def test_rotated_worker_secrets_replace_cached_settings(monkeypatch):
    monkeypatch.delenv("ADMIN_LOGIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_LOGIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    env = WorkerEnv()
    bridge_worker_env(env)
    first = get_settings()
    assert first.admin_login_email == "first-owner@example.test"
    assert first.admin_login_password == "first-password"

    env.ADMIN_LOGIN_EMAIL = "rotated-owner@example.test"
    env.ADMIN_LOGIN_PASSWORD = "rotated-password"
    bridge_worker_env(env)
    rotated = get_settings()

    assert rotated is not first
    assert rotated.admin_login_email == "rotated-owner@example.test"
    assert rotated.admin_login_password == "rotated-password"


def test_non_text_bindings_are_not_copied(monkeypatch):
    monkeypatch.setenv("ADMIN_LOGIN_EMAIL", "existing-owner@example.test")
    get_settings.cache_clear()

    env = WorkerEnv()
    env.ADMIN_LOGIN_EMAIL = object()
    bridge_worker_env(env)

    assert get_settings().admin_login_email == "existing-owner@example.test"
