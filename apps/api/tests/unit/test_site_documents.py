"""default_robots_txt must block crawling everywhere except production by
default -- a non-production environment (dev/test/staging) has no admin-set
override the first time it is ever deployed, so this default is what stood
between test.truegritin.com and Google actually indexing it."""

from __future__ import annotations

from typing import Literal

import pytest

from truegrit_api.config import Settings
from truegrit_api.services.site_documents import default_robots_txt

AppEnv = Literal["development", "test", "staging", "production"]


@pytest.mark.parametrize("app_env", ["development", "test", "staging"])
def test_non_production_environments_disallow_everything(app_env: AppEnv):
    content = default_robots_txt(Settings(app_env=app_env))
    assert "Disallow: /\n" in content
    assert "Allow:" not in content
    assert "Sitemap:" not in content


def test_production_allows_crawling_with_the_usual_exclusions():
    content = default_robots_txt(Settings(app_env="production"))
    assert "Allow: /\n" in content
    assert "Disallow: /checkout" in content
    assert "Disallow: /account" in content
    assert "Disallow: /payment/" in content
    assert "Sitemap:" in content
