from __future__ import annotations

import pytest

from application.services.card_generation.llm_schemas import (
    ReviewCardOutput,
    WriteCardOutput,
)

# Test cases:
# 1. В схемах для модели каждый объект запрещает лишние поля, все его поля обязательные, дефолтов нет
# 2. В схемах для модели нет maxLength и minLength на строках, ограничения массивов есть


def walk_objects(schema: dict) -> list[dict]:
    objects = [schema] if schema.get("type") == "object" else []
    for definition in schema.get("$defs", {}).values():
        objects.extend(walk_objects(definition))
    return objects


@pytest.mark.parametrize(
    ("output", "objects_count"),
    [(WriteCardOutput, 4), (ReviewCardOutput, 2)],
)
def test_case_1(output, objects_count) -> None:
    # 1. В схемах для модели каждый объект запрещает лишние поля, все его поля обязательные, дефолтов нет
    # Act
    objects = walk_objects(output.model_json_schema())

    # Assert
    assert len(objects) == objects_count
    for item in objects:
        assert item["additionalProperties"] is False
        assert set(item["required"]) == set(item["properties"])
        assert all("default" not in field for field in item["properties"].values())


def test_case_2() -> None:
    # 2. В схемах для модели нет maxLength и minLength на строках, ограничения массивов есть
    # Act
    schema = WriteCardOutput.model_json_schema()

    # Assert
    assert schema["properties"]["search_queries"]["minItems"] == 3
    assert schema["properties"]["search_queries"]["maxItems"] == 5
    assert schema["properties"]["missing_characteristics"]["maxItems"] == 5
    for item in walk_objects(schema):
        for field in item["properties"].values():
            assert "maxLength" not in field
            assert "minLength" not in field
