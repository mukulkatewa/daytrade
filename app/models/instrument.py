from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, IdMixin


class Instrument(IdMixin, CreatedAtMixin, Base):
    """A tradable stock, e.g. RELIANCE. Rows are seeded, not created by users."""

    __tablename__ = "instruments"
    __table_args__ = (
        # "IS NULL OR ..." lets the column stay empty, but if set it must be valid.
        CheckConstraint("last_price IS NULL OR last_price > 0", name="last_price_positive"),
    )

    symbol: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)

    # Last traded price, used to value holdings for P&L. `| None` -> nullable:
    # NULL until the first trade (or a seeded starting price).
    # NUMERIC(12,2) matches the cash scale so price x quantity is exact.
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # When False, new orders for this instrument are rejected.
    # true() renders SQL `DEFAULT true`. Mapped[bool] infers the BOOLEAN type.
    is_active: Mapped[bool] = mapped_column(server_default=true())
