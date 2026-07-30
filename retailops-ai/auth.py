"""Stage 6 backend hardening: JWT validation for retailops-ai's own API.

Per docs/BUILD-SPEC.md's own words -- "JWT integrated with StockPilot's
auth, no second user system" -- this service has no login endpoint, no
password hashing, and no user table of its own. It trusts tokens issued
by StockPilot's own /auth/login (stockpilot-core/services/security.py::
create_access_token) purely via a shared secret: both services' `.env`
files carry the identical JWT_SECRET/JWT_ALGORITHM values (synced once
for local dev the same way STOCKPILOT_USERNAME/PASSWORD were copied
across in Stage 2 Task 2.2 -- see project memory). Verifying the
signature and expiry is sufficient; this service never re-queries
StockPilot's user table to confirm the subject still exists or is
active, the same way any downstream service in a shared-secret JWT
design trusts whichever principal the issuer already vouched for rather
than re-authenticating it.

Deliberately at the service root, not under api/ -- it mirrors
settings.py/database.py/logging_config.py's existing pattern of
service-wide singletons/utilities that many layers depend on, not a
route-specific concern.
"""

from __future__ import annotations

import jwt

from settings import get_settings


def decode_bearer_subject(token: str) -> str:
    """Return the token's subject (the StockPilot user's email), or raise
    jwt.PyJWTError (or a subclass) if the signature, expiry, or shape is
    invalid. Mirrors stockpilot-core/services/security.py::decode_access_token
    exactly, since both services must agree on what a valid token looks
    like -- there is no second definition of "valid" to invent here.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    subject = payload["sub"]
    if not isinstance(subject, str):
        raise jwt.InvalidTokenError("Token subject is not a string")
    return subject
