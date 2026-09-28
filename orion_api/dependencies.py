from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import get_settings


def require_api_key(
    x_orion_api_key: str | None = Header(default=None, alias="X-Orion-API-Key"),
) -> None:
    """Require X-Orion-API-Key only when ORION_API_KEY is configured."""
    configured = get_settings().api_key
    if configured is None:
        return
    if x_orion_api_key is None or not hmac.compare_digest(
        x_orion_api_key, configured
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
