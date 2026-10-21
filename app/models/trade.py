from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin


class Trade(IdMixin, Base):
    """One execution: a buy order and a sell order matched for some quantity.

    One order can produce many trades (partial fills), so orders 1:N trades.
    Trades are history: written once, never updated.

    Rules the database can't check (they span several rows) and that the
    matching engine must enforce inside a transaction: both orders are for
    the same instrument, have opposite sides, are still open, and the trade
    quantity fits in each order's remaining quantity.
    """

    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("buy_order_id <> sell_order_id", name="distinct_orders"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    # Two foreign keys to the same table. index=True -> fast "trades for this order".
    buy_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), index=True)
    sell_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), index=True)

    # Execution price = the resting (maker) order's price.
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(BigInteger)

    # Named executed_at (not created_at), so no timestamp mixin here.
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
