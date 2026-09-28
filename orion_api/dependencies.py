from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from .rate_limit import CredentialSlot, RateLimitCategory, RateLimitExceeded


def _constant_time_match(candidate: str, configured: str) -> bool:
    return hmac.compare_digest(
        candidate.encode("utf-8"), configured.encode("utf-8")
    )


def require_api_key(
    request: Request,
    x_orion_api_key: str | None = Header(default=None, alias="X-Orion-API-Key"),
) -> CredentialSlot | None:
    """Require X-Orion-API-Key only when ORION_API_KEY is configured."""
    settings = request.app.state.settings
    if settings.api_key is None:
        return None
    primary_matches = x_orion_api_key is not None and _constant_time_match(
        x_orion_api_key, settings.api_key
    )
    secondary_matches = (
        x_orion_api_key is not None
        and settings.api_key_secondary is not None
        and _constant_time_match(x_orion_api_key, settings.api_key_secondary)
    )
    if not primary_matches and not secondary_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return (
        CredentialSlot.PRIMARY
        if primary_matches
        else CredentialSlot.SECONDARY
    )


def _consume_quota(
    request: Request,
    credential_slot: CredentialSlot | None,
    category: RateLimitCategory,
) -> None:
    if credential_slot is None:
        return
    try:
        request.app.state.rate_limiter.consume(credential_slot, category)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from None


def require_read_quota(
    request: Request,
    credential_slot: Annotated[CredentialSlot | None, Depends(require_api_key)],
) -> None:
    _consume_quota(request, credential_slot, RateLimitCategory.READ)


def require_write_quota(
    request: Request,
    credential_slot: Annotated[CredentialSlot | None, Depends(require_api_key)],
) -> None:
    _consume_quota(request, credential_slot, RateLimitCategory.WRITE)


def require_search_quota(
    request: Request,
    credential_slot: Annotated[CredentialSlot | None, Depends(require_api_key)],
) -> None:
    _consume_quota(request, credential_slot, RateLimitCategory.SEARCH)
