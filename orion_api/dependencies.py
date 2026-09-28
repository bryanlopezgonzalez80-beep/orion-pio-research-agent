from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request, status


def require_api_key(
    request: Request,
    x_orion_api_key: str | None = Header(default=None, alias="X-Orion-API-Key"),
) -> None:
    """Require X-Orion-API-Key only when ORION_API_KEY is configured."""
    configured = request.app.state.settings.api_key
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
