from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class Account(IdMixin, TimestampMixin, Base):
    """A user's virtual cash. One account per user in v1.

    Cash lives in two buckets:
      available_cash - free to spend on new buy orders
      reserved_cash  - locked by open buy orders, so it can't be spent twice
    Placing a buy order moves cash available -> reserved; a fill spends it;
    a cancel moves the unfilled part back. The total only changes on real
    cash movements, which are recorded in ledger_entries.
    """

    __tablename__ = "accounts"

    # __table_args__ holds table-level rules: CHECKs, multi-column UNIQUEs,
    # indexes. It must be a TUPLE (with one item, keep a trailing comma).
    # CHECK constraints are the database's last line of defence: even if
    # application code has a bug, Postgres refuses a negative balance.
    __table_args__ = (
        CheckConstraint("available_cash >= 0", name="available_cash_nonneg"),
        CheckConstraint("reserved_cash >= 0", name="reserved_cash_nonneg"),
    )

    # ForeignKey uses the TABLE name ("users"), not the class name (User).
    # BigInteger must be explicit: plain Mapped[int] would give INTEGER, which
    # doesn't match users.id (BIGINT). unique=True enforces one account per user.
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)

    # NUMERIC(18,2): exact decimal with 2 places (rupees.paise). Python sees
    # Decimal, never float - floats can't represent 0.1 exactly.
    available_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), server_default="0")
    reserved_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), server_default="0")
