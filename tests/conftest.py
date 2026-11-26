import os
import secrets
from unittest.mock import patch

import pytest

from app.api.dependencies import get_token_service
from app.core.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def jwt_test_secret():
    with patch.dict(os.environ, {"JWT_SECRET_KEY": secrets.token_urlsafe(32), "REFRESH_COOKIE_SECURE": "true"}):
        get_settings.cache_clear()
        get_token_service.cache_clear()
        yield
        get_settings.cache_clear()
        get_token_service.cache_clear()
