from fastapi import APIRouter, Response, status

from database.connection import check_database_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    database = check_database_health()
    reachable = database["reachable"] and database["basic_query"] == "pass"
    read_only = database.get("read_only")
    writable_ready = database["engine"] != "postgres" or read_only is False
    if not reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if reachable and writable_ready else "degraded" if reachable else "unavailable",
        "database": {
            "engine": database["engine"],
            "reachable": database["reachable"],
            "read_only": read_only,
        },
    }
