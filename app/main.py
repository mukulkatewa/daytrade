from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

app = FastAPI(title=settings.app_name)

@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.get('/health/db')
def db_health_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = value.scalar_one()

        return {
            "status": "ok",
            "database": "connected",
            "query_result": value,
        }