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
