from __future__ import annotations

import pytest
from pydantic import ValidationError

from bootstrap.settings import Settings

KEY_VARIABLE = "PRODUCT_CARD_OPENROUTER_API_KEY"

# Test cases:
# 1. Без ключа настройки не собираются, чужая переменная OPENROUTER_API_KEY не считается
# 2. Пустой ключ настройки не принимают
# 3. Ключ не виден в repr настроек, модель и base URL по умолчанию как у Carevia


def test_case_1(monkeypatch) -> None:
    # 1. Без ключа настройки не собираются, чужая переменная OPENROUTER_API_KEY не считается
    # Arrange
    monkeypatch.delenv(KEY_VARIABLE, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "other-service-key")

    # Act, Assert
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_case_2(monkeypatch) -> None:
    # 2. Пустой ключ настройки не принимают
    # Arrange
    monkeypatch.setenv(KEY_VARIABLE, "")

    # Act, Assert
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_case_3(monkeypatch) -> None:
    # 3. Ключ не виден в repr настроек, модель и base URL по умолчанию как у Carevia
    # Arrange
    monkeypatch.setenv(KEY_VARIABLE, "test-secret-value")

    # Act
    settings = Settings(_env_file=None)

    # Assert
    assert "test-secret-value" not in repr(settings)
    assert settings.openrouter_model == "meta/muse-spark-1.3-contributor"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
