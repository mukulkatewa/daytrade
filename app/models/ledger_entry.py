from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, IdMixin


class LedgerEntry(IdMixin, CreatedAtMixin, Base):
    """Append-only record of every cash movement - the source of truth.

    Rules:
    - Never UPDATE or DELETE a row. Fix mistakes by adding a REVERSAL entry.
    - Amounts are signed: +100000.00 for a deposit, -5000.00 for a buy.
    - Invariant, per account:
          SUM(amount) == available_cash + reserved_cash
      accounts holds the fast running balance; the ledger is the proof.
      If they ever disagree, there is a bug (and we can detect it).
    - Reserving cash for an order only moves it between available and
      reserved, the total doesn't change, so it creates NO ledger entry.
    - Insert the entry and update the account in the SAME transaction.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_nonzero"),
        # Adjacent string literals are joined by Python into one string.
        CheckConstraint(
            "entry_type IN ('DEPOSIT', 'WITHDRAWAL', 'BUY_SETTLEMENT', "
            "'SELL_SETTLEMENT', 'FEE', 'REVERSAL')",
            name="entry_type_valid",
        ),
    )

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    # Nullable FK: a DEPOSIT has no trade, so trade_id is NULL for it.
    trade_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("trades.id"), index=True)
    entry_type: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))


# "Ledger history for my account, newest first."
Index("ix_ledger_entries_account_created", LedgerEntry.account_id, LedgerEntry.created_at.desc())
