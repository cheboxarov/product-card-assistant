from __future__ import annotations

from application.services.card_generation.llm_schemas import CardTextsOutput

# Test cases:
# 1. В схеме для модели каждый объект запрещает лишние поля, все его поля обязательные, дефолтов нет


def walk_objects(schema: dict) -> list[dict]:
    objects = [schema] if schema.get("type") == "object" else []
    for definition in schema.get("$defs", {}).values():
        objects.extend(walk_objects(definition))
    return objects


def test_case_1() -> None:
    # 1. В схеме для модели каждый объект запрещает лишние поля, все его поля обязательные, дефолтов нет
    # Act
    objects = walk_objects(CardTextsOutput.model_json_schema())

    # Assert
    assert len(objects) == 2
    for item in objects:
        assert item["additionalProperties"] is False
        assert set(item["required"]) == set(item["properties"])
        assert all("default" not in field for field in item["properties"].values())
