from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

# Orders that are still resting in the order book and can be matched.
# PARTIALLY_FILLED counts: its unfilled remainder is still tradable.
OPEN_STATUSES = "status IN ('OPEN', 'PARTIALLY_FILLED')"


class Order(IdMixin, TimestampMixin, Base):
    """One limit order submitted by a user.

    Lifecycle (see docs/schema.md section 3):
        OPEN -> PARTIALLY_FILLED -> FILLED
        OPEN / PARTIALLY_FILLED -> CANCELLED
        REJECTED (never enters the book)
    FILLED, CANCELLED and REJECTED are terminal: no transitions out of them.
    """

    __tablename__ = "orders"  # "order" is a reserved SQL word (ORDER BY)
    __table_args__ = (
        # Idempotency: the client sends its own client_order_id with every
        # order. A retried request reuses it, so the second INSERT fails here
        # instead of creating a duplicate order. Unique per user, not
        # globally, because two users may happen to pick the same id.
        UniqueConstraint("user_id", "client_order_id"),
        # TEXT + CHECK instead of a Postgres ENUM: adding a value later is a
        # simple constraint change, while ENUM types are painful to alter.
        CheckConstraint("side IN ('BUY', 'SELL')", name="side_valid"),
        CheckConstraint("order_type IN ('LIMIT')", name="order_type_valid"),
        CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_FILLED', 'FILLED', 'CANCELLED', 'REJECTED')",
            name="status_valid",
        ),
        CheckConstraint("price > 0", name="price_positive"),
        # Tick size: prices move in steps of 0.05 (like NSE).
        # Use mod(), NOT `price % 0.05`: Alembic escapes % to %% (because % marks
        # parameters in Python DB drivers) and Postgres then rejects `%%`.
        CheckConstraint("mod(price, 0.05) = 0", name="price_tick_size"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # You can never fill more than you asked for.
        CheckConstraint(
            "filled_quantity >= 0 AND filled_quantity <= quantity",
            name="filled_quantity_valid",
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    instrument_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("instruments.id"))
    client_order_id: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    # Only LIMIT in v1. The column exists so MARKET can be added later.
    order_type: Mapped[str] = mapped_column(Text, server_default="LIMIT")
    # Limit price: the most a buyer will pay / the least a seller will accept.
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(BigInteger)
    # Grows with each partial fill; remaining = quantity - filled_quantity.
    filled_quantity: Mapped[int] = mapped_column(BigInteger, server_default="0")
    status: Mapped[str] = mapped_column(Text, server_default="OPEN")


# --- Indexes -----------------------------------------------------------------
# Defined after the class because `Order.price.desc()` needs the class to
# exist. Creating an Index with Order's columns attaches it to the table.
#
# The matching engine's hot query is "best opposite orders for instrument X":
#   best bid = highest buy price first, oldest first
#   best ask = lowest sell price first, oldest first
# Column order matters: instrument_id narrows the search, then price gives
# price priority, then id (always increasing) gives time priority.
#
# postgresql_where makes them PARTIAL indexes: they only contain orders that
# are currently in the book, not the ever-growing pile of FILLED/CANCELLED
# history, so they stay small and fast.
Index(
    "ix_orders_book_buy",
    Order.instrument_id,
    Order.price.desc(),
    Order.id,
    postgresql_where=text(f"side = 'BUY' AND {OPEN_STATUSES}"),
)
Index(
    "ix_orders_book_sell",
    Order.instrument_id,
    Order.price,
    Order.id,
    postgresql_where=text(f"side = 'SELL' AND {OPEN_STATUSES}"),
)
# "My orders, newest first" for the order-history screen.
Index("ix_orders_user_created", Order.user_id, Order.created_at.desc())
