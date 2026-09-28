class APIServiceError(RuntimeError):
    """A sanitized service failure safe to map to an API response."""


class ExternalSearchError(APIServiceError):
    pass


class ExternalSearchTimeout(ExternalSearchError):
    pass


class ExternalRateLimit(ExternalSearchError):
    pass
