from typing import Any

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Columns that hold raw agent/tool payloads (LLM plans, tool args, tool
# responses, provenance maps) are genuinely dynamically shaped JSON by
# design -- Any is the correct type here, not a shortcut around one.
JsonDict = dict[str, Any]
# Raw tool responses can be a single object (get_product) or a list of
# them (list_products) -- JsonDict alone can't express the list case.
JsonValue = JsonDict | list[JsonDict]
