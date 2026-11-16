from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_database_probe
from app.repositories.database_probe import DatabaseProbe

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def database_health(probe: Annotated[DatabaseProbe, Depends(get_database_probe)]) -> dict[str, str]:
    if not await probe.is_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
