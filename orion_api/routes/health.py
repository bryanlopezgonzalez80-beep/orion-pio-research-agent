from fastapi import APIRouter, Response, status

from database.connection import check_database_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    database = check_database_health()
    healthy = database["reachable"] and database["basic_query"] == "pass"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "unavailable",
        "database": {
            "engine": database["engine"],
            "reachable": database["reachable"],
        },
    }
