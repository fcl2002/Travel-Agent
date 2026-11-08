"""HTTP entry point for the Travel Agent backend."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.database import get_engine

app = FastAPI(title="Travel Agent API", version="0.1.0")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
def database_health(engine: Annotated[Engine, Depends(get_engine)]) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}
