from pydantic import BaseModel


class SourceResponse(BaseModel):
    name: str
    domain: str
    authority: str
    automated: bool
    free_access: bool
    official_url: str = ""
    status: str = "unknown"
    last_checked: str | None = None
    minimum_interval_seconds: float = 0.0
    rate_guidance: str = ""
