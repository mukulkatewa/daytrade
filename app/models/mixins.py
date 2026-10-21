"""Reusable column groups shared by many tables.

A mixin is a plain class holding columns. A model that inherits from it gets
those columns, so `id` and timestamps are written once instead of seven times.

How a column definition reads:
    name: Mapped[python_type] = mapped_column(SQL_TYPE, options...)

- Mapped[int]          -> NOT NULL column holding an int.
- Mapped[int | None]   -> NULLABLE column. The `| None` is the ONLY thing that
                          makes a column nullable.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, func
from sqlalchemy.orm import Mapped, mapped_column


class IdMixin:
    # BIGINT GENERATED ALWAYS AS IDENTITY: Postgres hands out 1, 2, 3, ...
    # Ids only ever increase, so orders.id doubles as the time-priority
    # tie-breaker in the order book. Ids are never reused, so gaps are normal
    # (a failed INSERT still consumes one) - never assume ids are consecutive.
    # sort_order=-1 just places `id` first in the table instead of last.
    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, sort_order=-1
    )


class CreatedAtMixin:
    # TIMESTAMPTZ stores an absolute moment in time (timezone-aware).
    # server_default=func.now() -> SQL `DEFAULT now()`: the DATABASE sets the
    # value, so every app server agrees on one clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    # onupdate=func.now(): whenever SQLAlchemy UPDATEs this row, it also sets
    # updated_at = now(). Note: raw SQL UPDATEs (e.g. in psql) won't trigger it.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
