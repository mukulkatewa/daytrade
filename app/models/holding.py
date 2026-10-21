from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class Holding(IdMixin, TimestampMixin, Base):
    """How many shares of one instrument an account owns right now.

    The share-side twin of Account: `reserved_quantity` is locked by open sell
    orders, exactly like reserved_cash is locked by open buy orders, so a user
    can't sell the same shares twice. This is a current snapshot; the history
    of how we got here lives in trades.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        # At most one row per (account, instrument). No name= needed: the
        # naming convention builds uq_holdings_account_id_instrument_id.
        UniqueConstraint("account_id", "instrument_id"),
        CheckConstraint("quantity >= 0", name="quantity_nonneg"),  # long-only: no short selling
        # A CHECK may compare two columns of the same row.
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="reserved_quantity_valid",
        ),
        CheckConstraint(
            "average_price IS NULL OR average_price >= 0", name="average_price_nonneg"
        ),
    )

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    instrument_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("instruments.id"))

    # Whole shares only in v1, so integers (BIGINT), not NUMERIC.
    quantity: Mapped[int] = mapped_column(BigInteger, server_default="0")
    reserved_quantity: Mapped[int] = mapped_column(BigInteger, server_default="0")

    # Weighted-average cost per share; NULL when quantity is 0. On a buy:
    #   new_avg = (old_qty * old_avg + buy_qty * buy_price) / new_qty
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
