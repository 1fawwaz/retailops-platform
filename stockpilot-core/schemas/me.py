from pydantic import BaseModel, ConfigDict

from schemas.user import UserRead


class MeRead(BaseModel):
    """docs/ARCHITECTURE.md §6: the ONE call both a profile page and the
    RBAC layer share, not two separate endpoints computing the same
    thing differently. Extended here (Backend Module 10) now that real
    roles/permissions data exists to resolve -- Backend Module 1 shipped
    this endpoint returning profile only, deliberately, since this data
    didn't exist yet.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user": {
                        "id": 1,
                        "email": "demo@retailops.local",
                        "is_active": True,
                        "is_read_only": False,
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    "roles": ["inventory_manager"],
                    "permissions": ["inventory:read", "inventory:update", "products:read"],
                }
            ]
        }
    )

    user: UserRead
    roles: list[str]
    permissions: list[str]
