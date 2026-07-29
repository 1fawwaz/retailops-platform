"""Shared JSON serialization for anything that crosses a persistence or
LLM-prompt boundary: tool results (tools/stockpilot_tools.py) and agent
tool-call results (agents/base.py) both need to turn a Pydantic model, a
list of them, a plain dict, or a bare primitive into JSON-safe data the
same way. StockPilot's own tools always return a Pydantic model or a
list of them (never a bare primitive), but agents/base.py's tool-calling
loop can run any StructuredTool, including simpler ones that just
return a string or number -- to_jsonable has to handle both.
"""

from pydantic import BaseModel

from orchestration.models.base import JsonDict, JsonValue

JsonPrimitive = str | int | float | bool


def to_jsonable(value: object) -> JsonValue | JsonPrimitive | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        result: JsonDict = value.model_dump(mode="json", by_alias=True)
        return result
    if isinstance(value, list):
        return [
            item.model_dump(mode="json", by_alias=True) if isinstance(item, BaseModel) else item
            for item in value
        ]
    if isinstance(value, dict):
        return value
    if isinstance(value, JsonPrimitive):
        return value
    raise TypeError(f"Cannot serialize value of type {type(value)!r} to JSON")
