from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# Every constraint/index in Postgres has a name. If we don't pick one, Postgres
# invents one (e.g. "orders_check1"), and later migrations that need to drop or
# change that constraint must guess it. This pattern makes every name
# predictable. %(...)s placeholders are filled in by SQLAlchemy:
#   CheckConstraint(..., name="price_positive") on "orders"
#     -> ck_orders_price_positive
#   UniqueConstraint("user_id", "client_order_id") on "orders"
#     -> uq_orders_user_id_client_order_id   (column_0_N_name = all columns)
# Because the "ck" pattern uses %(constraint_name)s, every CheckConstraint
# MUST be given a name=..., or SQLAlchemy raises an error.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent of every model. Base.metadata collects all tables; Alembic reads it."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()