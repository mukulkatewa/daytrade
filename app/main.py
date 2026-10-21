import logging

from fastapi import FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.get('/health/db')
def db_health_check(response: Response):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Log the details server-side; never leak DB errors to clients.
        logger.exception("Database health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unavailable"}

    return {"status": "ok", "database": "connected"}
