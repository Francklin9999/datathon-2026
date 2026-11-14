"""Export every named contract as one local-only JSON Schema registry."""

import inspect
from enum import StrEnum

from pydantic import Field, TypeAdapter, create_model
from typing_extensions import TypeAliasType

from . import CONTRACT_VERSION, api, base, models
from .base import WireModel


def contract_types() -> dict[str, type]:
    result = {}
    for module in (base, models, api):
        for name, value in vars(module).items():
            if name.startswith("_") or value is WireModel:
                continue
            is_model = inspect.isclass(value) and issubclass(value, WireModel)
            is_enum = inspect.isclass(value) and issubclass(value, StrEnum)
            if is_model or is_enum or isinstance(value, TypeAliasType):
                if name in result and result[name] is not value:
                    raise ValueError(f"Contract type redefined: {name}")
                result[name] = value
    return dict(sorted(result.items()))


def adapter(name: str) -> TypeAdapter:
    """Validate JSON with adapter(name).validate_json(payload)."""
    return TypeAdapter(contract_types()[name])


def export_schema() -> dict:
    registry = create_model(
        "AplombContracts",
        __base__=WireModel,
        **{name: (value, Field(alias=name)) for name, value in contract_types().items()},
    )
    schema = registry.model_json_schema(by_alias=True)
    # Registry property names are type names, not a public API payload.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://aplomb.local/contracts/{CONTRACT_VERSION}/schema.json"
    schema["x-contract-version"] = CONTRACT_VERSION

    def clean(node):
        if isinstance(node, dict):
            for prop in node.get("properties", {}).values():
                prop.pop("title", None)
            for child in node.values():
                clean(child)
        elif isinstance(node, list):
            for child in node:
                clean(child)

    clean(schema)
    return schema
